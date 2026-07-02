"""
build_databases.py  —  Task 2 executor
=======================================
Builds BOTH databases from the loaded Beijing data and runs the demonstration
queries, capturing real results:

  * SQL  : a SQLite mirror of the MySQL schema in sql/schema_mysql.sql
           (identical ANSI-SQL semantics; AUTO_INCREMENT/ENGINE stripped).
           Full dataset loaded. Results -> outputs/tables/sql_query_results.md
  * NoSQL: an in-memory MongoDB via `mongomock` (real pymongo API).
           A recent-window subset is loaded for the in-memory demo (the design
           and queries are scale-independent).
           Results -> outputs/tables/mongo_query_results.md
           Sample docs -> mongo/sample_documents.json

Run:  python db/build_databases.py
"""
from __future__ import annotations
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))
from data_loader import load_raw, add_datetime
import preprocessing as pp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(ROOT, "db")
TAB = os.path.join(ROOT, "outputs", "tables")
MONGO_DIR = os.path.join(ROOT, "mongo")
for d in (DB_DIR, TAB, MONGO_DIR):
    os.makedirs(d, exist_ok=True)
SQLITE_PATH = os.path.join(DB_DIR, "beijing.db")
# Build on sandbox-local disk (SQLite journaling fails on mounted folders), in a
# unique per-run temp dir so a stale file from an earlier run can never block it.
LOCAL_DB = os.path.join(tempfile.mkdtemp(prefix="beijing_build_"), "beijing.db")

# Approximate real coordinates + type for the 12 monitoring stations
STATION_META = {
    "Aotizhongxin":  ("urban",      39.982, 116.397),
    "Changping":     ("suburban",   40.217, 116.230),
    "Dingling":      ("background", 40.292, 116.220),
    "Dongsi":        ("urban",      39.929, 116.417),
    "Guanyuan":      ("urban",      39.929, 116.339),
    "Gucheng":       ("urban",      39.911, 116.184),
    "Huairou":       ("suburban",   40.328, 116.628),
    "Nongzhanguan":  ("urban",      39.937, 116.461),
    "Shunyi":        ("suburban",   40.127, 116.655),
    "Tiantan":       ("urban",      39.886, 116.407),
    "Wanliu":        ("urban",      39.987, 116.287),
    "Wanshouxigong": ("urban",      39.878, 116.352),
}
WD_LABELS = {
    "N": "North", "NNE": "North-Northeast", "NE": "Northeast",
    "ENE": "East-Northeast", "E": "East", "ESE": "East-Southeast",
    "SE": "Southeast", "SSE": "South-Southeast", "S": "South",
    "SSW": "South-Southwest", "SW": "Southwest", "WSW": "West-Southwest",
    "W": "West", "WNW": "West-Northwest", "NW": "Northwest",
    "NNW": "North-Northwest",
}

SQLITE_DDL = """
PRAGMA foreign_keys = ON;
DROP TABLE IF EXISTS weather_readings;
DROP TABLE IF EXISTS pollutant_readings;
DROP TABLE IF EXISTS wind_directions;
DROP TABLE IF EXISTS stations;

CREATE TABLE stations (
    station_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    station_name TEXT NOT NULL UNIQUE,
    station_type TEXT CHECK(station_type IN ('urban','suburban','background')),
    latitude     REAL,
    longitude    REAL
);
CREATE TABLE wind_directions (
    wind_dir_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    wd_code      TEXT NOT NULL UNIQUE,
    wd_label     TEXT
);
CREATE TABLE pollutant_readings (
    reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL REFERENCES stations(station_id),
    ts         TEXT NOT NULL,
    pm2_5 REAL, pm10 REAL, so2 REAL, no2 REAL, co REAL, o3 REAL,
    UNIQUE(station_id, ts)
);
CREATE TABLE weather_readings (
    reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL REFERENCES stations(station_id),
    ts         TEXT NOT NULL,
    temp REAL, pres REAL, dewp REAL, rain REAL, wspm REAL,
    wind_dir_id INTEGER REFERENCES wind_directions(wind_dir_id),
    UNIQUE(station_id, ts)
);
CREATE INDEX ix_poll_station_ts ON pollutant_readings(station_id, ts);
CREATE INDEX ix_wx_station_ts   ON weather_readings(station_id, ts);
"""

# SQLite-dialect versions of sql/queries_mysql.sql (strftime instead of
# DATE_FORMAT/MONTH); semantics identical.
SQL_QUERIES = {
"Q1 — latest record per station": """
SELECT s.station_name, p.ts, p.pm2_5, p.pm10, p.no2, p.co
FROM pollutant_readings p JOIN stations s ON s.station_id=p.station_id
WHERE p.ts = (SELECT MAX(p2.ts) FROM pollutant_readings p2
              WHERE p2.station_id=p.station_id)
ORDER BY s.station_name;""",
"Q2 — records by date range (Aotizhongxin, 2016-01-01 00:00..06:00)": """
SELECT p.ts, p.pm2_5, p.pm10, w.temp, w.wspm, wd.wd_code
FROM pollutant_readings p
JOIN stations s ON s.station_id=p.station_id
JOIN weather_readings w ON w.station_id=p.station_id AND w.ts=p.ts
LEFT JOIN wind_directions wd ON wd.wind_dir_id=w.wind_dir_id
WHERE s.station_name='Aotizhongxin'
  AND p.ts BETWEEN '2016-01-01 00:00:00' AND '2016-01-01 06:00:00'
ORDER BY p.ts;""",
"Q3 — monthly average PM2.5 (Aotizhongxin, first 12 months)": """
SELECT s.station_name, strftime('%Y-%m', p.ts) AS month,
       ROUND(AVG(p.pm2_5),1) AS avg_pm25, COUNT(*) AS n_hours
FROM pollutant_readings p JOIN stations s ON s.station_id=p.station_id
WHERE s.station_name='Aotizhongxin'
GROUP BY month ORDER BY month LIMIT 12;""",
"Q4 — top-10 most polluted hours (joins both facts + dims)": """
SELECT s.station_name, p.ts, p.pm2_5, w.wspm, wd.wd_code
FROM pollutant_readings p
JOIN stations s ON s.station_id=p.station_id
JOIN weather_readings w ON w.station_id=p.station_id AND w.ts=p.ts
LEFT JOIN wind_directions wd ON wd.wind_dir_id=w.wind_dir_id
ORDER BY p.pm2_5 DESC LIMIT 10;""",
"Q5 — mean PM2.5 by station_type x heating season": """
SELECT s.station_type,
       CASE WHEN CAST(strftime('%m',p.ts) AS INT) IN (11,12,1,2,3)
            THEN 'heating' ELSE 'non-heating' END AS season_kind,
       ROUND(AVG(p.pm2_5),1) AS avg_pm25
FROM pollutant_readings p JOIN stations s ON s.station_id=p.station_id
GROUP BY s.station_type, season_kind
ORDER BY s.station_type, season_kind;""",
}


def load_frame():
    raw, source = load_raw()
    raw = add_datetime(raw)
    df = pp.impute(pp.clean(raw))
    df["ts"] = df["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df, source


def build_sqlite(df: pd.DataFrame) -> sqlite3.Connection:
    if os.path.exists(LOCAL_DB):
        try:
            os.remove(LOCAL_DB)
        except OSError:
            pass  # not fatal: the temp dir above is unique to this run
    con = sqlite3.connect(LOCAL_DB)
    con.executescript(SQLITE_DDL)
    # dimensions
    stations = sorted(df["station"].unique())
    con.executemany(
        "INSERT INTO stations(station_name,station_type,latitude,longitude)"
        " VALUES (?,?,?,?)",
        [(s, *STATION_META.get(s, ("urban", None, None))) for s in stations])
    wd_codes = sorted(df["wd"].dropna().unique())
    con.executemany(
        "INSERT INTO wind_directions(wd_code,wd_label) VALUES (?,?)",
        [(c, WD_LABELS.get(c, c)) for c in wd_codes])
    con.commit()
    sid = {r[1]: r[0] for r in con.execute(
        "SELECT station_id,station_name FROM stations")}
    wid = {r[1]: r[0] for r in con.execute(
        "SELECT wind_dir_id,wd_code FROM wind_directions")}
    # facts — build column-wise (avoid itertuples renaming of 'PM2.5')
    poll = list(zip(df["station"].map(sid), df["ts"], df["PM2.5"], df["PM10"],
                    df["SO2"], df["NO2"], df["CO"], df["O3"]))
    con.executemany(
        "INSERT INTO pollutant_readings"
        "(station_id,ts,pm2_5,pm10,so2,no2,co,o3) VALUES (?,?,?,?,?,?,?,?)",
        poll)
    wx = list(zip(df["station"].map(sid), df["ts"], df["TEMP"], df["PRES"],
                  df["DEWP"], df["RAIN"], df["WSPM"], df["wd"].map(wid)))
    con.executemany(
        "INSERT INTO weather_readings"
        "(station_id,ts,temp,pres,dewp,rain,wspm,wind_dir_id)"
        " VALUES (?,?,?,?,?,?,?,?)", wx)
    con.commit()
    return con


def run_sql(con, source) -> None:
    lines = [f"# Task 2 — SQL query results (engine: SQLite mirror of MySQL "
             f"schema; data source: {source})\n"]
    n = con.execute("SELECT COUNT(*) FROM pollutant_readings").fetchone()[0]
    lines.append(f"_Loaded {n:,} pollutant rows + matching weather rows across "
                 f"{con.execute('SELECT COUNT(*) FROM stations').fetchone()[0]}"
                 f" stations._\n")
    for title, q in SQL_QUERIES.items():
        cur = con.execute(q)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=cols)
        lines.append(f"\n## {title}\n\n```sql{q}\n```\n")
        lines.append(df.to_markdown(index=False))
        lines.append("")
    with open(os.path.join(TAB, "sql_query_results.md"), "w") as f:
        f.write("\n".join(lines))
    print(f"[SQL] {n:,} rows loaded; 5 queries -> sql_query_results.md")


def build_mongo(df: pd.DataFrame, months_window: int = 4):
    import mongomock
    client = mongomock.MongoClient()
    coll = client["beijing_air"]["air_quality"]
    # recent-window subset for the in-memory demo
    cutoff = df["datetime"].max() - pd.DateOffset(months=months_window)
    sub = df[df["datetime"] >= cutoff]
    docs = []
    for d in sub.to_dict("records"):                 # explicit column keys
        stype, lat, lon = STATION_META.get(d["station"], ("urban", None, None))
        dt = d["datetime"]
        docs.append({
            "station": d["station"], "station_type": stype,
            "location": {"lat": lat, "lon": lon},
            "timestamp": dt.to_pydatetime(),
            "time": {"year": int(dt.year), "month": int(dt.month),
                     "day": int(dt.day), "hour": int(dt.hour),
                     "is_heating_season": int(dt.month in (11, 12, 1, 2, 3))},
            "pollutants": {"pm2_5": _f(d["PM2.5"]), "pm10": _f(d["PM10"]),
                           "so2": _f(d["SO2"]), "no2": _f(d["NO2"]),
                           "co": _f(d["CO"]), "o3": _f(d["O3"])},
            "weather": {"temp": _f(d["TEMP"]), "pres": _f(d["PRES"]),
                        "dewp": _f(d["DEWP"]), "rain": _f(d["RAIN"]),
                        "wind_dir": d["wd"], "wspm": _f(d["WSPM"])},
        })
    coll.insert_many(docs)
    coll.create_index([("station", 1), ("timestamp", 1)])
    coll.create_index([("timestamp", 1)])
    return coll, len(docs)


def _f(v):
    try:
        import math
        v = float(v)
        return None if math.isnan(v) else round(v, 1)
    except Exception:
        return None


def run_mongo(df) -> None:
    coll, n = build_mongo(df)
    out = ["# Task 2 — MongoDB query results (engine: mongomock, real pymongo "
           "API)\n", f"_In-memory demo collection `beijing_air.air_quality` "
           f"with {n:,} documents (recent 4-month window)._\n"]

    # M1 — latest document for a station (required "latest record")
    q1 = list(coll.find({"station": "Aotizhongxin"},
                        {"_id": 0, "station": 1, "timestamp": 1,
                         "pollutants.pm2_5": 1, "weather.wspm": 1})
              .sort("timestamp", -1).limit(1))
    out += ["\n## M1 — latest record for a station\n",
            "```js\ndb.air_quality.find({station:'Aotizhongxin'})"
            ".sort({timestamp:-1}).limit(1)\n```\n",
            "```json\n" + json.dumps(q1, default=str, indent=2) + "\n```"]

    # M2 — records by date range (required "date range")
    lo = datetime(2017, 2, 1); hi = datetime(2017, 2, 1, 6)
    q2 = list(coll.find(
        {"station": "Aotizhongxin",
         "timestamp": {"$gte": lo, "$lte": hi}},
        {"_id": 0, "timestamp": 1, "pollutants.pm2_5": 1,
         "weather.temp": 1, "weather.wind_dir": 1}).sort("timestamp", 1))
    out += ["\n## M2 — records by date range (2017-02-01 00:00..06:00)\n",
            "```js\ndb.air_quality.find({station:'Aotizhongxin',"
            "timestamp:{$gte:ISODate('2017-02-01'),$lte:ISODate('2017-02-01T06:00')}})"
            ".sort({timestamp:1})\n```\n",
            "```json\n" + json.dumps(q2, default=str, indent=2) + "\n```"]

    # M3 — aggregation: avg PM2.5 by station (sorted worst-first)
    q3 = list(coll.aggregate([
        {"$group": {"_id": "$station",
                    "avg_pm25": {"$avg": "$pollutants.pm2_5"},
                    "hours": {"$sum": 1}}},
        {"$sort": {"avg_pm25": -1}}]))
    out += ["\n## M3 — aggregation: average PM2.5 by station\n",
            "```js\ndb.air_quality.aggregate([{$group:{_id:'$station',"
            "avg_pm25:{$avg:'$pollutants.pm2_5'},hours:{$sum:1}}},"
            "{$sort:{avg_pm25:-1}}])\n```\n",
            "```json\n" + json.dumps(
                [{"station": d["_id"], "avg_pm25": round(d["avg_pm25"], 1),
                  "hours": d["hours"]} for d in q3], indent=2) + "\n```"]

    # M4 — count of hazardous hours (PM2.5 > 250) per station type
    q4 = list(coll.aggregate([
        {"$match": {"pollutants.pm2_5": {"$gt": 250}}},
        {"$group": {"_id": "$station_type", "hazardous_hours": {"$sum": 1}}},
        {"$sort": {"hazardous_hours": -1}}]))
    out += ["\n## M4 — hazardous hours (PM2.5 > 250) by station type\n",
            "```js\ndb.air_quality.aggregate([{$match:{'pollutants.pm2_5':"
            "{$gt:250}}},{$group:{_id:'$station_type',"
            "hazardous_hours:{$sum:1}}},{$sort:{hazardous_hours:-1}}])\n```\n",
            "```json\n" + json.dumps(
                [{"station_type": d["_id"],
                  "hazardous_hours": d["hazardous_hours"]} for d in q4],
                indent=2) + "\n```"]

    with open(os.path.join(TAB, "mongo_query_results.md"), "w") as f:
        f.write("\n".join(out))
    # sample documents export
    sample = list(coll.find({}, {"_id": 0}).limit(2))
    with open(os.path.join(MONGO_DIR, "sample_documents.json"), "w") as f:
        json.dump(sample, f, default=str, indent=2)
    print(f"[Mongo] {n:,} docs; 4 queries -> mongo_query_results.md; "
          f"samples -> mongo/sample_documents.json")


def main():
    import shutil
    df, source = load_frame()
    con = build_sqlite(df)
    run_sql(con, source)
    con.close()
    shutil.copy(LOCAL_DB, SQLITE_PATH)               # persist into the repo
    run_mongo(df)
    print("Task 2 databases built successfully.")


if __name__ == "__main__":
    main()
