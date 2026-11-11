# Data profile: TTC Subway Delay Data

Profiled on 2026-11-09 from the files in `data/raw/`, loaded as all-text tables
`raw.subway_delays` and `raw.delay_codes`.

## Summary

| | |
|---|---|
| Delay rows | **47,915** |
| Date range | 2025-01-01 → 2026-09-30 (21 months, 1,400–2,700 rows/month) |
| Delay codes in lookup | 140 (all unique, none null) |
| Codes used in data | 142 distinct, **11 missing from the lookup** (1,892 rows, 3.9%) |
| Unparseable dates / times | 0 / 0 |
| Non-numeric `Min Delay` / `Min Gap` | 0 / 0 |

## Column by column

| Column | Nulls | Distinct | Notes |
|---|---|---|---|
| `_id` | 0% | 47,915 | Just 1…47,915, the row number in this file version. **Not a stable key**: it gets reassigned when the file is republished. |
| `Date` | 0% | 656 | Clean ISO dates. |
| `Time` | 0% | 1,435 | Clean `HH:MM`. |
| `Day` | 0% | 7 | **Wrong for 2026-04-26**: 63 rows say Saturday, but it was a Sunday. Recompute from `Date` instead. |
| `Station` | 0% | 1,265 | Free text, **cut off at 22 characters** (4,440 rows hit the limit). See *Stations* below. |
| `Code` | 0% | 142 | See *Codes*. |
| `Min Delay` | 0% | 138 | **65% are 0** (31,361 rows). p99 = 25 min, max = 900. No `999` placeholder in this extract. |
| `Min Gap` | 0% | 137 | 0 in 67% of rows. When Delay is 0, Gap is 0 too, except in 1 row. |
| `Bound` | **35%** | 5 | N/S/E/W plus `B` (63 rows, mostly on multi-line records; probably "both"). |
| `Line` | 0.4% | 39 | 98% are YU / BD / SHP. The rest is free text: `YU/BD`, `YU / BD`, `LINE 2 BLOOR-DANFORTH`, bus routes like `504 KING`, and one `999`. |
| `Vehicle` | 0% | 888 | **`0` in 18,993 rows (40%)** = no train recorded. One `999`, also a placeholder. |

## Findings that drive the dbt models

**1. Zero-minute delays are most of the data.** 65% of rows have `Min Delay = 0`.
They are real logged incidents (a disorderly patron, an alarm) that did not stop
service. They are kept and flagged with `is_zero_delay`. Counting incidents
includes them; measuring lost minutes leaves them out.

**2. Exact duplicates exist.** 66 pairs (132 rows) match on every column except
`_id`, for example two `MUSC` records at Kennedy, 2025-02-28 20:21, train 5290.
These could be double entry or two genuine events, and the data can't tell which.
They are flagged with `is_possible_duplicate`, not dropped.

**3. The codes file has an encoding bug.** It is double-encoded UTF-8, so an
en dash appears as `â` plus two invisible characters (`PAA â NO TROUBLE FOUND`),
and the curly quotes around "FORCE MAJEURE" are garbled the same way. This affects
35 of the 140 descriptions. `stg_delay_codes` swaps them back to `-` and `"`.

**4. 11 codes are missing from the lookup.**

| Code | Rows | Code | Rows |
|---|---|---|---|
| SUL | 1,305 | MUFL | 33 |
| MUINF | 229 | MUBIO | 21 |
| PUTO | 205 | XXXXX | 9 |
| MUSE | 45 | STAE, TFPD, TUAV | 1 each |
| PUFA | 42 | | |

Only `PUTO` ("T&S Other") is in the old 2022 code list. `XXXXX` looks like
"unknown". That's why the fact table uses a **left join**: an inner join would
drop 1,892 delays. The `relationships` test is set to `warn`, so the gap is
reported on every run without failing the build.

**5. Station is not clean enough to group on yet.** Upper/trim doesn't merge
anything, because the variation isn't capitalization. It's things like:
- direction or platform text: `KENNEDY BD STATION (PL…`, `UNION STATION TO ST AN…`
- whole-line entries: `YONGE-UNIVERSITY AND B` (540 rows), `LINE 2 BLOOR DANFORT…`
- typos: `APPRAOCHING`, `SHEPPARDSTATION`, `STR. CLAIR`
- yards and facilities: `GREENWOOD YARD`, `HILLCREST COMPLEX`

The top ~75 values cover most rows. A seed file mapping raw names to station
names would be the next step. For now `station_raw` is passed through as-is.

**6. Line can be grouped simply.** `line` maps YU/YUS→YU, BD, SHP, SRT, and
everything else (multi-line, bus routes, junk) to `OTHER` (645 rows). The
original is kept in `line_raw`.

## Top codes

By count (all rows): SUDP disorderly patron 5,366 · MUIS injured/ill customer in
station 4,568 · SUO security other 3,430 · MUPAA PAA no trouble found 2,518 ·
PUOPO train door monitoring 2,489.

By minutes lost (non-zero rows): SUDP 12,434 · MUIR 8,989 · SUUT unauthorized at
track level 6,734 · SUO 6,619 · MUI 6,058.

## dbt test results (first run)

```
PASS  unique / not_null   stg_delay_codes.delay_code
PASS  not_null            stg_subway_delays.delay_ts
PASS  not_null            fct_subway_delays.delay_ts
WARN  relationships       stg_subway_delays.delay_code -> stg_delay_codes  (1,892 rows)
```
