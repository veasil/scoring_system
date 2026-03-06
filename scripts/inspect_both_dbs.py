#!/usr/bin/env python3
import sqlite3

def db_info(path, label):
    print(f"=== {label} ===")
    try:
        conn = sqlite3.connect(path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in c.fetchall()]
        print(f"Tables: {tables}")
        for t in tables:
            c.execute(f"SELECT count(*) FROM [{t}]")
            cnt = c.fetchone()[0]
            print(f"  {t}: {cnt} rows")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
    print()

db_info("/home/admin/app/scoring_system/data/wqt.db", "Production DB")
db_info("/home/admin/app/wqt-staging/data/wqt.db", "Staging DB")
db_info("/home/admin/app/wqt-staging/data/cards.db", "Staging Cards DB")

# Check if production has cards.db
import os
prod_cards = "/home/admin/app/scoring_system/data/cards.db"
if os.path.exists(prod_cards):
    db_info(prod_cards, "Production Cards DB")
else:
    print("=== Production Cards DB ===")
    print("NOT FOUND")
