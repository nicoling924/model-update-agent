"""Evidence required before a model row becomes a zero-balance objective."""
from openpyxl.formula.tokenizer import Tokenizer


def check_identity(wb, sheet, coord, reason, candidates):
    """A semantic declaration must agree with the model's arithmetic evidence.

    Discovery nominates residuals from historical reconciliation. Naming an
    ordinary input or calculated quantity cannot make its expected value zero.
    """
    if not isinstance(reason, str) or not reason.strip():
        return False, "explain the accounting identity for this individual check"
    cell = wb[sheet][coord]
    if not isinstance(cell.value, str) or not cell.value.startswith("="):
        return False, "an input is not an accounting identity"
    try:
        tokens = Tokenizer(cell.value).items
    except Exception:
        return False, "the proposed check formula cannot be read"
    if not any(t.type == "OPERAND" and t.subtype == "RANGE" for t in tokens):
        return False, "a check must reconcile live model operands"
    if cell.row not in candidates:
        return False, "the model's historical arithmetic has not established a zero identity"
    return True, ""
