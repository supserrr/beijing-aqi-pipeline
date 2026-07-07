"""
main.py  —  Task 3 FastAPI service (canonical deliverable)
==========================================================
CRUD (POST/GET/PUT/DELETE) + time-series query endpoints (latest record,
records by date range) for BOTH databases:

    /sql/...    -> MySQL   (via PyMySQL, DB-API placeholder '%s')
    /mongo/...  -> MongoDB (via pymongo)

Run locally:
    pip install fastapi uvicorn pymysql pymongo
    export MYSQL_HOST=localhost MYSQL_USER=root MYSQL_PASSWORD=... \
           MYSQL_DB=beijing_air MONGO_URI=mongodb://localhost:27017
    uvicorn api.main:app --reload
    # interactive docs at http://localhost:8000/docs

The endpoint logic is shared with the offline demo (api/demo_crud.py) through
the framework-independent repositories in api/repositories.py.
"""
from __future__ import annotations
import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel, Field

# Make the sibling repositories module importable whether the app is launched
# as `uvicorn api.main:app` from the repo root or `uvicorn main:app` from api/.
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from repositories import (SQLReadingRepository, MongoReadingRepository,
                          NotFound, Conflict, POLL_FIELDS)

app = FastAPI(title="Beijing Air-Quality API",
              description="CRUD + time-series queries over MySQL and MongoDB",
              version="1.0.0")


# --------------------------------------------------------------------------- #
# connections (lazy; configured via environment variables)
# --------------------------------------------------------------------------- #
def get_sql_repo() -> SQLReadingRepository:
    import pymysql
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "beijing_air"),
        autocommit=True)
    try:
        yield SQLReadingRepository(conn, ph="%s")
    finally:
        conn.close()


def get_mongo_repo() -> MongoReadingRepository:
    from pymongo import MongoClient
    client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    col = client[os.getenv("MONGO_DB", "beijing_air")]["air_quality"]
    try:
        yield MongoReadingRepository(col)
    finally:
        client.close()


# --------------------------------------------------------------------------- #
# request/response models
# --------------------------------------------------------------------------- #
class PollutantValues(BaseModel):
    pm2_5: Optional[float] = None
    pm10: Optional[float] = None
    so2: Optional[float] = None
    no2: Optional[float] = None
    co: Optional[float] = None
    o3: Optional[float] = None


class SQLReadingCreate(PollutantValues):
    station: str = Field(..., examples=["Aotizhongxin"])
    ts: datetime = Field(..., examples=["2017-02-28T23:00:00"])


class MongoReadingCreate(BaseModel):
    station: str
    timestamp: datetime
    station_type: Optional[str] = None
    location: Optional[dict] = None
    pollutants: dict = Field(default_factory=dict)
    weather: dict = Field(default_factory=dict)


def _handle(fn, *a, **k):
    try:
        return fn(*a, **k)
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Conflict as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}


# =========================================================================== #
# SQL endpoints
# =========================================================================== #
@app.post("/sql/readings", status_code=201, tags=["sql"])
def sql_create(body: SQLReadingCreate, repo=Depends(get_sql_repo)):
    vals = {f: getattr(body, f) for f in POLL_FIELDS}
    return _handle(repo.create, body.station,
                   body.ts.strftime("%Y-%m-%d %H:%M:%S"), vals)


@app.get("/sql/readings/{station}/latest", tags=["sql"])
def sql_latest(station: str, repo=Depends(get_sql_repo)):
    """Required: latest record for a station."""
    return _handle(repo.latest, station)


@app.get("/sql/readings/{station}/range", tags=["sql"])
def sql_range(station: str,
              start: datetime = Query(...), end: datetime = Query(...),
              limit: int = 1000, repo=Depends(get_sql_repo)):
    """Required: records by date range."""
    return _handle(repo.range, station,
                   start.strftime("%Y-%m-%d %H:%M:%S"),
                   end.strftime("%Y-%m-%d %H:%M:%S"), limit)


@app.get("/sql/readings/{station}/item/{ts}", tags=["sql"])
def sql_get(station: str, ts: datetime, repo=Depends(get_sql_repo)):
    return _handle(repo.get, station, ts.strftime("%Y-%m-%d %H:%M:%S"))


@app.put("/sql/readings/{station}/item/{ts}", tags=["sql"])
def sql_update(station: str, ts: datetime, body: PollutantValues,
               repo=Depends(get_sql_repo)):
    return _handle(repo.update, station, ts.strftime("%Y-%m-%d %H:%M:%S"),
                   body.model_dump())


@app.delete("/sql/readings/{station}/item/{ts}", tags=["sql"])
def sql_delete(station: str, ts: datetime, repo=Depends(get_sql_repo)):
    return _handle(repo.delete, station, ts.strftime("%Y-%m-%d %H:%M:%S"))


# =========================================================================== #
# MongoDB endpoints
# =========================================================================== #
@app.post("/mongo/readings", status_code=201, tags=["mongo"])
def mongo_create(body: MongoReadingCreate, repo=Depends(get_mongo_repo)):
    return _handle(repo.create, body.model_dump())


@app.get("/mongo/readings/{station}/latest", tags=["mongo"])
def mongo_latest(station: str, repo=Depends(get_mongo_repo)):
    """Required: latest record for a station."""
    return _handle(repo.latest, station)


@app.get("/mongo/readings/{station}/range", tags=["mongo"])
def mongo_range(station: str,
                start: datetime = Query(...), end: datetime = Query(...),
                limit: int = 1000, repo=Depends(get_mongo_repo)):
    """Required: records by date range."""
    return _handle(repo.range, station, start, end, limit)


@app.get("/mongo/readings/{station}/item/{ts}", tags=["mongo"])
def mongo_get(station: str, ts: datetime, repo=Depends(get_mongo_repo)):
    return _handle(repo.get, station, ts)


@app.put("/mongo/readings/{station}/item/{ts}", tags=["mongo"])
def mongo_update(station: str, ts: datetime, body: dict,
                 repo=Depends(get_mongo_repo)):
    return _handle(repo.update, station, ts, body)


@app.delete("/mongo/readings/{station}/item/{ts}", tags=["mongo"])
def mongo_delete(station: str, ts: datetime, repo=Depends(get_mongo_repo)):
    return _handle(repo.delete, station, ts)
