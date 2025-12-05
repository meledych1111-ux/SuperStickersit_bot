import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode='require', cursor_factory=RealDictCursor)

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS stickers (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    sticker_type TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    caption TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, file_id)
                )
            """)
            conn.commit()

def save_sticker(user, sticker_type: str, file_id: str, caption: str = ""):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO stickers (user_id, username, first_name, sticker_type, file_id, caption)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user.id, user.username or "", user.first_name or "", sticker_type, file_id, caption))
                conn.commit()
    except:
        pass
