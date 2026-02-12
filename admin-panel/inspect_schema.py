import pandas as pd
import os
import sys

# Add current directory to path to allow import
sys.path.append(os.path.dirname(__file__))

import db_utils

print("Initializing DB...")
# db_utils.init_db() is called on import

print("Inspecting Schema...")
tables_df = db_utils.get_all_tables()
if isinstance(tables_df, pd.DataFrame):
     tables = tables_df['name'].tolist()
     print("Tables:", tables)

     if 'system_settings' in tables:
         print("\n--- Schema for system_settings ---")
         # We can't use db_utils.run_query for PRAGMA easily if it expects SELECT usually?
         # db_utils.run_query uses read_sql_query which supports any SQL that returns rows.
         schema = db_utils.run_query("PRAGMA table_info(system_settings)")
         print(schema)
     else:
         print("ERROR: system_settings table NOT found!")
else:
    print("Error getting tables:", tables_df)
