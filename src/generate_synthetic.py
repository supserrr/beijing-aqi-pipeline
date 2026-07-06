"""
generate_synthetic.py
======================
Generate a HIGH-FIDELITY synthetic stand-in for the Beijing Multi-Site
Air-Quality dataset when the real CSVs are not available locally.

The synthetic data matches the REAL dataset exactly in:
  * file naming        -> PRSA_Data_<Station>_20130301-20170228.csv
  * 12 station names
  * column names/order -> No, year, month, day, hour,
                          PM2.5, PM10, SO2, NO2, CO, O3,
                          TEMP, PRES, DEWP, RAIN, wd, WSPM, station
  * hourly cadence     -> 2013-03-01 00:00 .. 2017-02-28 23:00 (35,064 h/station)
  * realistic structure-> diurnal + annual seasonality, multi-day pollution
                          episodes (autocorrelation), winter heating spikes,
                          wind dispersion, inter-pollutant correlation,
                          right-skewed pollutant distributions, and
                          block-missing values (sensor outages).

==> The ONLY purpose of this file is to let the full pipeline run/test end to
    end before the real Kaggle download is in place. The data loader prefers
    the REAL files automatically (see data_loader.py). Any numbers/plots
    produced from synthetic data are clearly labelled and must be regenerated
    on the real download for the final report.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd

# The 12 real monitoring stations + a coarse urban/suburban/bg type
STATIONS = {
    "Aotizhongxin":  "urban",
    "Changping":     "suburban",
    "Dingling":      "background",
    "Dongsi":        "urban",
    "Guanyuan":      "urban",
    "Gucheng":       "urban",
    "Huairou":       "suburban",
    "Nongzhanguan":  "urban",
    "Shunyi":        "suburban",
    "Tiantan":       "urban",
    "Wanliu":        "urban",
    "Wanshouxigong": "urban",
}
WIND_DIRS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
             "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

START = "2013-03-01 00:00"
END = "2017-02-28 23:00"

# Multiplicative pollution offset by station type (urban dirtier, bg cleaner)
TYPE_OFFSET = {"urban": 1.12, "suburban": 0.98, "background": 0.80}


def _ar1(n: int, phi: float, sigma: float, rng: np.random.Generator,
         n_series: int = 1) -> np.ndarray:
    """Vectorised AR(1): x_t = phi*x_{t-1} + eps. Returns (n, n_series)."""
    eps = rng.normal(0.0, sigma, size=(n, n_series))
    x = np.empty((n, n_series))
    x[0] = eps[0]
    for t in range(1, n):                      # loop over time only (fast)
        x[t] = phi * x[t - 1] + eps[t]
    return x


def _station_frame(name: str, stype: str, idx: pd.DatetimeIndex,
                   rng: np.random.Generator) -> pd.DataFrame:
    n = len(idx)
    hour = idx.hour.to_numpy()
    doy = idx.dayofyear.to_numpy()
    month = idx.month.to_numpy()

    # ---- deterministic seasonal / diurnal signals -----------------------
    # annual phase: coldest ~ Jan (doy~15), warmest ~ Jul (doy~196)
    ann = np.cos(2 * np.pi * (doy - 15) / 365.25)          # +1 winter, -1 summer
    diur = np.cos(2 * np.pi * (hour - 14) / 24)            # +1 ~14:00, -1 ~02:00

    # ---- meteorology -----------------------------------------------------
    TEMP = 12.5 - 14.5 * ann + 5.0 * (-diur) + rng.normal(0, 2.2, n)
    PRES = 1011 + 12 * ann - 0.18 * (TEMP - 12) + rng.normal(0, 3.0, n)
    DEWP = TEMP - (8 + 6 * ann) - rng.gamma(2.0, 1.3, n)   # drier in winter
    WSPM = np.abs(rng.gamma(2.0, 0.9, n) + 0.6 * ann + 0.3)  # windier in winter
    # rain mostly 0, more frequent/heavier in summer
    rain_p = np.clip(0.04 + 0.06 * (-ann), 0.01, 0.14)
    RAIN = np.where(rng.random(n) < rain_p, rng.gamma(1.3, 1.6, n), 0.0)
    # wind direction: NW prevailing in winter, SE in summer
    nw_bias = np.clip(0.5 + 0.4 * ann, 0.1, 0.9)
    wd = np.where(rng.random(n) < nw_bias,
                  rng.choice(["NW", "NNW", "N", "WNW"], n),
                  rng.choice(["SE", "SSE", "S", "ESE"], n))

    # ---- shared "synoptic" stagnation factor (multi-day episodes) -------
    # high value => stagnant air => pollutants accumulate; AR(1) gives the
    # day-to-day persistence that makes weekly lag features informative.
    synoptic = _ar1(n, phi=0.96, sigma=0.22, rng=rng).ravel()
    stagnation = synoptic - 0.45 * (WSPM - WSPM.mean()) / WSPM.std()

    toff = TYPE_OFFSET[stype]
    heating = np.clip(ann, 0, None)        # coal-heating term (Nov-Mar)
    zwind = (WSPM - WSPM.mean()) / WSPM.std()

    def pollutant(base, b_ann, b_diur, b_stag, b_wind, b_loc=0.85, noise=0.05):
        # each pollutant gets its OWN fast AR(1) -> strong hourly persistence
        # (high lag-1 autocorrelation, like the real data), while the shared
        # synoptic + seasonal terms create inter-pollutant correlation and the
        # 24h / 168h echoes.
        local = _ar1(n, phi=0.92, sigma=0.40, rng=rng).ravel()
        latent = (np.log(base)
                  + b_ann * ann + 0.45 * heating
                  + b_diur * diur
                  + b_stag * stagnation
                  - b_wind * zwind
                  + np.log(toff)
                  + b_loc * local
                  + rng.normal(0, noise, n))
        return np.exp(latent)

    PM25 = pollutant(70, 0.30, 0.18, 0.55, 0.20)
    PM10 = PM25 * rng.uniform(1.2, 1.7, n) + 12 * np.clip(
        np.cos(2 * np.pi * (doy - 95) / 365.25), 0, None)        # spring dust
    SO2 = pollutant(14, 0.55, 0.12, 0.35, 0.18)                  # coal -> winter
    NO2 = pollutant(45, 0.30, 0.22, 0.40, 0.22)                  # traffic
    CO = pollutant(900, 0.45, 0.15, 0.45, 0.18)                 # combustion
    # ozone: photochemical -> high summer daytime, anti-correlated with NO2
    o3_local = _ar1(n, phi=0.85, sigma=0.45, rng=rng).ravel()
    O3 = np.clip(np.exp(np.log(55) - 0.45 * ann + 0.55 * diur
                        - 0.30 * (NO2 - NO2.mean()) / NO2.std()
                        + 0.55 * o3_local + rng.normal(0, 0.10, n)), 1, None)

    df = pd.DataFrame({
        "year": idx.year, "month": month, "day": idx.day, "hour": hour,
        "PM2.5": PM25, "PM10": PM10, "SO2": SO2, "NO2": NO2, "CO": CO, "O3": O3,
        "TEMP": TEMP, "PRES": PRES, "DEWP": DEWP, "RAIN": RAIN,
        "wd": wd, "WSPM": WSPM, "station": name,
    })

    # realistic rounding/units
    for c in ["PM2.5", "PM10", "SO2", "NO2", "O3"]:
        df[c] = df[c].round(0)
    df["CO"] = df["CO"].round(0)
    for c in ["TEMP", "PRES", "DEWP", "WSPM"]:
        df[c] = df[c].round(1)
    df["RAIN"] = df["RAIN"].round(1)
    return df


def _inject_missing(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Insert NaN as consecutive blocks (sensor outages), CO worst."""
    rates = {"PM2.5": 0.021, "PM10": 0.022, "SO2": 0.028, "NO2": 0.025,
             "CO": 0.049, "O3": 0.031,
             "TEMP": 0.004, "PRES": 0.004, "DEWP": 0.004,
             "RAIN": 0.004, "WSPM": 0.004, "wd": 0.004}
    n = len(df)
    for col, rate in rates.items():
        target = int(rate * n)
        placed = 0
        while placed < target:
            blk = rng.integers(2, 14)               # 2..13 h outage
            start = rng.integers(0, n - blk)
            df.iloc[start:start + blk, df.columns.get_loc(col)] = np.nan
            placed += blk
    return df


def generate(out_dir: str, seed: int = 42, verbose: bool = True) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(seed)
    idx = pd.date_range(START, END, freq="h")
    paths = []
    for i, (name, stype) in enumerate(STATIONS.items()):
        # independent stream per station for reproducibility
        st_rng = np.random.default_rng(seed + i)
        df = _station_frame(name, stype, idx, st_rng)
        df = _inject_missing(df, st_rng)
        df.insert(0, "No", np.arange(1, len(df) + 1))
        fname = f"PRSA_Data_{name}_20130301-20170228.csv"
        fpath = os.path.join(out_dir, fname)
        df.to_csv(fpath, index=False)
        paths.append(fpath)
        if verbose:
            print(f"  wrote {fname:55s} rows={len(df)}")
    return paths


if __name__ == "__main__":
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(here, "data", "synthetic")
    print(f"Generating synthetic Beijing Multi-Site data -> {out}")
    generate(out)
    print("Done.")
