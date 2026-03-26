import sys
import os

# Ensure the app module is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.base import SessionLocal
from app.models.models import User
from app.services.auth_service import get_password_hash

def seed_admin():
    db = SessionLocal()
    try:
        username = "ces_admin"
        password = "ces_admin26"
        
        # Check if exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"Admin user '{username}' already exists. Updating password and role to ensure access.")
            existing_user.hashed_password = get_password_hash(password)
            existing_user.role = "admin"
            existing_user.is_active = True
        else:
            print(f"Creating initial admin user '{username}'...")
            admin_user = User(
                username=username,
                email="admin@ces.local",
                hashed_password=get_password_hash(password),
                role="admin",
                is_active=True
            )
            db.add(admin_user)
            
        db.commit()
        print("Successfully seeded admin user.")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_admin()
