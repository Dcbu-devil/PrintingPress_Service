#checking if database connection is successful or not?
from sqlalchemy import text
from app.database import engine

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT current_database()"))
        print("✅ Database Connected Successfully")
        print("Database:", result.scalar())
except Exception as e:
    print("❌ Connection Failed")
    print(e)