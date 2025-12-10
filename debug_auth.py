from database import init_db, SessionLocal, User
from auth import get_password_hash

print("Initializing DB...")
try:
    init_db()
    print("DB Init Success")
except Exception as e:
    print(f"DB Init Failed: {e}")

print("Testing Signup...")
try:
    db = SessionLocal()
    email = "debug@test.com"
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        print("User already exists, deleting...")
        db.delete(existing)
        db.commit()
    
    hashed_pw = get_password_hash("password")
    user = User(email=email, password_hash=hashed_pw)
    db.add(user)
    db.commit()
    print("Signup Success")
except Exception as e:
    print(f"Signup Logic Failed: {e}")
finally:
    db.close()
