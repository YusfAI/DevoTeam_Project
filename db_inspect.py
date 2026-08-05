from backend.db import get_connection

def inspect():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM v_by_month LIMIT 5")
                print("v_by_month:", cur.fetchall())
                
                cur.execute("SELECT COUNT(*) FROM opportunities")
                print("opp_count:", cur.fetchone())
    except Exception as e:
        print("Error:", e)

inspect()
