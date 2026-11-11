import duckdb 
import numpy 
import pandas as pd

con = duckdb.connect("ttc.duckdb")
# 1. what columns exist?
print(con.execute("DESCRIBE raw.subway_delays").fetchdf())

# 2. how many rows and what date range? (use the real date column)
print(con.execute("SELECT count(*) n, min(Date) first, max(Date) last FROM raw.subway_delays").fetchdf())

# 3. null rates and distinct counts for every column at once
print(con.execute("SELECT column_name, null_percentage, approx_unique FROM (SUMMARIZE raw.subway_delays)").fetchdf())

# 4. zero-minute rows, the 999 placeholder, and non-numeric delays
print(con.execute("""SELECT count(*) rows,
  sum(CASE WHEN try_cast("Min Delay" AS INT)=0 THEN 1 ELSE 0 END) zero_min,
  sum(CASE WHEN "Min Delay"='999' THEN 1 ELSE 0 END) v999,
  sum(CASE WHEN try_cast("Min Delay" AS INT) IS NULL THEN 1 ELSE 0 END) not_numeric
  FROM raw.subway_delays""").fetchdf())

# 5. station names that are spelled more than one way
print(con.execute("""SELECT upper(trim(Station)) station_clean, count(*) n, count(DISTINCT Station) spellings
  FROM raw.subway_delays GROUP BY 1 HAVING count(DISTINCT Station)>1 ORDER BY n DESC""").fetchdf())

# 6. most common delay codes
print(con.execute("SELECT Code, count(*) n FROM raw.subway_delays GROUP BY 1 ORDER BY n DESC LIMIT 20").fetchdf())