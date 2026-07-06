"""
forecast.py  —  Task 4: end-to-end prediction script
=====================================================
Consolidates every previous task into a single forecasting pipeline:

  A. FETCH    a recent window of records for a station FROM THE API
             (Mongo documents carry both the PM2.5 history and the weather).
  B. PREPROCESS using the SAME Task-1 pipeline (preprocessing.py): aggregate to
             daily means and build the leakage-safe next-day feature row.
  C. LOAD     the trained classifier (models/clf_model.npz + model_meta.json).
  D. PREDICT  the next day's AQI category (with class probabilities), and
             backtest the model over the most recent days.

The fetch layer has two interchangeable clients:
  * HttpClient  — calls the live FastAPI service over HTTP (urllib, stdlib).
  * LocalClient — routes through the same MongoReadingRepository the API uses,
                  against an in-memory mongomock backend (for offline demo).

Usage:
  python forecast/forecast.py --station Aotizhongxin            # offline demo
  API_URL=http://localhost:8000 python forecast/forecast.py ... # live API
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "db"))
sys.path.insert(0, os.path.join(ROOT, "api"))
import preprocessing as pp

MODELS = os.path.join(ROOT, "models")
TAB = os.path.join(ROOT, "outputs", "tables")
FIG = os.path.join(ROOT, "outputs", "figures")
SHORT = ["Good", "Mod", "USG", "Unhlth", "VUnhlth", "Hazard"]


# --------------------------------------------------------------------------- #
# (A) FETCH — two interchangeable clients returning the same document shape
# --------------------------------------------------------------------------- #
class HttpClient:
    """Calls the live FastAPI /mongo endpoints (stdlib urllib, no deps)."""
    def __init__(self, base_url):
        self.base = base_url.rstrip("/")

    def _get(self, path, params=None):
        import urllib.parse
        import urllib.request
        url = f"{self.base}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.loads(r.read().decode())

    def latest(self, station):
        return self._get(f"/mongo/readings/{station}/latest")

    def range(self, station, start, end, limit=100000):
        return self._get(f"/mongo/readings/{station}/range",
                         {"start": start.isoformat(), "end": end.isoformat(),
                          "limit": limit})


class LocalClient:
    """Offline: same MongoReadingRepository the API uses, over mongomock."""
    def __init__(self, station, window_days=200):
        import mongomock
        from data_loader import load_raw, add_datetime
        from repositories import MongoReadingRepository
        from build_databases import STATION_META, _f
        raw, self.source = load_raw()
        raw = add_datetime(raw)
        df = pp.impute(pp.clean(raw))
        df = df[df["station"] == station]
        hi = df["datetime"].max()
        df = df[df["datetime"] >= hi - pd.Timedelta(days=window_days)]
        col = mongomock.MongoClient()["beijing_air"]["air_quality"]
        docs = []
        for d in df.to_dict("records"):
            stype, lat, lon = STATION_META.get(d["station"], ("urban", 0, 0))
            docs.append({"station": d["station"], "station_type": stype,
                         "timestamp": d["datetime"].to_pydatetime(),
                         "pollutants": {"pm2_5": _f(d["PM2.5"]), "pm10": _f(d["PM10"]),
                                        "so2": _f(d["SO2"]), "no2": _f(d["NO2"]),
                                        "co": _f(d["CO"]), "o3": _f(d["O3"])},
                         "weather": {"temp": _f(d["TEMP"]), "pres": _f(d["PRES"]),
                                     "dewp": _f(d["DEWP"]), "rain": _f(d["RAIN"]),
                                     "wspm": _f(d["WSPM"]), "wind_dir": d["wd"]}})
        col.insert_many(docs)
        self.repo = MongoReadingRepository(col)

    def latest(self, station):
        return self.repo.latest(station)

    def range(self, station, start, end, limit=100000):
        return self.repo.range(station, start, end, limit)


# --------------------------------------------------------------------------- #
# (B) PREPROCESS — fetched docs -> hourly frame -> daily next-day features
# --------------------------------------------------------------------------- #
def docs_to_frame(docs: list[dict]) -> pd.DataFrame:
    rows = []
    for d in docs:
        w = d.get("weather", {}); p = d.get("pollutants", {})
        rows.append({"station": d["station"],
                     "datetime": pd.to_datetime(d["timestamp"]),
                     "PM2.5": p.get("pm2_5"), "PM10": p.get("pm10"),
                     "SO2": p.get("so2"), "NO2": p.get("no2"),
                     "CO": p.get("co"), "O3": p.get("o3"),
                     "TEMP": w.get("temp"), "PRES": w.get("pres"),
                     "DEWP": w.get("dewp"), "RAIN": w.get("rain"),
                     "WSPM": w.get("wspm"), "wd": w.get("wind_dir")})
    return pd.DataFrame(rows).sort_values("datetime").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# (C) LOAD the trained classifier
# --------------------------------------------------------------------------- #
def _softmax(Z):
    Z = Z - Z.max(1, keepdims=True)
    e = np.exp(Z)
    return e / e.sum(1, keepdims=True)


def load_model():
    z = dict(np.load(os.path.join(MODELS, "clf_model.npz")))
    with open(os.path.join(MODELS, "model_meta.json")) as f:
        meta = json.load(f)
    return z, meta


def predict_proba(z, meta, Xstd):
    """Apply the deployed model (logistic regression or MLP) to standardized X."""
    if meta.get("model") == "mlp":
        a1 = np.maximum(0, Xstd @ z["W1"] + z["b1"])
        return _softmax(a1 @ z["W2"] + z["b2"])
    return _softmax(np.hstack([np.ones((len(Xstd), 1)), Xstd]) @ z["W"])


# --------------------------------------------------------------------------- #
# (D) PREDICT — orchestration
# --------------------------------------------------------------------------- #
def run(station: str, client, backtest_days: int = 90) -> dict:
    z, meta = load_model()
    labels = meta["labels"]
    feat = meta["feature_cols"]
    lab2i = {c: i for i, c in enumerate(labels)}

    # (A) fetch a long-enough recent window (need 30-day rolling + backtest)
    latest = client.latest(station)
    t_last = pd.to_datetime(latest["timestamp"])
    docs = client.range(station, (t_last - timedelta(days=200)).to_pydatetime(),
                        t_last.to_pydatetime())
    hist = docs_to_frame(docs)
    hist, _ = pp.cap_outliers(hist)             # same hourly spike capping as training

    # (B) build daily next-day features (keep the last day -> our forecast target)
    d, _ = pp.build_daily_classification(hist, require_label=False)
    d = d[d["station"] == station].sort_values("date").reset_index(drop=True)
    if len(d) < 5:
        raise SystemExit("Not enough daily history fetched to build features.")
    X = d[feat].to_numpy(float)
    Xs = (X - z["mu"]) / z["sd"]

    # (C/D) predict every day's next-day category
    proba = predict_proba(z, meta, Xs)
    pred = proba.argmax(1)

    # backtest over the most recent days whose true next-day label is known
    yi = d["y"].map(lab2i).to_numpy(dtype=float)
    known = np.where(~np.isnan(yi))[0]
    bt = known[-backtest_days:]
    bt_acc = float(np.mean(pred[bt] == yi[bt].astype(int))) if len(bt) else float("nan")

    # the final row has no known label yet -> that is the live next-day forecast
    last = len(d) - 1
    next_date = pd.to_datetime(d.loc[last, "date"]) + pd.Timedelta(days=1)
    fc_cat = labels[pred[last]]
    fc_conf = float(proba[last].max())
    top = sorted(((labels[c], float(proba[last, c])) for c in range(len(labels))),
                 key=lambda kv: -kv[1])[:3]

    # plot: recent actual vs predicted category + the next-day forecast point
    fig, ax = plt.subplots(figsize=(15, 5))
    dts = pd.to_datetime(d["date"].to_numpy())
    ax.step(dts[bt], yi[bt], where="mid", color="#333", lw=1.6, label="actual")
    ax.step(dts[bt], pred[bt], where="mid", color="crimson", lw=1.4,
            ls="--", label="predicted")
    ax.scatter([next_date], [pred[last]], color="#1a7", s=110, zorder=5,
               label="next-day forecast")
    ax.set_yticks(range(len(labels))); ax.set_yticklabels(SHORT)
    ax.set_title(f"Task 4: next-day AQI category — backtest + forecast "
                 f"({station}, last {len(bt)} days, acc={bt_acc:.2f})")
    ax.legend(loc="upper left")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "4_forecast_backtest.png"), dpi=120)
    plt.close(fig)

    return {"station": station,
            "deployed_model": meta.get("deployed_model", meta.get("model")),
            "data_source": meta.get("source", "?"),
            "fetched_records": len(hist),
            "daily_days_built": len(d),
            "today_category": str(d.loc[last, "cat"]),
            f"backtest_last_{len(bt)}d_accuracy": round(bt_acc, 3),
            "forecast_date": str(next_date.date()),
            "forecast_next_day_category": fc_cat,
            "forecast_confidence": round(fc_conf, 3),
            "top3_class_probabilities": {k: round(v, 3) for k, v in top}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--station", default="Aotizhongxin")
    ap.add_argument("--api-url", default=os.getenv("API_URL"))
    args = ap.parse_args()

    if args.api_url:
        print(f"[fetch] live API at {args.api_url}")
        client = HttpClient(args.api_url)
    else:
        print("[fetch] offline demo via in-process repository (mongomock)")
        client = LocalClient(args.station)

    result = run(args.station, client)
    print("\n=== FORECAST RESULT ===")
    for k, v in result.items():
        print(f"  {k:30s}: {v}")

    os.makedirs(TAB, exist_ok=True)
    with open(os.path.join(TAB, "forecast_demo.md"), "w") as f:
        f.write("# Task 4 — Forecast script output\n\n")
        f.write("Pipeline: fetch (API) -> preprocess (daily Task-1 features) -> "
                "load classifier -> predict next-day AQI category.\n\n```json\n")
        f.write(json.dumps(result, indent=2))
        f.write("\n```\n")
    print(f"\nsaved -> {os.path.join(TAB, 'forecast_demo.md')}")


if __name__ == "__main__":
    main()
