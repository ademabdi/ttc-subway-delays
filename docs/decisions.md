# Decision log

One entry per judgment call: what was decided, why, and what it costs.

| # | Decision | Why | Trade-off / revisit when |
|---|---|---|---|
| 1 | Load raw CSVs as all-text (`all_varchar`) and clean in dbt | Raw load never fails on a format change; problems surface as dbt test failures where they can be seen | None significant |
| 2 | `_id` is not used as a key | It's the row number of the current file version and changes on republish | Need a real key if we ever load incrementally |
| 3 | Flag zero-minute delays (`is_zero_delay`), don't drop them | 65% of rows; they're real incidents that didn't stop service | Incident counts include them, minutes-lost analysis excludes them |
| 4 | Flag exact duplicates (`is_possible_duplicate`), don't drop them | 66 pairs; can't tell double entry from two real events | Revisit if TTC documents how records are entered |
| 5 | LEFT join delays to codes | 11 codes (1,892 rows) missing from TTC's lookup; inner join would silently lose 4% of delays | Relationships test warns on every run as a reminder |
| 6 | Recompute weekday from `Date` | Source `Day` is wrong for 2026-04-26 (63 rows) | None |
| 7 | `Vehicle` 0 and 999 -> null | Placeholders, not train numbers | None |
| 8 | Station names mapped through a reviewed seed (`seeds/station_mapping.csv`), not regex in SQL | The mapping is a business decision that needs review, like a mapping spreadsheet; a seed keeps it readable and version-controlled | New spellings in future refreshes need adding (test warns) |
| 9 | Canonical names use current station names: TMU (was Dundas), Cedarvale (was Eglinton West) | Data contains both old and new names | Ridership tables using old names need the same mapping |
| 10 | Station grain is station + line | Interchanges (Bloor-Yonge, St. George, Spadina, Sheppard-Yonge) have separate ridership per line | — |
| 11 | Interchange line = record's `Line` if that station serves it, else the line implied by the raw name | Operators write "BLOOR STATION" for the Line 1 side and "YONGE BD STATION" for Line 2, but the `Line` column is more direct | 6 rows end up with no line |
| 12 | "A TO B" locations mapped to the first station named, tagged `BETWEEN` | A delay between two stations has to be counted somewhere; the first station named is a simple, consistent rule | Decided: attributed to the first station named, unless the record states otherwise. Affects 0.9% of rows |
| 13 | Line-level, facility and unmapped rows get no station | Forcing them into a station would distort per-station numbers | ~4.3% of rows excluded from per-station analysis |
| 14 | Ridership = TTC "Subway Ridership 2023-2024" PDF, extracted into `seeds/station_ridership.csv` | Latest per-station figures published; 2025-26 TTC stats are system-level only | Assumes each station's share of riders is stable; scale by system growth for absolute rates |
| 15 | Ridership measure is **station usage** (entries + exits), not boardings | That's what the table reports per station; verified: each line's station usage sums to exactly 2.0x its boardings | Rates are "per 100k station users"; halve usage for an approximate per-boarding figure |
| 16 | Rate mart uses weekdays only; BETWEEN rows are included, attributed per #12 | Ridership is a typical weekday | Weekend reliability not covered by this view |
| 17 | Per-rider rates are read as "how often things go wrong here relative to local use", **not** passenger impact | A delay at a small station (e.g. Rosedale) also delays everyone riding through it, so per-station-user rates overstate small stations | Small stations rank high partly from a small denominator; pair with raw minutes, and consider median delay for outliers |
