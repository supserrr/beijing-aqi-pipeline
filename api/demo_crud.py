"""
demo_crud.py  —  Task 3 offline demonstration
==============================================
Exercises EVERY endpoint's logic (POST/GET/PUT/DELETE + latest + date-range)
for BOTH databases, without needing a web server — by calling the same
repository layer that FastAPI uses (api/repositories.py) against a SQLite mirror
and a mongomock collection.

Captures realistic request -> response examples to
outputs/tables/api_crud_demo.md. Proves the CRUD logic is correct end to end.
"""
from __future__ import annotations
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "db"))
sys.path.insert(0, HERE)

from data_loader import load_raw, add_datetime
import preprocessing as pp
from build_databases import SQLITE_DDL, STATION_META, WD_LABELS, _f
from repositories import (SQLReadingRepository, MongoReadingRepository,
                          NotFound, Conflict)

TAB = os.path.join(ROOT, "outputs", "tables")
os.makedirs(TAB, exist_ok=True)
# Unique, current-user-owned temp DB per run, so a stale file left by an
# earlier run (or another user in a shared sandbox) can never block the demo.
LOCAL_DB = os.path.join(tempfile.mkdtemp(prefix="api_demo_"), "api_demo.db")
STATION = "Aotizhongxin"
LOG: list[str] = []


def step(title, request, response):
    LOG.append(f"\n### {title}\n")
    if request is not None:
        LOG.append("**request**\n\n```json\n"
                   + json.dumps(request, default=str, indent=2) + "\n```\n")
    LOG.append("**response**\n\n```json\n"
               + json.dumps(response, default=str, indent=2) + "\n```")
    print(f"  {title} -> ok")


def build_backends():
    """Small real-schema backend (3 stations, 7-day window) for the demo."""
    raw, source = load_raw()
    raw = add_datetime(raw)
    df = pp.impute(pp.clean(raw))
    stations = ["Aotizhongxin", "Huairou", "Dingling"]
    hi = df["datetime"].max()
    lo = hi - pd.Timedelta(days=7)
    df = df[(df["station"].isin(stations)) & (df["datetime"] >= lo)].copy()
    df["ts"] = df["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")

    # --- SQLite ---
    if os.path.exists(LOCAL_DB):
        try:
            os.remove(LOCAL_DB)
        except OSError:
            pass  # not fatal: the temp dir above is unique to this run
    con = sqlite3.connect(LOCAL_DB)
    con.executescript(SQLITE_DDL)
    con.executemany(
        "INSERT INTO stations(station_name,station_type,latitude,longitude)"
        " VALUES (?,?,?,?)",
        [(s, *STATION_META[s]) for s in stations])
    wd = sorted(df["wd"].dropna().unique())
    con.executemany("INSERT INTO wind_directions(wd_code,wd_label) VALUES (?,?)",
                    [(c, WD_LABELS.get(c, c)) for c in wd])
    sid = {r[1]: r[0] for r in con.execute(
        "SELECT station_id,station_name FROM stations")}
    con.executemany(
        "INSERT INTO pollutant_readings(station_id,ts,pm2_5,pm10,so2,no2,co,o3)"
        " VALUES (?,?,?,?,?,?,?,?)",
        list(zip(df["station"].map(sid), df["ts"], df["PM2.5"], df["PM10"],
                 df["SO2"], df["NO2"], df["CO"], df["O3"])))
    con.commit()

    # --- mongomock ---
    import mongomock
    col = mongomock.MongoClient()["beijing_air"]["air_quality"]
    docs = []
    for d in df.to_dict("records"):
        stype, lat, lon = STATION_META[d["station"]]
        dt = d["datetime"]
        docs.append({"station": d["station"], "station_type": stype,
                     "location": {"lat": lat, "lon": lon},
                     "timestamp": dt.to_pydatetime(),
                     "pollutants": {"pm2_5": _f(d["PM2.5"]), "pm10": _f(d["PM10"]),
                                    "so2": _f(d["SO2"]), "no2": _f(d["NO2"]),
                                    "co": _f(d["CO"]), "o3": _f(d["O3"])},
                     "weather": {"temp": _f(d["TEMP"]), "wind_dir": d["wd"],
                                 "wspm": _f(d["WSPM"])}})
    col.insert_many(docs)
    col.create_index([("station", 1), ("timestamp", 1)])
    return con, col, source, df


def demo_sql(repo: SQLReadingRepository):
    LOG.append("\n## SQL backend (MySQL schema / SQLite mirror)\n")
    new_ts = "2017-03-01 00:00:00"
    body = {"pm2_5": 123, "pm10": 180, "so2": 12, "no2": 64, "co": 900, "o3": 30}
    step("POST /sql/readings  (CREATE)",
         {"station": STATION, "ts": new_ts, **body},
         repo.create(STATION, new_ts, body))
    step(f"GET /sql/readings/{STATION}/item/{new_ts}  (READ one)",
         None, repo.get(STATION, new_ts))
    step(f"GET /sql/readings/{STATION}/latest  (READ latest — required)",
         None, repo.latest(STATION))
    rng = repo.range(STATION, "2017-02-28 18:00:00", "2017-02-28 23:00:00")
    step(f"GET /sql/readings/{STATION}/range  (READ date range — required)",
         {"start": "2017-02-28 18:00:00", "end": "2017-02-28 23:00:00",
          "returned": len(rng)}, rng)
    step(f"PUT /sql/readings/{STATION}/item/{new_ts}  (UPDATE)",
         {"pm2_5": 999}, repo.update(STATION, new_ts, {"pm2_5": 999}))
    step(f"DELETE /sql/readings/{STATION}/item/{new_ts}  (DELETE)",
         None, repo.delete(STATION, new_ts))
    try:
        repo.get(STATION, new_ts)
    except NotFound as e:
        step("GET deleted record -> 404", None, {"status": 404, "detail": str(e)})


def demo_mongo(repo: MongoReadingRepository):
    LOG.append("\n## MongoDB backend (pymongo / mongomock)\n")
    new_ts = datetime(2017, 3, 1, 0, 0, 0)
    doc = {"station": STATION, "timestamp": new_ts, "station_type": "urban",
           "location": {"lat": 39.982, "lon": 116.397},
           "pollutants": {"pm2_5": 123, "pm10": 180, "co": 900},
           "weather": {"temp": 2.0, "wind_dir": "NW", "wspm": 3.1}}
    step("POST /mongo/readings  (CREATE)", doc, repo.create(doc))
    step(f"GET /mongo/readings/{STATION}/item/{new_ts}  (READ one)",
         None, repo.get(STATION, new_ts))
    step(f"GET /mongo/readings/{STATION}/latest  (READ latest — required)",
         None, repo.latest(STATION))
    rng = repo.range(STATION, datetime(2017, 2, 28, 18), datetime(2017, 2, 28, 23))
    step(f"GET /mongo/readings/{STATION}/range  (READ date range — required)",
         {"start": "2017-02-28T18:00", "end": "2017-02-28T23:00",
          "returned": len(rng)}, rng[:3] + (["..."] if len(rng) > 3 else []))
    step(f"PUT /mongo/readings/{STATION}/item  (UPDATE)",
         {"pollutants.pm2_5": 999},
         repo.update(STATION, new_ts, {"pollutants.pm2_5": 999}))
    step(f"DELETE /mongo/readings/{STATION}/item  (DELETE)",
         None, repo.delete(STATION, new_ts))
    try:
        repo.get(STATION, new_ts)
    except NotFound as e:
        step("GET deleted record -> 404", None, {"status": 404, "detail": str(e)})


def main():
    con, col, source, df = build_backends()
    LOG.append(f"# Task 3 — CRUD + time-series endpoint demonstration\n")
    LOG.append(f"_Data source: {source}. Backends: SQLite mirror of the MySQL "
               f"schema + mongomock (real pymongo API). Each step calls the same "
               f"repository the FastAPI routes use._\n")
    demo_sql(SQLReadingRepository(con, ph="?"))
    demo_mongo(MongoReadingRepository(col))
    con.close()
    with open(os.path.join(TAB, "api_crud_demo.md"), "w") as f:
        f.write("\n".join(LOG))
    print(f"\nCRUD demo (both DBs) -> {os.path.join(TAB, 'api_crud_demo.md')}")


if __name__ == "__main__":
    main()
