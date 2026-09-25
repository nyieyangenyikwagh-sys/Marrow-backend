from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from app.models import User, KYCAttachment, AuditLog, LedgerEntry
from app.core.constants import UserRole, KYCStatus
from app.core.security import hash_password
from app.services.reconciliation_service import reconcile
from app.services.transfer_service import TransferService
from tests.helpers import funded, headers


async def setup(factory):
    async with factory() as db:
        source, dest, fee, people = await funded(db)
        staff = User(email="operations@example.com", password_hash=hash_password("TestingPassword123!"),
                     first_name="Operations", last_name="Reviewer", role=UserRole.COMPLIANCE)
        support = User(email="support@example.com", password_hash=staff.password_hash,
                       first_name="Support", last_name="Member", role=UserRole.SUPPORT)
        db.add_all([staff, support])
        people[0].kyc_status = KYCStatus.PENDING
        await db.commit()
        return source, dest, people, headers(staff, "admin"), headers(support, "admin")


async def test_encrypted_upload_ownership_review_and_audit(client, factory):
    source, dest, people, staff, support = await setup(factory)
    user = headers(people[0])
    content = b"\x89PNG\r\n\x1a\nidentity-test-content"
    refs = {}
    for role in ("front", "selfie"):
        result = await client.post("/api/v1/kyc/attachments", headers=user, data={"role": role},
                                   files={"file": ("identity.png", content, "image/png")})
        assert result.status_code == 201, result.text
        refs[role] = result.json()
    attachment_id = refs["front"]["id"]
    async with factory() as db:
        stored = await db.get(KYCAttachment, UUID(attachment_id))
        assert content not in stored.encrypted_data
        # A pending second customer cannot reference someone else's upload.
        from app.models import Customer
        other = await db.get(Customer, people[1].id)
        other.kyc_status = KYCStatus.PENDING
        await db.commit()
    data = dict(document_type="passport", document_number="TEST-123",
                document_front_url=refs["front"]["reference"], selfie_url=refs["selfie"]["reference"])
    foreign = await client.post("/api/v1/kyc/documents", headers=headers(people[1]), json=data)
    assert foreign.status_code == 400
    wrong_role = await client.post("/api/v1/kyc/documents", headers=user, json={**data, "selfie_url": refs["front"]["reference"]})
    assert wrong_role.status_code == 400
    submitted = await client.post("/api/v1/kyc/documents", headers=user, json=data)
    assert submitted.status_code == 201, submitted.text
    for denied in (user, support):
        assert (await client.get(f"/api/v1/admin/attachments/{attachment_id}", headers=denied)).status_code in (401, 403)
    viewed = await client.get(f"/api/v1/admin/attachments/{attachment_id}", headers=staff)
    assert viewed.content == content
    assert viewed.headers["content-type"] == "image/png"
    assert "attachment;" in viewed.headers["content-disposition"]
    reviewed = await client.post(f'/api/v1/kyc/{submitted.json()["id"]}/review', headers=staff,
                                 json={"approve": True, "notes": "Identity files inspected"})
    assert reviewed.status_code == 200
    async with factory() as db:
        assert await db.scalar(select(AuditLog.id).where(AuditLog.action == "sensitive_file_viewed"))
    invalid = await client.post("/api/v1/kyc/attachments", headers=user, data={"role": "front"},
                                files={"file": ("bad.html", b"<script>alert(1)</script>", "image/png")})
    assert invalid.status_code == 400
    oversized = await client.post("/api/v1/kyc/attachments", headers=user, data={"role": "front"},
                                  files={"file": ("big.png", content + b"x" * (5 * 1024 * 1024), "image/png")})
    assert oversized.status_code == 413


async def test_risk_changes_affect_transfers_and_staff_pagination(client, factory):
    source, dest, people, staff, support = await setup(factory)
    from app.models import Customer
    async with factory() as db:
        sender = await db.get(Customer, people[0].id)
        sender.kyc_status = KYCStatus.VERIFIED
        await db.commit()
        pending = await TransferService.transfer(db, source.id, dest.id, Decimal("11000"), idempotency_key="before-risk-change")
        await db.commit()
        pending_id = pending.id
    path = f"/api/v1/admin/customers/{people[0].id}/risk"
    assert (await client.patch(path, headers=support, json={"score": 90, "reason": "Manual screening"})).status_code == 403
    assert (await client.patch(path, headers=staff, json={"score": 101, "reason": "Manual screening"})).status_code == 422
    result = await client.patch(path, headers=staff, json={"score": 90, "reason": "Manual screening"})
    assert result.json()["risk_level"] == "high"
    approval = await client.post(f"/api/v1/transactions/{pending_id}/review/approve", headers=staff,
                                 json={"notes": "Recheck current customer risk"})
    assert approval.status_code == 403
    async with factory() as db:
        txn = await TransferService.transfer(db, source.id, dest.id, Decimal("100"), idempotency_key="risk-test")
        await db.commit()
        assert txn.status.value == "failed"
        assert (await reconcile(db))["ok"]
    checks = await client.get("/api/v1/admin/aml?resolution=blocked", headers=staff)
    assert len(checks.json()) == 1
    first = (await client.get("/api/v1/admin/customers?limit=1", headers=support)).json()
    second = (await client.get("/api/v1/admin/customers?limit=1&offset=1", headers=support)).json()
    assert first[0]["id"] != second[0]["id"]
    found = (await client.get(f"/api/v1/admin/customers?q={people[0].id}", headers=staff)).json()
    assert len(found) == 1
    audit = (await client.get("/api/v1/admin/audit?q=risk_assessed", headers=staff)).json()
    assert len(audit) == 1 and audit[0]["new_values"]["score"] == 90
    assert (await client.get("/api/v1/admin/audit", headers=support)).status_code == 403


async def test_card_and_account_limit_changes(client, factory):
    source, dest, people, staff, support = await setup(factory)
    from app.models import Customer
    async with factory() as db:
        sender = await db.get(Customer, people[0].id)
        sender.kyc_status = KYCStatus.VERIFIED
        await db.commit()
    user = headers(people[0])
    created = await client.post("/api/v1/cards", headers=user, json={"account_id": str(source.id), "card_holder_name": "Test Person"})
    path = f'/api/v1/cards/{created.json()["id"]}'
    assert (await client.patch(path + "/limits", headers=headers(people[1]), json={"daily_limit": "10"})).status_code == 400
    assert (await client.patch(path + "/limits", headers=user, json={"daily_limit": "1.001"})).status_code == 422
    changed = await client.patch(path + "/limits", headers=user, json={"daily_limit": "50.25", "monthly_limit": "100"})
    assert changed.json()["daily_limit"] == "50.25"
    cleared = await client.patch(path + "/limits", headers=user, json={"daily_limit": None})
    assert cleared.json()["daily_limit"] is None and cleared.json()["monthly_limit"] == "100.00"
    await client.patch(path + "/status", headers=user, json={"status": "cancelled"})
    assert (await client.patch(path + "/limits", headers=user, json={"daily_limit": "10"})).status_code == 400
    account_path = f"/api/v1/accounts/{source.id}/limits"
    assert (await client.patch(account_path, headers=staff, json={"daily_limit": "100"})).status_code == 200
    cleared = await client.patch(account_path, headers=staff, json={"daily_limit": None})
    assert cleared.json()["daily_limit"] is None
    assert (await client.get("/api/v1/admin/accounts", headers=support)).status_code == 403


async def test_csv_statement_authorization_and_reconciliation(client, factory):
    source, dest, people, staff, support = await setup(factory)
    params = {"start": "2020-01-01T00:00:00Z", "end": datetime.now(timezone.utc).isoformat()}
    path = f"/api/v1/ledger/{source.id}/statement-csv"
    response = await client.get(path, headers=headers(people[0]), params=params)
    assert response.status_code == 200, response.text
    assert "Opening balance" in response.text and "Closing balance,,,25000.00,CAD" in response.text
    assert (await client.get(path, headers=headers(people[1]), params=params)).status_code == 404
    assert (await client.get(path, headers=headers(people[0]), params={**params, "start": "2020-01-01"})).status_code == 400
    async with factory() as db:
        assert (await reconcile(db))["ok"]
        # Bypass ORM invariants to emulate damaged legacy data in the SQLite test database.
        from sqlalchemy import update
        await db.execute(update(LedgerEntry).where(LedgerEntry.account_id == source.id).values(amount=Decimal("24999")))
        report = await reconcile(db)
        assert not report["ok"] and report["issues"]["unbalanced_transactions"]
