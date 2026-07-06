# Task 4 — Forecast script output

Pipeline: fetch (API) -> preprocess (daily Task-1 features) -> load classifier -> predict next-day AQI category.

```json
{
  "station": "Aotizhongxin",
  "deployed_model": "Exp5: MLP classifier (small, h=8)",
  "data_source": "real",
  "fetched_records": 4801,
  "daily_days_built": 192,
  "today_category": "Moderate",
  "backtest_last_90d_accuracy": 0.4,
  "forecast_date": "2017-03-01",
  "forecast_next_day_category": "Moderate",
  "forecast_confidence": 0.397,
  "top3_class_probabilities": {
    "Moderate": 0.397,
    "Unhealthy": 0.211,
    "Good": 0.196
  }
}
```
