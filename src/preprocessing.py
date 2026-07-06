"""
preprocessing.py
================
Reusable time-series preprocessing pipeline for the Beijing Multi-Site
Air-Quality data. The SAME functions are used in:
  * Task 1  (EDA + modelling)
  * Task 4  (forecast script, so train/inference preprocessing matches)

Pipeline order (important for correctness):
  load -> clean/index -> assess missingness -> impute (per station,
  time-aware) -> engineer time features -> lag features -> moving averages.

Imputation is performed BEFORE lag/rolling features so the autocorrelation
structure that those features depend on is preserved, and it is done
PER STATION so one site's outage never leaks into another's history.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

TARGET = "PM2.5"
POLLUTANTS = ["PM2.5", "PM10", "SO2", "NO2", "CO", "O3"]
WEATHER_NUM = ["TEMP", "PRES", "DEWP", "RAIN", "WSPM"]
NUMERIC = POLLUTANTS + WEATHER_NUM
DEFAULT_LAGS = [1, 2, 3, 24, 168]          # 1-3h, 1 day, 1 week (hourly data)
DEFAULT_WINDOWS = [3, 24, 168]             # 3h, daily, weekly moving averages


# --------------------------------------------------------------------------- #
# 1. cleaning / indexing
# --------------------------------------------------------------------------- #
def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Build datetime, sort by station+time, coerce numerics, drop dup hours."""
    df = df.copy()
    if "datetime" not in df.columns:
        df["datetime"] = pd.to_datetime(df[["year", "month", "day", "hour"]])
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # physically impossible negatives -> missing (concentrations/temp floors)
    for c in POLLUTANTS + ["WSPM", "RAIN"]:
        df.loc[df[c] < 0, c] = np.nan
    df = (df.sort_values(["station", "datetime"])
            .drop_duplicates(["station", "datetime"])
            .reset_index(drop=True))
    return df


# --------------------------------------------------------------------------- #
# 2. missingness assessment
# --------------------------------------------------------------------------- #
def missing_report(df: pd.DataFrame) -> pd.DataFrame:
    """Per-column missing count + percentage, sorted worst first."""
    cols = [c for c in NUMERIC + ["wd"] if c in df.columns]
    n = len(df)
    rep = pd.DataFrame({
        "missing": [df[c].isna().sum() for c in cols],
    }, index=cols)
    rep["pct"] = (100 * rep["missing"] / n).round(2)
    return rep.sort_values("missing", ascending=False)


def missing_by_station(df: pd.DataFrame, col: str = TARGET) -> pd.DataFrame:
    g = df.groupby("station")[col]
    out = pd.DataFrame({"missing": g.apply(lambda s: s.isna().sum()),
                        "n": g.size()})
    out["pct"] = (100 * out["missing"] / out["n"]).round(2)
    return out.sort_values("pct", ascending=False)


# --------------------------------------------------------------------------- #
# 3. imputation (per station, time-aware)
# --------------------------------------------------------------------------- #
def impute(df: pd.DataFrame,
           short_gap: int = 6,
           method: str = "time") -> pd.DataFrame:
    """
    Time-aware imputation, applied independently per station:
      * numeric: linear/time interpolation for gaps <= `short_gap` hours,
        then forward-fill + back-fill any longer residual runs.
      * wind direction (categorical): forward-fill then mode.
    Rationale: gaps are short consecutive sensor outages, so interpolation
    respects the local trend far better than mean/median imputation, and it
    keeps the regular hourly index intact for lag/rolling features.
    """
    df = df.copy().sort_values(["station", "datetime"])
    num = [c for c in NUMERIC if c in df.columns]

    def _fill(group: pd.DataFrame) -> pd.DataFrame:
        g = group.set_index("datetime")
        g[num] = (g[num]
                  .interpolate(method=method, limit=short_gap,
                               limit_direction="both")
                  .ffill().bfill())
        if "wd" in g.columns:
            g["wd"] = g["wd"].ffill().bfill()
            if g["wd"].isna().any():
                g["wd"] = g["wd"].fillna(g["wd"].mode().iloc[0]
                                         if not g["wd"].mode().empty else "N")
        return g.reset_index()

    parts = [_fill(group) for _, group in df.groupby("station", sort=False)]
    return pd.concat(parts, ignore_index=True)


# --------------------------------------------------------------------------- #
# 3.5 outlier / sensor-glitch handling (robust, causal, conservative)
# --------------------------------------------------------------------------- #
def iqr_upper_fence(s: pd.Series, k: float = 3.0) -> float:
    """Tukey upper fence Q3 + k*IQR for one series (used to fit, persist and
    later re-apply the same outlier cap at inference time)."""
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    return float(q3 + k * (q3 - q1))


def cap_outliers(df: pd.DataFrame,
                 cols: list[str] = None,
                 k: float = 3.0,
                 target: str = TARGET) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Winsorize extreme upper-tail sensor spikes per station using Tukey's
    "far-out" fence: any reading above Q3 + k*IQR (k=3) is clipped back to
    that fence. Computed independently per station and per pollutant.

    Scope. By default this is applied only to the variables the forecaster
    actually consumes — the PM2.5 target and wind speed (WSPM) — which are the
    right-skewed channels prone to spike artefacts. The co-pollutants are left
    untouched (they are excluded from the model and shown as-is in the EDA),
    and degenerate/zero-inflated columns (IQR = 0, e.g. RAIN) are skipped.

    Design rationale:
      * UPPER side only. Concentrations and wind speed are non-negative and low
        values are physically valid (true negatives were already set to NaN in
        clean()), so only the implausible high spikes are capped.
      * Tukey's k=3 ("far out") rather than the usual k=1.5. PM2.5 is heavily
        right-skewed and the genuine multi-hour pollution episodes are exactly
        the signal we want to forecast. The wide k=3 fence leaves those episodes
        intact and trims only the rare extreme spikes (well under 1% of
        readings), so the heavy tail is preserved, not erased.
      * IQR-based, so — unlike a rolling MAD filter — it never collapses on
        low-variance stretches and never over-flags ordinary values.

    Returns the cleaned frame and a per-column report (count + %) of capped
    values, so the step stays transparent and fully reproducible.
    """
    cols = cols or [target, "WSPM"]
    cols = [c for c in cols if c in df.columns]
    df = df.copy().sort_values(["station", "datetime"])
    capped_counts = {c: 0 for c in cols}

    def _cap(group: pd.DataFrame) -> pd.DataFrame:
        g = group.copy()
        for c in cols:
            s = g[c]
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            if iqr <= 0:                      # degenerate / zero-inflated column
                continue
            hi = q3 + k * iqr
            mask = s > hi
            capped_counts[c] += int(mask.sum())
            g[c] = s.clip(upper=hi)
        return g

    parts = [_cap(group) for _, group in df.groupby("station", sort=False)]
    out = pd.concat(parts, ignore_index=True)
    n = len(out)
    report = pd.DataFrame(
        {"capped": [capped_counts[c] for c in cols]}, index=cols)
    report["pct"] = (100 * report["capped"] / n).round(3)
    report = report.sort_values("capped", ascending=False)
    return out, report


# --------------------------------------------------------------------------- #
# 4. calendar / time features
# --------------------------------------------------------------------------- #
def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    dt = df["datetime"]
    df["hour"] = dt.dt.hour
    df["dayofweek"] = dt.dt.dayofweek
    df["month"] = dt.dt.month
    df["is_weekend"] = (df["dayofweek"] >= 5).astype(int)
    # Beijing coal-heating season (mid-Nov .. mid-Mar) -> key PM2.5 driver
    df["is_heating_season"] = df["month"].isin([11, 12, 1, 2, 3]).astype(int)
    df["season"] = (df["month"] % 12 // 3).map(
        {0: "Winter", 1: "Spring", 2: "Summer", 3: "Autumn"})
    # cyclical encodings (so 23h and 0h are adjacent)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    return df


# --------------------------------------------------------------------------- #
# 5. lag features + moving averages  (REQUIRED by the brief)
# --------------------------------------------------------------------------- #
def add_lag_features(df: pd.DataFrame, target: str = TARGET,
                     lags: list[int] = None) -> pd.DataFrame:
    """y(t-k) lag features, computed per station (no cross-station leakage)."""
    lags = lags or DEFAULT_LAGS
    df = df.copy().sort_values(["station", "datetime"])
    g = df.groupby("station")[target]
    for k in lags:
        df[f"{target}_lag{k}"] = g.shift(k)
    return df


def add_moving_averages(df: pd.DataFrame, target: str = TARGET,
                        windows: list[int] = None) -> pd.DataFrame:
    """Trailing moving average + rolling std, per station. Uses shift(1) so
    the window only sees PAST values (no target leakage at time t)."""
    windows = windows or DEFAULT_WINDOWS
    df = df.copy().sort_values(["station", "datetime"])
    grp = df.groupby("station")[target]
    for w in windows:
        df[f"{target}_ma{w}"] = grp.transform(
            lambda s: s.shift(1).rolling(w, min_periods=max(2, w // 4)).mean())
        df[f"{target}_mstd{w}"] = grp.transform(
            lambda s: s.shift(1).rolling(w, min_periods=max(2, w // 4)).std())
    return df


# --------------------------------------------------------------------------- #
# 6. one-call builder
# --------------------------------------------------------------------------- #
def build_features(df: pd.DataFrame, target: str = TARGET,
                   lags: list[int] = None,
                   windows: list[int] = None,
                   do_impute: bool = True,
                   do_cap: bool = True) -> pd.DataFrame:
    """Full feature pipeline:
    clean -> impute -> cap outliers -> time -> lag -> moving avg.

    Outlier capping sits AFTER imputation (so the rolling statistics are not
    broken by gaps) and BEFORE lag/rolling features (so a glitch is not copied
    forward into every downstream lag and moving average)."""
    df = clean(df)
    if do_impute:
        df = impute(df)
    if do_cap:
        df, _ = cap_outliers(df, target=target)
    df = add_time_features(df)
    df = add_lag_features(df, target, lags)
    df = add_moving_averages(df, target, windows)
    return df


# --------------------------------------------------------------------------- #
# 7. daily AQI-category classification  (next-day forecasting target)
# --------------------------------------------------------------------------- #
# US EPA 24-hour PM2.5 AQI breakpoints (ug/m3) -> six health categories.
AQI_BINS = [0.0, 12.0, 35.4, 55.4, 150.4, 250.4, float("inf")]
AQI_LABELS = ["Good", "Moderate", "USG", "Unhealthy",
              "Very Unhealthy", "Hazardous"]
DAILY_LAGS = [1, 2, 3, 7]
DAILY_ROLL = [7, 30]
CLF_WEATHER = ["TEMP", "PRES", "DEWP", "WSPM", "RAIN"]
# same-day co-pollutant channels (EDA Q3: PM10 r~0.88, combustion tracers CO/NO2)
CLF_COPOLL = ["PM10", "SO2", "NO2", "CO", "O3"]
# 1-day lag of the strongest particulate/combustion tracers
COPOLL_LAG1 = ["PM10", "NO2", "CO"]


def aqi_category(pm) -> pd.Categorical:
    """Map daily-mean PM2.5 to an ordered EPA AQI category."""
    return pd.cut(pm, bins=AQI_BINS, labels=AQI_LABELS,
                  right=True, include_lowest=True)


def daily_means(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate cleaned+imputed hourly readings to per-station daily means."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["datetime"]).dt.floor("D")
    cols = [c for c in NUMERIC if c in df.columns]
    daily = (df.groupby(["station", "date"])[cols].mean().reset_index()
               .sort_values(["station", "date"]))
    return daily


def build_daily_classification(df: pd.DataFrame, require_label: bool = True):
    """Build the leakage-safe *next-day* AQI-category design matrix.

    Each row is a station-day t; the features use only information available by
    the end of day t (today's and earlier daily PM2.5 and weather, plus the
    known calendar of the target day t+1), and the label is the AQI category of
    day t+1. Returns (frame, feature_columns).

    With ``require_label=False`` the most recent day per station (whose t+1 label
    is not yet known) is retained, so the same builder serves inference in the
    Task-4 forecast script.
    """
    d = daily_means(df)
    d["pm"] = d["PM2.5"]
    d["cat"] = aqi_category(d["pm"]).astype(object)
    g = d.groupby("station", sort=False)

    # today's value (t) plus daily lags (t-1 .. t-7) — all known by the end of t
    d["pm_today"] = d["pm"]
    for k in DAILY_LAGS:
        d[f"pm_lag{k}"] = g["pm"].shift(k)
    # trailing rolling stats through day t (inclusive -> known at end of t)
    d["pm_roll7_mean"] = g["pm"].transform(lambda s: s.rolling(7, min_periods=3).mean())
    d["pm_roll7_std"] = g["pm"].transform(lambda s: s.rolling(7, min_periods=3).std())
    d["pm_roll30_mean"] = g["pm"].transform(lambda s: s.rolling(30, min_periods=10).mean())
    d["pm_roll30_std"] = g["pm"].transform(lambda s: s.rolling(30, min_periods=10).std())
    # deviation of today's PM2.5 from its trailing weekly mean — the episode-onset
    # signal flagged in EDA Q5 (causal: both terms are known by the end of day t)
    d["pm_dev7"] = d["pm_today"] - d["pm_roll7_mean"]

    # same-day co-pollutant channels (EDA Q3) plus a 1-day lag of the strongest
    # tracers — today's co-pollutants are known by the end of day t, so causal
    copoll_cols = []
    for c in CLF_COPOLL:
        if c in d.columns:
            name = f"{c.lower().replace('.', '_')}_today"
            d[name] = d[c]
            copoll_cols.append(name)
    for c in COPOLL_LAG1:
        if c in d.columns:
            name = f"{c.lower().replace('.', '_')}_lag1"
            d[name] = g[c].shift(1)
            copoll_cols.append(name)

    # calendar of the TARGET day (t+1) — deterministic, known in advance
    tgt_date = d["date"] + pd.Timedelta(days=1)
    d["t_month_sin"] = np.sin(2 * np.pi * tgt_date.dt.month / 12)
    d["t_month_cos"] = np.cos(2 * np.pi * tgt_date.dt.month / 12)
    d["t_doy_sin"] = np.sin(2 * np.pi * tgt_date.dt.dayofyear / 365.25)
    d["t_doy_cos"] = np.cos(2 * np.pi * tgt_date.dt.dayofyear / 365.25)
    d["t_is_weekend"] = (tgt_date.dt.dayofweek >= 5).astype(int)
    d["t_is_heating"] = tgt_date.dt.month.isin([11, 12, 1, 2, 3]).astype(int)

    # label: AQI category of day t+1
    d["y"] = g["cat"].shift(-1)

    feature_cols = (["pm_today"] + [f"pm_lag{k}" for k in DAILY_LAGS]
                    + ["pm_roll7_mean", "pm_roll7_std", "pm_roll30_mean",
                       "pm_roll30_std", "pm_dev7"]
                    + copoll_cols
                    + CLF_WEATHER
                    + ["t_month_sin", "t_month_cos", "t_doy_sin", "t_doy_cos",
                       "t_is_weekend", "t_is_heating"])
    need = feature_cols + (["y"] if require_label else [])
    d = d.dropna(subset=need).reset_index(drop=True)
    return d, feature_cols


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from data_loader import load_raw, add_datetime
    raw, src = load_raw()
    raw = add_datetime(raw)
    print(f"[{src}] raw rows: {len(raw):,}")
    print("\nMissing report (overall):")
    print(missing_report(clean(raw)).to_string())
    feat = build_features(raw)
    print(f"\nfeature rows: {len(feat):,}  cols: {feat.shape[1]}")
    print("engineered:", [c for c in feat.columns if "lag" in c or "ma" in c
                          or "sin" in c or "heating" in c])
