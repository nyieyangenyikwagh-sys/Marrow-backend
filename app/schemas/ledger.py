from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.schemas.base import ORMBase
from app.core.constants import EntryType, LedgerEntryStatus

class LedgerEntryResponse(ORMBase):
    """Read-only by design — there is no LedgerEntryCreate schema
    anywhere in this system. Per §1.1, the only way a ledger_entries
    row comes into existence is through LedgerService internally;
    nothing external ever constructs one directly via the API."""
    id: UUID
    transaction_id: UUID
    account_id: UUID
    entry_type: EntryType
    amount: Decimal
    currency_code: str
    description: str
    status: LedgerEntryStatus
    entry_date: datetime

class BalanceResponse(BaseModel):
    """Not an ORMBase — there is no `balance` row to read `from_attributes`
    from (§8.4: balance is computed live, not stored). Built explicitly
    by the service layer instead."""
    account_id: UUID
    balance: Decimal
    currency_code: str
    as_of: datetime

class StatementResponse(BaseModel):
    account_id: UUID
    period_start: datetime
    period_end: datetime
    opening_balance: Decimal
    closing_balance: Decimal
    entries: List[LedgerEntryResponse]
