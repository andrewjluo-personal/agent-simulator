"""Initialize the database and refresh paper-backed scenario libraries."""

from app import db
from app.samples import SAMPLE_SCENARIOS

if __name__ == "__main__":
    db.init_schema()
    store = db.PgStore()
    count = 0
    for scenario in SAMPLE_SCENARIOS:
        if scenario.source.kind == "paper":
            store.upsert_scenario(scenario)
            count += 1
    print(f"schema ready; upserted {count} paper scenarios")
