from enum import Enum

class KYCStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"

class EntryType(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"

class LedgerEntryStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    REVERSED = "reversed"

class TransactionType(str, Enum):
    REVERSAL = "reversal"
    TRANSFER = "transfer"
    PAYMENT = "payment"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    FEE = "fee"

class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"

class AccountType(str, Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT = "credit"

class AccountStatus(str, Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"

class DocumentType(str, Enum):
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    ID_CARD = "id_card"
    NATIONAL_ID = "national_id"

class VerificationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class UserRole(str, Enum):
    ADMIN = "admin"
    COMPLIANCE = "compliance"
    SUPPORT = "support"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class AMLResolution(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REVIEW = "review"
    BLOCKED = "blocked"

class CardStatus(str, Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CANCELLED = "cancelled"


class CustomerType(str, Enum):
    """Gates nothing directly today, but promoted to a real DB enum
    anyway (Section 8) since business-vs-personal customers are
    expected to diverge in limits/rules later — cheap to enforce now."""
    PERSONAL = "personal"
    BUSINESS = "business"

class CustomerStatus(str, Enum):
    """Renamed from the source docs' Customer.account_status (Section 8)
    to avoid colliding with Account.account_status — a customer being
    frozen (this) and one specific account being frozen (that) are
    different things that must not share a name. Gates whether the
    customer can transact at all — promoted to a DB enum."""
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"

class CardType(str, Enum):
    """Purely descriptive (what kind of card this is) — does not gate
    a decision by itself (CardStatus does that). Left as an app-level
    enum only; the DB column stays a free string (Section 8)."""
    VIRTUAL = "virtual"
    DEBIT = "debit"
    CREDIT = "credit"

class AMLCheckType(str, Enum):
    """Purely descriptive/categorical, same reasoning as CardType —
    app-level only, DB column stays a free string."""
    TRANSACTION = "transaction"
    CUSTOMER = "customer"
    BENEFICIARY = "beneficiary"
