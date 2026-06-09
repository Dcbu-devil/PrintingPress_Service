from datetime import date

from app.database import SessionLocal
from app.models import User, Role
from app.auth import hash_password


def create_super_admin():
    db = SessionLocal()

    try:
        super_admin_role = (
            db.query(Role)
            .filter(Role.name == "super_admin")
            .first()
        )

        if not super_admin_role:
            print("❌ super_admin role not found. Please insert roles first.")
            return

        existing_user = (
            db.query(User)
            .filter(User.email == "super@admin.com")
            .first()
        )

        if existing_user:
            print("✅ Super Admin already exists.")
            print("Email: super@admin.com")
            return

        super_admin = User(
            name="Super Admin",
            email="super@admin.com",
            hashed_password=hash_password("admin123"),
            role_id=super_admin_role.id,
            agent_id=None,
            status="Active",
            created_date=str(date.today()),
            last_login=None,
        )

        db.add(super_admin)
        db.commit()

        print("✅ Super Admin created successfully.")
        print("Email: super@admin.com")
        print("Password: admin123")

    except Exception as error:
        db.rollback()
        print("❌ Error creating Super Admin:", error)

    finally:
        db.close()


if __name__ == "__main__":
    create_super_admin()