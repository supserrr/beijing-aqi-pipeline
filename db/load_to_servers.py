"""
load_to_servers.py — load the dataset into REAL MySQL + MongoDB servers.

Used by docker-compose (the `loader` service). Connects via environment
variables (defaults match the compose service names), creates/loads:
  * MySQL : stations, wind_directions, pollutant_readings, weather_readings
            (schema is created by sql/schema_mysql.sql at container init)
  * Mongo : air_quality collection (embedded docs) + indexes

Idempotent: truncates/drops existing rows so re-running reloads cleanly.
Set SAMPLE_MONTHS=N to load only the last N months (faster demo); 0 = all.
"""
from __future__ import annotations
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
from data_loader import load_raw, add_datetime
import preprocessing as pp
from build_databases import STATION_META, WD_LABELS, _f

MYSQL = dict(host=os.getenv("MYSQL_HOST", "localhost"),
             user=os.getenv("MYSQL_USER", "root"),
             password=os.getenv("MYSQL_PASSWORD", "beijing"),
             database=os.getenv("MYSQL_DB", "beijing_air"))
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "beijing_air")
BATCH = 20000


def frame():
    raw, source = load_raw()
    raw = add_datetime(raw)
    df = pp.impute(pp.clean(raw))
    months = int(os.getenv("SAMPLE_MONTHS", "0"))
    if months > 0:
        df = df[df["datetime"] >= df["datetime"].max() - pd.DateOffset(months=months)]
    df["ts"] = df["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df.reset_index(drop=True), source


def _chunked(cur, sql, rows):
    for i in range(0, len(rows), BATCH):
        cur.executemany(sql, rows[i:i + BATCH])


def load_mysql(df) -> int:
    import pymysql
    con = pymysql.connect(**MYSQL, autocommit=False)
    cur = con.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    for t in ("weather_readings", "pollutant_readings",
              "wind_directions", "stations"):
        cur.execute(f"TRUNCATE TABLE {t}")
    cur.execute("SET FOREIGN_KEY_CHECKS=1")

    stations = sorted(df["station"].unique())
    cur.executemany(
        "INSERT INTO stations(station_name,station_type,latitude,longitude)"
        " VALUES(%s,%s,%s,%s)",
        [(s, *STATION_META[s]) for s in stations])
    wds = sorted(df["wd"].dropna().unique())
    cur.executemany(
        "INSERT INTO wind_directions(wd_code,wd_label) VALUES(%s,%s)",
        [(c, WD_LABELS.get(c, c)) for c in wds])
    con.commit()

    cur.execute("SELECT station_id,station_name FROM stations")
    sid = {n: i for i, n in cur.fetchall()}
    cur.execute("SELECT wind_dir_id,wd_code FROM wind_directions")
    wid = {c: i for i, c in cur.fetchall()}

    poll = list(zip(df["station"].map(sid).tolist(), df["ts"].tolist(),
                    df["PM2.5"].tolist(), df["PM10"].tolist(),
                    df["SO2"].tolist(), df["NO2"].tolist(),
                    df["CO"].tolist(), df["O3"].tolist()))
    _chunked(cur, "INSERT INTO pollutant_readings"
                  "(station_id,ts,pm2_5,pm10,so2,no2,co,o3)"
                  " VALUES(%s,%s,%s,%s,%s,%s,%s,%s)", poll)
    wx = list(zip(df["station"].map(sid).tolist(), df["ts"].tolist(),
                  df["TEMP"].tolist(), df["PRES"].tolist(),
                  df["DEWP"].tolist(), df["RAIN"].tolist(),
                  df["WSPM"].tolist(), df["wd"].map(wid).tolist()))
    _chunked(cur, "INSERT INTO weather_readings"
                  "(station_id,ts,temp,pres,dewp,rain,wspm,wind_dir_id)"
                  " VALUES(%s,%s,%s,%s,%s,%s,%s,%s)", wx)
    con.commit()
    cur.execute("SELECT COUNT(*) FROM pollutant_readings")
    n = cur.fetchone()[0]
    con.close()
    return n


def load_mongo(df) -> int:
    import pymongo
    client = pymongo.MongoClient(MONGO_URI)
    col = client[MONGO_DB]["air_quality"]
    col.drop()
    docs = []
    total = 0
    for d in df.to_dict("records"):
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
        if len(docs) >= BATCH:
            col.insert_many(docs); total += len(docs); docs = []
    if docs:
        col.insert_many(docs); total += len(docs)
    col.create_index([("station", 1), ("timestamp", 1)])
    col.create_index([("timestamp", 1)])
    return total


def main():
    df, source = frame()
    print(f"[loader] data source: {source}; rows to load: {len(df):,}")
    n_sql = load_mysql(df)
    print(f"[loader] MySQL  : {n_sql:,} pollutant + weather rows loaded")
    n_mongo = load_mongo(df)
    print(f"[loader] MongoDB: {n_mongo:,} documents loaded")
    print("[loader] done.")


if __name__ == "__main__":
    main()
