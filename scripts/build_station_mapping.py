"""Draft seeds/station_mapping.csv: every raw Station value -> a canonical station.

Run from the project root after `dbt build` (reads stg_subway_delays):
    python scripts/build_station_mapping.py

This is a one-off DRAFTING helper, not part of the pipeline. The CSV it writes is
the thing you review and edit by hand (like a mapping spreadsheet). Re-running it
OVERWRITES the CSV, so once you've made manual edits, edit the CSV directly
instead of re-running this.

mapping_type:
  EXACT       "<station> STATION" or an obvious spelling of it
  VARIANT     station plus extra location text (platform, approaching, leaving...)
  BETWEEN     "A TO B" / "A - B": mapped to the FIRST station named (judgment call)
  LINE_LEVEL  a whole line, not one station -> no station
  FACILITY    yard, carhouse, office -> no station
  UNMAPPED    couldn't tell -> no station
"""
import csv
import re
import duckdb

# canonical name -> raw spellings (after normalise()). Longest alias wins, so
# "SHEPPARD WEST" beats "SHEPPARD" and "ST CLAIR WEST" beats "ST CLAIR".
ALIASES = {
    "Finch": ["FINCH"],
    "North York Centre": ["NORTH YORK CENTRE", "NORTH YORK CENTER", "NORTH YORK CTR", "NORTH YORK"],
    "Sheppard-Yonge": ["SHEPPARD YONGE", "SHEPPARD"],          # "Sheppard" = old name
    "York Mills": ["YORK MILLS"],
    "Lawrence": ["LAWRENCE"],
    "Eglinton": ["EGLINTON"],
    "Davisville": ["DAVISVILLE"],
    "St. Clair": ["ST CLAIR"],
    "Summerhill": ["SUMMERHILL"],
    "Rosedale": ["ROSEDALE"],
    "Bloor-Yonge": ["BLOOR YONGE", "YONGE BLOOR", "YONGE AND BLOOR", "BLOOR", "YONGE BD", "YONGE"],
    "Wellesley": ["WELLESLEY"],
    "College": ["COLLEGE"],
    "TMU": ["TMU", "DUNDAS", "YONGE DUNDAS"],                                   # renamed from Dundas
    "Queen": ["QUEEN"],
    "King": ["KING"],
    "Union": ["UNION"],
    "St. Andrew": ["ST ANDREW"],
    "Osgoode": ["OSGOODE"],
    "St. Patrick": ["ST PATRICK"],
    "Queen's Park": ["QUEENS PARK"],
    "Museum": ["MUSEUM"],
    "St. George": ["ST GEORGE"],
    "Spadina": ["SPADINA"],
    "Dupont": ["DUPONT"],
    "St. Clair West": ["ST CLAIR WEST", "ST CLAIR W"],
    "Cedarvale": ["CEDARVALE", "EGLINTON WEST"],                # renamed from Eglinton West
    "Glencairn": ["GLENCAIRN"],
    "Lawrence West": ["LAWRENCE WEST"],
    "Yorkdale": ["YORKDALE"],
    "Wilson": ["WILSON"],
    "Sheppard West": ["SHEPPARD WEST", "DOWNSVIEW"],             # "Downsview" = old name
    "Downsview Park": ["DOWNSVIEW PARK"],
    "Finch West": ["FINCH WEST"],
    "York University": ["YORK UNIVERSITY", "YORK U"],
    "Pioneer Village": ["PIONEER VILLAGE"],
    "Highway 407": ["HIGHWAY 407", "HWY 407"],
    "Vaughan Metropolitan Centre": ["VAUGHAN METROPOLITAN", "VAUGHAN MC", "VAUGHAN", "VMC"],
    "Kipling": ["KIPLING"],
    "Islington": ["ISLINGTON"],
    "Royal York": ["ROYAL YORK"],
    "Old Mill": ["OLD MILL"],
    "Jane": ["JANE"],
    "Runnymede": ["RUNNYMEDE"],
    "High Park": ["HIGH PARK"],
    "Keele": ["KEELE"],
    "Dundas West": ["DUNDAS WEST", "DUNDAS WES", "DUNDAS W"],   # raw text is cut at 22 chars
    "Lansdowne": ["LANSDOWNE"],
    "Dufferin": ["DUFFERIN"],
    "Ossington": ["OSSINGTON"],
    "Christie": ["CHRISTIE"],
    "Bathurst": ["BATHURST"],
    "Bay": ["BAY"],
    "Sherbourne": ["SHERBOURNE"],
    "Castle Frank": ["CASTLE FRANK"],
    "Broadview": ["BROADVIEW"],
    "Chester": ["CHESTER"],
    "Pape": ["PAPE"],
    "Donlands": ["DONLANDS"],
    "Greenwood": ["GREENWOOD"],
    "Coxwell": ["COXWELL"],
    "Woodbine": ["WOODBINE"],
    "Main Street": ["MAIN STREET", "MAIN"],
    "Victoria Park": ["VICTORIA PARK"],
    "Warden": ["WARDEN"],
    "Kennedy": ["KENNEDY"],
    "Bayview": ["BAYVIEW"],
    "Bessarion": ["BESSARION"],
    "Leslie": ["LESLIE"],
    "Don Mills": ["DON MILLS"],
}
RENAMED = {"DUNDAS": "renamed: Dundas -> TMU", "EGLINTON WEST": "renamed: Eglinton West -> Cedarvale",
           "SHEPPARD": "old name for Sheppard-Yonge", "DOWNSVIEW": "old name for Sheppard West"}

# station -> lines it serves (to decide the default line)
LINES = {}
for row in csv.DictReader(open("seeds/stations.csv")):
    LINES.setdefault(row["station_name"], []).append(row["line"])

ALIAS_LIST = sorted(((a, s) for s, al in ALIASES.items() for a in al), key=lambda x: -len(x[0]))

FACILITY = re.compile(r"YARD|CARHOUSE|HILLCREST|WYE|TRANSIT CONTROL|TORONTO TRANSIT|SUBSTATION|GATEHOUSE|BUILDING|OFFICE|SHOP")
LINE_LEVEL = re.compile(r"^(LINE|LIEN|YONGE AND UNI|SUBWAY|YONGE UNI|YONGE UNV|YONGE UNIV|BLOOR DANF|BLOOR DANFOTH|BLOOR DANFORTH|YUS |YU |BD |ALL |SYSTEM)")
TYPOS = {"APPRAOCHING": "APPROACHING", "STR CLAIR": "ST CLAIR", "SHEPPARDSTATION": "SHEPPARD STATION",
         "PLATFROM": "PLATFORM", " STN": " STATION"}
PREFIXES = re.compile(r"^(APPROACHING|LEAVING|ENTERING|EXITING|ARRIVING|E O|W O|N O|S O|B W|EA|WEST OF|EAST OF|NORTH OF|SOUTH OF)\s+")


def normalise(s):
    s = s.upper().replace(".", "").replace("'", "")
    s = re.sub(r"[-/:,]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for bad, good in TYPOS.items():
        s = s.replace(bad, good)
    return s


def find_station(text):
    """Longest alias at the start of text, ending on a word boundary."""
    for alias, station in ALIAS_LIST:
        if text == alias or re.match(re.escape(alias) + r"\b", text):
            return station, alias, text[len(alias):].strip()
    return None, None, text


def line_hint(rest, alias):
    toks = rest.split()
    if "BD" in toks[:2]:
        return "BD"
    if "YU" in toks[:2] or "YUS" in toks[:2]:
        return "YU"
    if alias == "BLOOR":   # "BLOOR STATION" is how operators write the Line 1 side
        return "YU"
    if alias in ("YONGE", "YONGE BD"):  # "YONGE (BD) STATION" is the Line 2 side
        return "BD"
    return None


# Hand decisions that rules can't make. raw_value -> (station, line, type, review, note)
OVERRIDES = {
    "QUEEN QUAY STATION": (None, None, "UNMAPPED", "N", "Queens Quay is a streetcar station, not subway"),
    "QUEEN ALBERT": (None, None, "UNMAPPED", "Y", "unclear location"),
    "QUEEN PARK STATION": ("Queen's Park", "YU", "VARIANT", "N", "missing apostrophe-s"),
    "YONGE 1": (None, None, "LINE_LEVEL", "N", "reads as Line 1 Yonge"),
    "LEASIDE STATION": (None, None, "UNMAPPED", "N", "Line 5 Eglinton station, not in subway master list"),
}


def classify(raw):
    if raw in OVERRIDES:
        return OVERRIDES[raw]
    n = normalise(raw)
    if FACILITY.search(n):
        return None, None, "FACILITY", "N", ""
    if re.search(r"\bEE\b", n):          # "MARKDALE EE" = emergency exit building
        return None, None, "FACILITY", "N", "emergency exit"
    if "SCARBOROUGH" in n:
        return None, None, "UNMAPPED", "N", "Line 3 Scarborough (closed 2023)"

    stripped = PREFIXES.sub("", n)
    had_prefix = stripped != n
    if LINE_LEVEL.match(n) or LINE_LEVEL.match(stripped):
        return None, None, "LINE_LEVEL", "N", ""
    station, alias, rest = find_station(stripped)
    if station is None:
        return None, None, "UNMAPPED", "Y", ""

    note = RENAMED.get(alias, "")
    lines = LINES[station]
    line = lines[0] if len(lines) == 1 else line_hint(rest, alias)  # None = use record's Line
    rest_clean = re.sub(r"^(BD|YUS|YU)\b", "", rest).strip()

    if not had_prefix and rest_clean in ("", "STATION"):
        return station, line, "EXACT", "N", note
    if re.search(r"(^|\s)(TO|TOWARDS|AND|&)\s", " " + rest_clean + " ") or (
            rest_clean.startswith("STATION ") and find_station(rest_clean[8:].strip())[0]):
        return station, line, "BETWEEN", "Y", ("; ".join(x for x in [note, "mapped to first station named"] if x))
    if had_prefix and n.startswith(("B W", "E O", "W O", "N O", "S O")):
        return station, line, "BETWEEN", "Y", "near/between stations; mapped to station named"
    return station, line, "VARIANT", "N", note


con = duckdb.connect("ttc.duckdb", read_only=True)
raw_counts = con.sql("""select station_raw, count(*) n from stg_subway_delays
                        group by 1 order by n desc, 1""").fetchall()

with open("seeds/station_mapping.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["raw_value", "station_name", "line", "mapping_type", "needs_review", "rows_affected", "notes"])
    for raw, n in raw_counts:
        st, ln, typ, rev, note = classify(raw)
        w.writerow([raw, st or "", ln or "", typ, rev, n, note])

print(f"wrote {len(raw_counts)} rows to seeds/station_mapping.csv")
