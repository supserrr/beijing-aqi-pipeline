# Parfait Christian Henry UHIRIWE — Task 4: Consolidated Forecast

You own `forecast/`, `run_all.py`, the backtest figure, and the forecast demo output. You commit **last** — your script consumes the model (Gaju) via the API (Shima), so everything else must be merged first.

Copy this folder's contents into the repo root, keeping the same relative paths.

## Commits (in this exact order)

### Commit 1 — forecast script
```bash
git add forecast/forecast.py
git commit -m "Add consolidated forecast: fetch, preprocess, load model, predict next-day AQI"
```

### Commit 2 — forecast outputs
```bash
git add outputs/figures/4_forecast_backtest.png outputs/tables/forecast_demo.md
git commit -m "Add forecast demo transcript and recent-window backtest figure"
```

### Commit 3 — end-to-end runner
```bash
git add run_all.py
git commit -m "Add run_all.py to reproduce the entire pipeline end to end"
```

## Verify your part runs

```bash
python forecast/forecast.py --station Aotizhongxin        # offline demo
# against the live API (after docker compose up):
API_URL=http://localhost:8000 python forecast/forecast.py --station Aotizhongxin
python run_all.py                                          # full pipeline
```
