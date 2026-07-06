"""
data_loader.py
==============
Single source of truth for loading the Beijing Multi-Site Air-Quality data.

Resolution order (REAL data always wins):
  1. data/raw/PRSA_Data_*.csv         <- drop the real Kaggle/UCI files here
  2. data/raw/*.zip                    <- or drop the downloaded zip; auto-extracted
  3. data/synthetic/PRSA_Data_*.csv    <- generated fixture (auto-created if absent)

Because the schema is identical, the rest of the pipeline (EDA, modelling,
databases, API, forecast) is agnostic to which source is used. When the real
files appear in data/raw/, every downstream output regenerates on real data
with zero code changes.
"""
from __future__ import annotations
import glob
import os
import zipfile
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW_DIR = os.path.join(ROOT, "data", "raw")
SYN_DIR = os.path.join(ROOT, "data", "synthetic")

CANONICAL_COLS = ["No", "year", "month", "day", "hour",
                  "PM2.5", "PM10", "SO2", "NO2", "CO", "O3",
                  "TEMP", "PRES", "DEWP", "RAIN", "wd", "WSPM", "station"]


def _extract_zips(folder: str) -> None:
    for z in glob.glob(os.path.join(folder, "*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(folder)
            print(f"[data_loader] extracted {os.path.basename(z)}")
        except zipfile.BadZipFile:
            print(f"[data_loader] WARNING: bad zip {z}")


def _find_station_csvs(folder: str) -> list[str]:
    if not os.path.isdir(folder):
        return []
    _extract_zips(folder)
    # real files are named PRSA_Data_<Station>_*.csv; also accept nested dirs
    hits = glob.glob(os.path.join(folder, "**", "PRSA_*.csv"), recursive=True)
    return sorted(hits)


def data_source() -> tuple[str, list[str]]:
    """Return ('real'|'synthetic', [csv paths])."""
    real = _find_station_csvs(RAW_DIR)
    if real:
        return "real", real
    syn = _find_station_csvs(SYN_DIR)
    if not syn:                       # generate fixture on first use
        from generate_synthetic import generate
        print("[data_loader] no data found -> generating synthetic fixture ...")
        generate(SYN_DIR, verbose=False)
        syn = _find_station_csvs(SYN_DIR)
    return "synthetic", syn


def load_raw() -> tuple[pd.DataFrame, str]:
    """Load + concatenate all stations. Returns (df, source_label)."""
    source, paths = data_source()
    frames = [pd.read_csv(p) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    # normalise column presence/order
    for c in CANONICAL_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[CANONICAL_COLS]
    return df, source


def add_datetime(df: pd.DataFrame) -> pd.DataFrame:
    """Build a proper datetime index column from year/month/day/hour."""
    df = df.copy()
    df["datetime"] = pd.to_datetime(df[["year", "month", "day", "hour"]])
    return df


if __name__ == "__main__":
    df, src = load_raw()
    df = add_datetime(df)
    print(f"source      : {src}")
    print(f"rows        : {len(df):,}")
    print(f"stations    : {df['station'].nunique()} -> "
          f"{sorted(df['station'].unique())}")
    print(f"time range  : {df['datetime'].min()} .. {df['datetime'].max()}")
    print(f"columns     : {list(df.columns)}")
    print(df.head(3).to_string())
