from app.core.constants import TransactionStatus

TRANSACTION_TRANSITIONS = {
    TransactionStatus.PENDING: {TransactionStatus.COMPLETED, TransactionStatus.FAILED},
    TransactionStatus.COMPLETED: {TransactionStatus.REVERSED},
    TransactionStatus.FAILED: set(),
    TransactionStatus.REVERSED: set(),
}


def can_transition(current, target):
    return target in TRANSACTION_TRANSITIONS.get(current, set())


def validate_transition(current, target):
    if not can_transition(current, target):
        raise ValueError(f"Cannot transition transaction from '{current.value}' to '{target.value}'")
