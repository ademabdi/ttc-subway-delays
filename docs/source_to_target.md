# Source-to-target mapping

How each column in the source files becomes a column in the dbt models.
Logic lives in `models/staging/stg_subway_delays.sql` and `models/staging/stg_delay_codes.sql`;
the reasoning behind each choice is in [decisions.md](decisions.md).

## Delays: `TTC_Subway_Delay_Data_since_2025.csv` → `stg_subway_delays`

| # | Source column | Target column | Rule |
|---|---|---|---|
| 1 | `_id` | `source_row_id` | Cast to integer. Kept for tracing only: it's the row number in the current file and changes when the file is republished, so it is not a key |
| 2 | `Date` | `delay_date` | Cast text to date |
| 3 | `Date` + `Time` | `delay_ts` | Combined into one timestamp (`YYYY-MM-DD HH:MM`) |
| 4 | `Day` | — | Not used. `day_of_week` is recomputed from `Date` because the source is wrong for 2026-04-26 (63 rows) |
| 5 | `Station` | `station_raw` | Trimmed and upper-cased; kept as free text |
| 6 | `Code` | `delay_code` | Trimmed and upper-cased so it matches the code list |
| 7 | `Min Delay` | `min_delay` | Cast to integer (minutes of delay) |
| 8 | `Min Gap` | `min_gap` | Cast to integer (minutes between trains) |
| 9 | `Bound` | `bound` | Trimmed and upper-cased; blank → null |
| 10 | `Line` | `line_raw` | Trimmed and upper-cased; original text kept |
| 11 | `Vehicle` | `vehicle_number` | `0` and `999` → null (placeholders, not train numbers); otherwise cast to integer |

## Derived columns

New columns with no single source column.

| Target column | Derived from | Rule |
|---|---|---|
| `day_of_week` | `Date` | Weekday name computed from the date |
| `line` | `Line` | YU / YUS → YU; BD; SHP; SRT; anything else (multi-line, bus routes, junk) → OTHER; blank → null |
| `station_name` | `Station` | Looked up in `seeds/station_mapping.csv`; null for line-level, facility and unmapped values |
| `station_line` | `Station` + `Line` | The record's line if that station serves it, otherwise the line implied by the station name (e.g. "ST GEORGE BD" → BD) |
| `station_mapping_type` | `Station` | How the station was mapped: EXACT, VARIANT, BETWEEN, LINE_LEVEL, FACILITY, UNMAPPED |
| `is_zero_delay` | `Min Delay` | True when the delay is 0 minutes (logged incident that didn't stop service) |
| `is_possible_duplicate` | all columns except `_id` | True when another row matches on every column; flagged, not removed |

## Delay codes: `Code_Descriptions.csv` → `stg_delay_codes`

| # | Source column | Target column | Rule |
|---|---|---|---|
| 1 | `_id` | — | Not used |
| 2 | `CODE` | `delay_code` | Trimmed and upper-cased; the join key to delays |
| 3 | `DESCRIPTION` | `delay_description` | Trimmed; double-encoded dashes and curly quotes repaired to `-` and `"` |

## Join

`fct_subway_delays` = `stg_subway_delays` **left join** `stg_delay_codes` on `delay_code`.
Left join so the 1,892 delays whose code is missing from TTC's list are kept (with a null description).
