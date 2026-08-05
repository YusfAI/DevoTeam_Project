import os
from backend.db import get_connection

def test_connection():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM opportunities;")
                row = cur.fetchone()
                print(f"Connection successful. Row count: {row['cnt']}")
    except Exception as e:
        print(f"Error connecting to DB: {e}")

if __name__ == "__main__":
    test_connection()
