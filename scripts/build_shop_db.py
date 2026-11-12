"""Build the sample shop database at data/shop.db and show what's inside.

    python scripts/build_shop_db.py            # build (refuses if it already exists)
    python scripts/build_shop_db.py --rebuild  # replace it safely (same seed -> same data)
"""

import sys

from agentbench.datasets import DEFAULT_DB_PATH, build_shop_db
from agentbench.tools import ReadOnlySQLite

if __name__ == "__main__":
    rebuild = "--rebuild" in sys.argv
    if DEFAULT_DB_PATH.exists() and not rebuild:
        print(f"{DEFAULT_DB_PATH} already exists (use --rebuild to replace it).")
    else:
        build_shop_db(DEFAULT_DB_PATH, overwrite=rebuild)
        print(f"Built {DEFAULT_DB_PATH}")

    with ReadOnlySQLite(DEFAULT_DB_PATH) as db:
        print("\nTables:", ", ".join(db.schema))
        for table in db.schema:
            print(f"  {table:12} {db.query(f'SELECT COUNT(*) FROM {table}').splitlines()[1]} rows")
        print("\nExample query - customers per city:")
        print(db.query("SELECT city, COUNT(*) AS customers FROM customers GROUP BY city ORDER BY customers DESC"))
        print("\nExample blocked query - DELETE FROM orders:")
        try:
            db.query("WITH x AS (SELECT 1) DELETE FROM orders")
        except Exception as exc:
            print(f"  {exc}")
