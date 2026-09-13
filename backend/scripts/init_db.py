"""Create the database schema in Neon. Usage: uv run python scripts/init_db.py"""

from app import db

if __name__ == "__main__":
    db.init_schema()
    print("schema ready")
