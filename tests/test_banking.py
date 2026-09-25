from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.models import Transaction, LedgerEntry, User, Customer, Account, AMLCheck, AuditLog
from app.core.constants import TransactionStatus, UserRole, AccountStatus, CustomerStatus, KYCStatus
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password
from app.services.transfer_service import TransferService
from app.services.transaction_service import TransactionService
from app.services.ledger_service import LedgerService
from app.services.auth_service import AuthService
from app.services.account_service import AccountService
from tests.helpers import funded, headers


async def test_transfer_balances_fee_and_exactly_once(factory):
    async with factory() as db:
        source, dest, fees, people = await funded(db)
        kwargs=dict(from_account_id=source.id, to_account_id=dest.id, amount=Decimal("100.00"), idempotency_key="one")
        txn = await TransferService.transfer(db, **kwargs)
        await db.commit()
        duplicate = await TransferService.transfer(db, **kwargs)
        assert duplicate.id == txn.id
        assert await LedgerService.get_account_balance(db, source.id) == Decimal("24899.00")
        assert await LedgerService.get_account_balance(db, dest.id) == Decimal("100.00")
        assert await LedgerService.get_account_balance(db, fees.id) == Decimal("1.00")
        assert await db.scalar(select(func.count()).select_from(LedgerEntry).where(LedgerEntry.transaction_id == txn.id)) == 4
        assert await LedgerService.verify_ledger_integrity(db, txn.id)
        with pytest.raises(ValueError, match="different request"):
            await TransferService.transfer(db, **{**kwargs, "amount":Decimal("101")})


async def test_pending_approval_rechecks_funds_and_is_terminal(factory):
    async with factory() as db:
        source, dest, fees, people = await funded(db, "15000")
        pending = await TransferService.transfer(db, source.id, dest.id, Decimal("10000"), idempotency_key="pending")
        assert pending.status == TransactionStatus.PENDING
        pending_id = pending.id
        assert not await LedgerService.verify_ledger_integrity(db, pending.id)
        await db.commit()
        await TransferService.transfer(db, source.id, dest.id, Decimal("6000"), idempotency_key="spend")
        await db.commit()
        with pytest.raises(ValueError, match="Insufficient"):
            await TransactionService.review_approve(db, pending.id, uuid4(), "Reviewed")
        await db.rollback()
        rejected = await TransactionService.review_reject(db, pending_id, uuid4(), "Insufficient funds")
        await db.commit()
        assert rejected.status == TransactionStatus.FAILED
        with pytest.raises(ValueError, match="Cannot transition"):
            await TransactionService.review_approve(db, rejected.id, uuid4(), "Retry")


async def test_review_and_reversal_are_audited_and_immutable(factory):
    async with factory() as db:
        source, dest, fees, people = await funded(db)
        txn = await TransferService.transfer(db, source.id, dest.id, Decimal("10000"), idempotency_key="review")
        await db.commit()
        await TransactionService.review_approve(db, txn.id, uuid4(), "Source checked")
        await db.commit()
        original = (await db.scalars(select(LedgerEntry).where(LedgerEntry.transaction_id == txn.id))).all()
        snapshot = [(x.id,x.amount,x.entry_type) for x in original]
        reversal = await TransactionService.reverse(db, txn.id, uuid4(), "Customer request")
        await db.commit()
        assert reversal.reverses_transaction_id == txn.id
        assert await LedgerService.get_account_balance(db, source.id) == Decimal("25000")
        assert await LedgerService.get_account_balance(db, dest.id) == 0
        assert snapshot == [(x.id,x.amount,x.entry_type) for x in original]
        assert await db.scalar(select(func.count()).select_from(AuditLog)) == 3
        with pytest.raises(ValueError, match="Cannot transition"):
            await TransactionService.reverse(db, txn.id, uuid4(), "Repeat")


@pytest.mark.parametrize("guard", ["frozen", "customer_frozen", "kyc", "currency", "limit", "same", "funds"])
async def test_transfer_guards_leave_no_posting(factory, guard):
    async with factory() as db:
        source, dest, fees, people = await funded(db)
        amount = Decimal("100")
        if guard == "frozen": source.account_status = AccountStatus.FROZEN
        if guard == "customer_frozen": people[0].customer_status = CustomerStatus.FROZEN
        if guard == "kyc": people[0].kyc_status = KYCStatus.PENDING
        if guard == "currency": dest.currency_code = "USD"
        if guard == "limit": source.daily_limit = Decimal("100")
        if guard == "funds": amount = Decimal("25000")
        await db.commit()
        with pytest.raises((ValueError, PermissionError)):
            await TransferService.transfer(db, source.id, source.id if guard=="same" else dest.id, amount, idempotency_key="guard")
        assert await db.scalar(select(func.count()).select_from(Transaction)) == 1


async def test_small_fee_rounds_to_zero_without_zero_entries(factory):
    async with factory() as db:
        source,dest,_,_=await funded(db)
        txn=await TransferService.transfer(db,source.id,dest.id,Decimal("0.01"),idempotency_key="penny")
        await db.commit()
        assert txn.fee_amount==0
        assert await db.scalar(select(func.count()).select_from(LedgerEntry).where(LedgerEntry.transaction_id==txn.id))==2


async def test_rollback_removes_all_legs_and_request(factory, monkeypatch):
    async with factory() as db:
        source,dest,_,_=await funded(db)
        source_id,dest_id=source.id,dest.id
        original=LedgerService.create_entry
        calls=0
        async def fail(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==3: raise RuntimeError("Injected failure")
            return await original(*args,**kwargs)
        monkeypatch.setattr(LedgerService,"create_entry",fail)
        with pytest.raises(RuntimeError):
            await TransferService.transfer(db,source_id,dest_id,Decimal("100"),idempotency_key="rollback")
        await db.rollback()
        assert await db.scalar(select(func.count()).select_from(Transaction))==1
        assert await db.scalar(select(func.count()).select_from(LedgerEntry))==2
        assert await LedgerService.get_account_balance(db,source_id)==Decimal("25000")


async def test_statement_start_boundary_is_not_double_counted(factory):
    async with factory() as db:
        source,_,_,_=await funded(db)
        entry=await db.scalar(select(LedgerEntry).where(LedgerEntry.account_id==source.id))
        statement=await LedgerService.get_statement(db,source.id,entry.entry_date.replace(tzinfo=timezone.utc),datetime.now(timezone.utc))
        assert statement["opening_balance"]==0
        assert statement["closing_balance"]==Decimal("25000")


async def test_signup_login_and_role_preserving_refresh(client,factory,redis):
    data=dict(email="new@example.com",password="LongPassword123!",first_name="New",last_name="Customer")
    signup=await client.post('/api/v1/auth/signup',json=data)
    assert signup.status_code==201,signup.text
    login=await client.post('/api/v1/auth/login',json={"email":data["email"],"password":data["password"]})
    assert login.status_code==200
    token=login.json()["access_token"]
    profile=await client.get('/api/v1/customers/me',headers={"Authorization":f"Bearer {token}"})
    assert "password_hash" not in profile.json()
    assert profile.json()["kyc_status"]=="pending"
    async with factory() as db:
        staff=User(email="staff@example.com",password_hash=hash_password(data["password"]),first_name="Staff",last_name="Member",role=UserRole.COMPLIANCE)
        db.add(staff);await db.commit()
        refresh=create_refresh_token(staff.id,"admin")
        access=await AuthService.refresh_access_token(db,refresh)
        assert decode_token(access)["type"]=="admin"
        await AuthService.logout(refresh)
        with pytest.raises(ValueError,match="revoked"):
            await AuthService.refresh_access_token(db,refresh)


async def test_api_ownership_precision_and_staff_permissions(client,factory):
    async with factory() as db:
        source,dest,_,people=await funded(db)
        support=User(email="support@example.com",password_hash=hash_password("LongPassword123!"),first_name="Support",last_name="User",role=UserRole.SUPPORT)
        db.add(support);await db.commit()
        payload=dict(from_account_id=str(source.id),to_account_id=str(dest.id),amount="100.00",idempotency_key="api")
        foreign=await client.post('/api/v1/transactions/transfer',json=payload,headers=headers(people[1]))
        assert foreign.status_code==403
        for amount in ("0", "-1", "1.001", "NaN", "Infinity"):
            invalid=await client.post('/api/v1/transactions/transfer',json={**payload,"amount":amount},headers=headers(people[0]))
            assert invalid.status_code==422,invalid.text
        created=await client.post('/api/v1/transactions/transfer',json=payload,headers=headers(people[0]))
        assert created.status_code==201,created.text
        assert created.json()["amount"]=="100.00"
        denied=await client.post(f'/api/v1/transactions/{created.json()["id"]}/reverse',json={"reason":"Test reason"},headers=headers(support,"admin"))
        assert denied.status_code==403
        absent=await client.get(f'/api/v1/transactions/{created.json()["id"]}',headers=headers(people[2]))
        assert absent.status_code==404


async def test_kyc_and_card_workflow(client,factory):
    async with factory() as db:
        source,_,_,people=await funded(db)
        people[0].kyc_status=KYCStatus.PENDING
        staff=User(email="reviewer@example.com",password_hash=hash_password("LongPassword123!"),first_name="Review",last_name="User",role=UserRole.COMPLIANCE)
        db.add(staff);await db.commit()
        user_headers=headers(people[0]);staff_headers=headers(staff,"admin")
    doc=await client.post('/api/v1/kyc/documents',headers=user_headers,json=dict(document_type="passport",document_number="TEST123",document_front_url="https://example.com/test.png",selfie_url="https://example.com/selfie.png"))
    assert doc.status_code==201,doc.text
    assert "document_number" not in doc.json()
    review=await client.post(f'/api/v1/kyc/{doc.json()["id"]}/review',headers=staff_headers,json={"approve":True,"notes":"Test identity reviewed"})
    assert review.status_code==200,review.text
    card=await client.post('/api/v1/cards',headers=user_headers,json={"account_id":str(source.id),"card_holder_name":"Test User"})
    assert card.status_code==201,card.text
    assert "cvv_encrypted" not in card.json()
    freeze=await client.patch(f'/api/v1/cards/{card.json()["id"]}/status',headers=user_headers,json={"status":"frozen"})
    assert freeze.json()["card_status"]=="frozen"
