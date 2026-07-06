"""
eda.py  —  Task 1A: Understanding the dataset
=============================================
Produces the exploratory-data-analysis artefacts required by the brief:
  * time range + frequency/granularity
  * missing-value assessment (table + figure) and the imputation rationale
  * statistical distribution of numerical columns (describe table + histograms)
  * a target overview (PM2.5 over time + monthly climatology)

All figures are written to outputs/figures and all tables to outputs/tables.
A machine-readable summary (eda_summary.json) is emitted for the report.
"""
from __future__ import annotations
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_loader import load_raw, add_datetime
import preprocessing as pp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "outputs", "figures")
TAB = os.path.join(ROOT, "outputs", "tables")
os.makedirs(FIG, exist_ok=True)
os.makedirs(TAB, exist_ok=True)
sns.set_theme(style="whitegrid", context="talk")
PALETTE = "viridis"


def overview(df: pd.DataFrame) -> dict:
    dt = df["datetime"]
    # infer cadence within a SINGLE station (timestamps repeat across stations)
    one = (df[df["station"] == df["station"].iloc[0]]
           .sort_values("datetime")["datetime"])
    freq = one.diff().dropna().mode().iloc[0]
    info = {
        "rows": int(len(df)),
        "stations": int(df["station"].nunique()),
        "station_names": sorted(df["station"].unique().tolist()),
        "start": str(dt.min()),
        "end": str(dt.max()),
        "span_days": int((dt.max() - dt.min()).days),
        "inferred_frequency": str(freq),
        "n_numeric_cols": len(pp.NUMERIC),
    }
    return info


def plot_missingness(df: pd.DataFrame) -> pd.DataFrame:
    rep = pp.missing_report(df)
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.viridis(np.linspace(0.15, 0.85, len(rep)))
    ax.barh(rep.index[::-1], rep["pct"][::-1], color=colors)
    ax.set_xlabel("% missing")
    ax.set_title("Missing values by column")
    for i, (idx, row) in enumerate(rep[::-1].iterrows()):
        ax.text(row["pct"] + 0.03, i, f"{row['pct']:.2f}%", va="center",
                fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "01_missingness.png"), dpi=120)
    plt.close(fig)
    rep.to_csv(os.path.join(TAB, "missing_report.csv"))
    return rep


def describe_numeric(df: pd.DataFrame) -> pd.DataFrame:
    desc = df[pp.NUMERIC].describe().T
    desc["skew"] = df[pp.NUMERIC].skew()
    desc = desc.round(2)
    desc.to_csv(os.path.join(TAB, "numeric_describe.csv"))
    return desc


def plot_distributions(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 4, figsize=(20, 12))
    for ax, col in zip(axes.ravel(), pp.NUMERIC):
        sns.histplot(df[col].dropna(), bins=60, ax=ax, color="#3b7dba", kde=True)
        ax.set_title(f"{col}  (skew={df[col].skew():.2f})")
        ax.set_xlabel("")
    # hide unused axis (11 numeric cols in 3x4 grid)
    for ax in axes.ravel()[len(pp.NUMERIC):]:
        ax.set_visible(False)
    fig.suptitle("Distributions of numerical columns", y=1.01, fontsize=22)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "02_distributions.png"), dpi=120,
                bbox_inches="tight")
    plt.close(fig)


def plot_target_overview(df: pd.DataFrame, station: str = "Aotizhongxin") -> None:
    fig, axes = plt.subplots(2, 1, figsize=(16, 10))
    s = (df[df["station"] == station]
         .set_index("datetime")["PM2.5"].resample("D").mean())
    axes[0].plot(s.index, s.values, lw=0.7, color="#444")
    axes[0].plot(s.index, s.rolling(30).mean(), lw=2.2, color="crimson",
                 label="30-day moving avg")
    axes[0].set_title(f"Daily mean PM2.5 ({station})")
    axes[0].set_ylabel("PM2.5 (ug/m3)")
    axes[0].legend()

    monthly = df.groupby(df["datetime"].dt.month)["PM2.5"].mean()
    axes[1].bar(monthly.index, monthly.values,
                color=plt.cm.coolwarm(np.linspace(0, 1, 12)))
    axes[1].set_title("Monthly mean PM2.5 (all stations), winter heating peak")
    axes[1].set_xlabel("month")
    axes[1].set_ylabel("PM2.5 (ug/m3)")
    axes[1].set_xticks(range(1, 13))
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "03_target_overview.png"), dpi=120)
    plt.close(fig)


def run() -> dict:
    raw, source = load_raw()
    raw = add_datetime(raw)
    df = pp.clean(raw)

    info = overview(df)
    info["source"] = source
    rep = plot_missingness(df)
    desc = describe_numeric(df)
    plot_distributions(df)
    plot_target_overview(df)

    info["missing_top"] = rep.head(6)["pct"].to_dict()
    with open(os.path.join(TAB, "eda_summary.json"), "w") as f:
        json.dump(info, f, indent=2)

    print(f"[source={source}] rows={info['rows']:,} stations={info['stations']}")
    print(f"time range : {info['start']} .. {info['end']} "
          f"({info['span_days']} days)")
    print(f"frequency  : {info['inferred_frequency']}")
    print("\n— Missing report —")
    print(rep.to_string())
    print("\n— Numeric describe (head) —")
    print(desc[["mean", "std", "min", "50%", "max", "skew"]].to_string())
    print(f"\nFigures -> {FIG}")
    return info


if __name__ == "__main__":
    run()
