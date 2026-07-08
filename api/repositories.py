"""
repositories.py  —  Task 3 data-access layer (framework-independent)
====================================================================
All CRUD + time-series query logic lives here, decoupled from FastAPI so it can
be unit-tested/demonstrated without a web server and reused by both the SQL and
MongoDB backends.

  * SQLReadingRepository   works over any DB-API 2.0 connection.
      - parameter placeholder is configurable: '%s' for MySQL (PyMySQL),
        '?' for the SQLite demo. => the SAME code runs in production and in tests.
  * MongoReadingRepository works over a pymongo/mongomock collection (same API).

Resource = one hourly *pollutant* reading, identified by (station_name, ts).
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional

POLL_FIELDS = ["pm2_5", "pm10", "so2", "no2", "co", "o3"]


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


# ===========================================================================
# SQL (MySQL in prod, SQLite in the demo) — DB-API 2.0
# ===========================================================================
class SQLReadingRepository:
    def __init__(self, conn, ph: str = "%s"):
        self.c = conn
        self.ph = ph                     # '%s' (MySQL) or '?' (SQLite)

    # -- helpers ----------------------------------------------------------
    def _ex(self, sql: str, params: tuple = ()):
        """Execute via a cursor and return it. Portable across DB-API 2.0
        drivers: PyMySQL exposes no Connection.execute() (and its
        Cursor.execute() returns rowcount, not the cursor), so we must open a
        cursor explicitly rather than rely on the sqlite3 connection shortcut."""
        cur = self.c.cursor()
        cur.execute(sql, params)
        return cur

    def _station_id(self, name: str) -> int:
        cur = self._ex(
            f"SELECT station_id FROM stations WHERE station_name = {self.ph}",
            (name,))
        row = cur.fetchone()
        if not row:
            raise NotFound(f"station '{name}' does not exist")
        return row[0]

    def _row_to_dict(self, name: str, row) -> dict:
        ts, *vals = row
        return {"station": name, "ts": ts,
                **{f: v for f, v in zip(POLL_FIELDS, vals)}}

    def _select(self, sid: int, where: str, params: tuple):
        cols = ", ".join(["ts"] + POLL_FIELDS)
        return self._ex(
            f"SELECT {cols} FROM pollutant_readings "
            f"WHERE station_id = {self.ph} {where}", (sid, *params))

    # -- CREATE -----------------------------------------------------------
    def create(self, station: str, ts: str, values: dict) -> dict:
        sid = self._station_id(station)
        exists = self._select(sid, f"AND ts = {self.ph}", (ts,)).fetchone()
        if exists:
            raise Conflict(f"reading for {station} @ {ts} already exists")
        cols = ", ".join(POLL_FIELDS)
        marks = ", ".join([self.ph] * len(POLL_FIELDS))
        self._ex(
            f"INSERT INTO pollutant_readings (station_id, ts, {cols}) "
            f"VALUES ({self.ph}, {self.ph}, {marks})",
            (sid, ts, *[values.get(f) for f in POLL_FIELDS]))
        self.c.commit()
        return self.get(station, ts)

    # -- READ: one -------------------------------------------------------
    def get(self, station: str, ts: str) -> dict:
        sid = self._station_id(station)
        row = self._select(sid, f"AND ts = {self.ph}", (ts,)).fetchone()
        if not row:
            raise NotFound(f"no reading for {station} @ {ts}")
        return self._row_to_dict(station, row)

    # -- READ: latest (required query endpoint) --------------------------
    def latest(self, station: str) -> dict:
        sid = self._station_id(station)
        row = self._select(sid, "ORDER BY ts DESC LIMIT 1", ()).fetchone()
        if not row:
            raise NotFound(f"no readings for {station}")
        return self._row_to_dict(station, row)

    # -- READ: by date range (required query endpoint) -------------------
    def range(self, station: str, start: str, end: str,
              limit: int = 1000) -> list[dict]:
        sid = self._station_id(station)
        rows = self._select(
            sid, f"AND ts BETWEEN {self.ph} AND {self.ph} "
                 f"ORDER BY ts LIMIT {self.ph}",
            (start, end, limit)).fetchall()
        return [self._row_to_dict(station, r) for r in rows]

    # -- UPDATE -----------------------------------------------------------
    def update(self, station: str, ts: str, values: dict) -> dict:
        sid = self._station_id(station)
        fields = {k: v for k, v in values.items() if k in POLL_FIELDS
                  and v is not None}
        if not fields:
            return self.get(station, ts)
        sets = ", ".join(f"{k} = {self.ph}" for k in fields)
        cur = self._ex(
            f"UPDATE pollutant_readings SET {sets} "
            f"WHERE station_id = {self.ph} AND ts = {self.ph}",
            (*fields.values(), sid, ts))
        self.c.commit()
        if cur.rowcount == 0:
            raise NotFound(f"no reading for {station} @ {ts}")
        return self.get(station, ts)

    # -- DELETE -----------------------------------------------------------
    def delete(self, station: str, ts: str) -> dict:
        sid = self._station_id(station)
        cur = self._ex(
            f"DELETE FROM pollutant_readings "
            f"WHERE station_id = {self.ph} AND ts = {self.ph}", (sid, ts))
        self.c.commit()
        if cur.rowcount == 0:
            raise NotFound(f"no reading for {station} @ {ts}")
        return {"deleted": True, "station": station, "ts": ts}


# ===========================================================================
# MongoDB (pymongo in prod, mongomock in the demo — same API)
# ===========================================================================
class MongoReadingRepository:
    def __init__(self, collection):
        self.col = collection

    @staticmethod
    def _clean(doc: Optional[dict]) -> Optional[dict]:
        if doc:
            doc.pop("_id", None)
        return doc

    def _ts(self, ts):
        return ts if isinstance(ts, datetime) else datetime.fromisoformat(ts)

    # -- CREATE -----------------------------------------------------------
    def create(self, doc: dict) -> dict:
        doc = dict(doc)
        doc["timestamp"] = self._ts(doc["timestamp"])
        if self.col.find_one({"station": doc["station"],
                              "timestamp": doc["timestamp"]}):
            raise Conflict("document already exists for station/timestamp")
        self.col.insert_one(doc)
        return self._clean(self.col.find_one(
            {"station": doc["station"], "timestamp": doc["timestamp"]}))

    # -- READ: one --------------------------------------------------------
    def get(self, station: str, ts) -> dict:
        d = self._clean(self.col.find_one(
            {"station": station, "timestamp": self._ts(ts)}))
        if not d:
            raise NotFound(f"no document for {station} @ {ts}")
        return d

    # -- READ: latest (required) -----------------------------------------
    def latest(self, station: str) -> dict:
        cur = self.col.find({"station": station}).sort("timestamp", -1).limit(1)
        docs = [self._clean(d) for d in cur]
        if not docs:
            raise NotFound(f"no documents for {station}")
        return docs[0]

    # -- READ: by date range (required) ----------------------------------
    def range(self, station: str, start, end, limit: int = 1000) -> list[dict]:
        cur = (self.col.find({"station": station,
                              "timestamp": {"$gte": self._ts(start),
                                            "$lte": self._ts(end)}})
               .sort("timestamp", 1).limit(limit))
        return [self._clean(d) for d in cur]

    # -- UPDATE -----------------------------------------------------------
    # Only the measurement sub-documents are mutable; identity/structural fields
    # (station, timestamp, station_type, location, _id) and any unknown top-level
    # key are rejected, mirroring the SQL side's field whitelist so a client
    # cannot re-key or corrupt a document via $set.
    _MUTABLE = ("pollutants", "weather")

    def update(self, station: str, ts, values: dict) -> dict:
        fields = {k: v for k, v in values.items()
                  if k.split(".", 1)[0] in self._MUTABLE}
        if not fields:
            return self.get(station, ts)
        res = self.col.update_one(
            {"station": station, "timestamp": self._ts(ts)}, {"$set": fields})
        if res.matched_count == 0:
            raise NotFound(f"no document for {station} @ {ts}")
        return self.get(station, ts)

    # -- DELETE -----------------------------------------------------------
    def delete(self, station: str, ts) -> dict:
        res = self.col.delete_one(
            {"station": station, "timestamp": self._ts(ts)})
        if res.deleted_count == 0:
            raise NotFound(f"no document for {station} @ {ts}")
        return {"deleted": True, "station": station, "ts": str(ts)}
