from datetime import date

from app.database import SessionLocal
from app.models import User, Role
from app.auth import get_password_hash


def create_super_admin():
    db = SessionLocal()

    try:
        admin_role = (
            db.query(Role)
            .filter(Role.name == "admin")
            .first()
        )

        if not admin_role:
            print("ERROR: super_admin role not found. Please insert roles first.")
            return

        existing_user = (
            db.query(User)
            .filter(User.email == "admin@123.com")
            .first()
        )

        if existing_user:
            print("OK: Super Admin already exists.")
            print("Email: admin@123.com")
            return

        admin = User(
            name="Admin",
            email="admin@123.com",
            hashed_password=get_password_hash("admin@23"),
            role_id=admin_role.id,
            agent_id=None,
            status="Active",
            must_reset_password=False,
            created_date=str(date.today()),
            last_login=None,
        )

        db.add(admin)
        db.commit()

        print("SUCCESS: Admin created successfully.")
        print("Email: admin@123.com")
        print("Password: admin@23")

    except Exception as error:
        db.rollback()
        print("ERROR creating Super Admin:", error)

    finally:
        db.close()


if __name__ == "__main__":
    create_super_admin()