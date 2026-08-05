from backend.db import get_connection

def setup_tables():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                prompt TEXT,
                intent_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS generated_dashboards (
                intent_hash VARCHAR(64) PRIMARY KEY,
                vega_spec JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
        conn.commit()
    print("Tables created successfully.")

if __name__ == "__main__":
    setup_tables()
