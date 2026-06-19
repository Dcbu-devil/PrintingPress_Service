import secrets
from sqlalchemy.orm import Session


# ============================================================
# ORDER ID GENERATION
# ============================================================
# Generates sequential order IDs like ORD-1001, ORD-1002, etc.
#
# Uses the highest existing order ID number to determine
# the next available number. Includes uniqueness check
# to prevent duplicate IDs under concurrent access.

def generate_order_id(db: Session) -> str:
    from app.models import Order

    last_order = db.query(Order).order_by(Order.id.desc()).first()

    if not last_order or not last_order.order_id:
        return "ORD-1001"

    try:
        last_num = int(last_order.order_id.split("-")[1])
        next_num = last_num + 1
    except (IndexError, ValueError):
        next_num = 1001 + db.query(Order).count()

    order_id = f"ORD-{next_num}"

    # Ensure uniqueness in case of gaps or manual entries
    while db.query(Order).filter(Order.order_id == order_id).first():
        next_num += 1
        order_id = f"ORD-{next_num}"

    return order_id


# ============================================================
# PAYMENT ID GENERATION
# ============================================================
# Generates sequential payment IDs like PAY-1001, PAY-1002, etc.
#
# Uses the highest existing payment ID number to determine
# the next available number. extra_count is used when creating
# multiple payment records in a single transaction
# (e.g., direct + parent + grandparent member payments).

def generate_payment_id(db: Session, extra_count: int = 0) -> str:
    from app.models import CommissionPayment

    last_payment = (
        db.query(CommissionPayment)
        .order_by(CommissionPayment.id.desc())
        .first()
    )

    if not last_payment or not last_payment.payment_id:
        base_num = 1001
    else:
        try:
            base_num = int(last_payment.payment_id.split("-")[1]) + 1
        except (IndexError, ValueError):
            base_num = 1001 + db.query(CommissionPayment).count()

    next_num = base_num + extra_count
    payment_id = f"PAY-{next_num}"

    # Ensure uniqueness
    while (
        db.query(CommissionPayment)
        .filter(CommissionPayment.payment_id == payment_id)
        .first()
    ):
        next_num += 1
        payment_id = f"PAY-{next_num}"

    return payment_id


# ============================================================
# TEMPORARY PASSWORD GENERATION
# ============================================================
# Generates a default password for new member accounts.
# Used when admin creates a member. The default password is set
# to "password" as documented in the frontend login page.

def generate_temp_password() -> str:
    return "password"

