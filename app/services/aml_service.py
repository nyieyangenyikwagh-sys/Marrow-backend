from app.core.config import settings
from app.core.constants import AMLResolution, RiskLevel
from app.models.aml import AMLCheck
from app.models.customer import Customer


class AMLService:
    """Local, deterministic review rules. No external sanctions screening is implied."""
    @staticmethod
    async def check_transaction(db, customer_id, amount, transaction_type):
        customer = await db.get(Customer, customer_id)
        score = customer.risk_score
        flags = []
        if amount >= settings.TRANSACTION_REVIEW_AMOUNT:
            score = max(score, settings.AML_MEDIUM_RISK_THRESHOLD)
            flags.append("large_transaction")
        if score >= settings.AML_HIGH_RISK_THRESHOLD:
            level, resolution = RiskLevel.HIGH, AMLResolution.BLOCKED
            flags.append("high_customer_risk")
        elif score >= settings.AML_MEDIUM_RISK_THRESHOLD:
            level, resolution = RiskLevel.MEDIUM, AMLResolution.REVIEW
        else:
            level, resolution = RiskLevel.LOW, AMLResolution.APPROVED
        check = AMLCheck(customer_id=customer_id, check_type="transaction", risk_score=score,
                         risk_level=level, flags_triggered=flags, resolution=resolution)
        db.add(check)
        await db.flush()
        return check
