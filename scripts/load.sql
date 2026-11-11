-- Raw layer: copy the CSVs into DuckDB exactly as they are.
-- all_varchar = true means every column is text. We do NOT clean or cast here;
-- that is dbt's job (staging models). If the source changes shape, the raw
-- load still succeeds and the problem shows up in dbt, where we can test it.

CREATE SCHEMA IF NOT EXISTS raw;

CREATE OR REPLACE TABLE raw.subway_delays AS
SELECT *
FROM read_csv('data/raw/TTC_Subway_Delay_Data_since_2025.csv',
              header = true, all_varchar = true);

CREATE OR REPLACE TABLE raw.delay_codes AS
SELECT *
FROM read_csv('data/raw/Code_Descriptions.csv',
              header = true, all_varchar = true);
