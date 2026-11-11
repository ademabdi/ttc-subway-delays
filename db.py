import pathlib
import duckdb

# Run from the project root:  python db.py
sql = pathlib.Path("scripts/load.sql").read_text()

con = duckdb.connect("ttc.duckdb")
con.execute(sql)

for t in ["raw.subway_delays", "raw.delay_codes"]:
    n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"{t}: {n} rows")

con.close()  # release the file lock so dbt can open ttc.duckdb
