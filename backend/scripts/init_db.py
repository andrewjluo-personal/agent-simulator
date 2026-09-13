"""Create the database schema in Neon and seed sample scenarios.
Usage: .venv/bin/python scripts/init_db.py
"""

from app import db
from app.samples import ensure_samples

if __name__ == "__main__":
    db.init_schema()
    print(f"schema ready; seeded {ensure_samples(db.PgStore())} sample scenarios")
