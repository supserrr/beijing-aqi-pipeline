# Beijing Air-Quality Time-Series ML Pipeline

End-to-end machine learning pipeline on the Beijing Multi-Site Air-Quality
dataset (from Kaggle): 12 monitoring stations, hourly readings from
2013-03-01 to 2017-02-28, six pollutants and six meteorological variables.
The modelling target is the **next day's** PM2.5 AQI category (six EPA health bands).

Built for the assignment *Formative 1: Building a Pipeline for Time-Series
Data*. It covers all four tasks: preprocessing and EDA with a tuned model, the
MySQL and MongoDB design, a CRUD/query API over both databases, and a
consolidated forecast script.

> **Data note.** The real Beijing Multi-Site Air-Quality dataset is included in
> `data/raw/` (12 station CSVs, ~32 MB), so every number, figure, and table in
> the report reproduces directly from the committed data on a fresh clone. A
> faithful synthetic generator (`src/generate_synthetic.py`) is also provided as
> a fallback: if the raw CSVs are ever absent, `src/data_loader.py` regenerates
> an identical-schema stand-in automatically, so the pipeline always runs out of
> the box.

---

## Repository structure

```
beijing-aqi-pipeline/
├── src/                      # Task 1: preprocessing, EDA, modelling
│   ├── generate_synthetic.py #   faithful synthetic fixture generator
│   ├── data_loader.py        #   real-or-synthetic loader (real wins)
│   ├── preprocessing.py      #   clean · impute · cap · lag/MA features · daily AQI-class builder
│   ├── eda.py                #   1A: EDA figures + summary
│   ├── analytical_questions.py #  1B: 6 questions (2 use lag/MA)
│   └── train_model.py        #   1C: next-day AQI classification — logistic/kNN/MLP (10 experiments) + diagnostics
├── sql/                      # Task 2: relational design
│   ├── schema_mysql.sql      #   MySQL DDL (3NF, 4 tables)
│   ├── queries_mysql.sql     #   5 demo queries (incl. latest + date range)
│   ├── erd.dot / erd.mermaid #   Entity-Relationship Diagram (source)
├── mongo/                    # Task 2: document design
│   ├── collection_design.md  #   embedded-document design + indexes
│   └── sample_documents.json
├── db/build_databases.py     # Task 2: loads both DBs, runs queries, saves results
├── api/                      # Task 3: FastAPI service
│   ├── repositories.py       #   shared, framework-free CRUD/query logic
│   ├── main.py               #   FastAPI app (MySQL + MongoDB)
│   └── demo_crud.py          #   offline demo of every endpoint (both DBs)
├── forecast/forecast.py      # Task 4: fetch -> preprocess -> load model -> predict
├── models/                   # trained model + metadata
├── outputs/figures|tables/   # all generated figures + result tables
├── docker-compose.yml        # MySQL + MongoDB + loader + API (one command)
├── Dockerfile
├── run_all.py                # reproduce the entire pipeline end-to-end
└── requirements.txt
```

---

## Quickstart

```bash
pip install -r requirements.txt        # numpy, pandas, matplotlib, seaborn

# ---- Task 1: EDA, analytical questions, model ----
python src/eda.py                      # -> outputs/figures + eda_summary.json
python src/analytical_questions.py     # -> 6 question figures + interpretations
python src/train_model.py              # -> 10-experiment table + diagnostics + trained model

# ---- Task 2: build both databases + run all queries ----
python db/build_databases.py           # -> sql_query_results.md, mongo_query_results.md
#   (uses a SQLite mirror + mongomock so it runs with no DB servers;
#    sql/schema_mysql.sql is the canonical MySQL DDL.)

# ---- Task 3: API ----
python api/demo_crud.py                # offline: exercises all endpoints, both DBs
# or serve for real:
#   pip install fastapi uvicorn pymysql pymongo
#   uvicorn api.main:app --reload      # docs at http://localhost:8000/docs

# ---- Task 4: forecast ----
python forecast/forecast.py --station Aotizhongxin       # offline demo
# API_URL=http://localhost:8000 python forecast/forecast.py --station Aotizhongxin
```

---

## Run against real MySQL + MongoDB (Docker)

The commands above run with no servers (SQLite mirror plus in-memory Mongo). To
exercise the real databases, which are the canonical Task 2/3 implementation, use
Docker:

```bash
docker compose up --build
```

This starts MySQL 8 and MongoDB 7, creates the schema from `sql/schema_mysql.sql`,
loads the data into both via `db/load_to_servers.py`, and serves the FastAPI app
at http://localhost:8000/docs. For example:

```bash
# live forecast against the running API
API_URL=http://localhost:8000 python forecast/forecast.py --station Aotizhongxin

# query MySQL directly
docker compose exec mysql mysql -uroot -pbeijing beijing_air \
  -e "SELECT s.station_name, MAX(p.ts) FROM pollutant_readings p \
      JOIN stations s USING(station_id) GROUP BY s.station_name;"
```

`SAMPLE_MONTHS=6 docker compose up --build` loads only the last 6 months for a
quick demo; `docker compose down -v` stops everything and wipes the DB volumes.

---

## Results (Task 1C: next-day AQI-category classification)

The modelling task is to predict the **next day's** PM2.5 AQI category (six EPA
bands, Good → Hazardous), pooling all 12 stations into ~17,500 station-days. Strict
temporal split by date (70/15/15), tuned on the validation window, scored once on
the held-out test window. Ten experiments span three model families plus two
baselines (full table, with per-run observations, in
[`outputs/tables/experiment_table.md`](outputs/tables/experiment_table.md)).

| Experiment | Hyper-params | test acc | macro-F1 |
|---|---|---|---|
| Persistence (today's category) | none | 0.38 | 0.34 |
| Majority class | always 'Unhealthy' | 0.35 | 0.09 |
| Logistic regression (lags only) | 5 features | 0.42 | 0.22 |
| Logistic regression (full) | 29 features | 0.48 | 0.28 |
| Logistic regression (tuned L2) | L2 = 1e-3 | 0.49 | 0.30 |
| k-NN classifier (tuned) | k = 15 | 0.38 | 0.31 |
| **MLP classifier (best acc, deployed)** | **h = 8, lr = 0.1, L2 = 1e-4** | **0.49** | 0.33 |
| Logistic (class-balanced) | L2 = 1e-3, β = 0.75 | 0.40 | **0.36** |

Every learned model except k-NN beats the 0.38 persistence baseline on accuracy. The deployed forecaster is a
from-scratch MLP with the best test accuracy (≈ 0.49, macro-AUC ≈ 0.77); a
class-balanced logistic model reaches the best macro-F1 (≈ 0.36) by recovering
minority-class recall, at an accuracy cost. Adding same-day co-pollutants and the
weekly-MA deviation lifts the linear models from ≈ 0.46 to ≈ 0.49 accuracy, while
k-NN over-fits (train ≈ 0.76 / test ≈ 0.38). The confusion matrix, ROC and
precision-recall curves (`outputs/figures/clf_*.png`) show the model is strong on the
extreme bands but limited by class imbalance on the rare middle category. The forecast
script predicts the next day's category with class probabilities and backtests over
the recent window.

---

## Design notes

- The hourly series is aggregated to per-station daily means and labelled with EPA
  AQI categories; the target is the **next** day's category. Features are strictly
  causal — daily PM2.5 lags {today,1,2,3,7}, 7/30-day rolling mean & std, the
  deviation of today's PM2.5 from its weekly mean, same-day co-pollutants
  (PM10/SO2/NO2/CO/O3, with 1-day lags of PM10/NO2/CO), same-day weather, and the
  (known) calendar of the target day — so there is no look-ahead
  leakage. Imputation runs per station before feature construction, and a
  conservative per-station Tukey fence (Q3 + 3·IQR) caps extreme PM2.5/wind-speed
  spikes (< 1% of readings).
- Modelling compares three families — multinomial logistic regression (including a
  class-balanced variant), instance-based k-NN, and a from-scratch MLP classifier —
  against persistence and majority-class baselines, judged on macro-F1 as well as
  accuracy, with confusion-matrix, ROC/AUC, precision-recall and bias–variance
  diagnostics. The report adds a literature review
  with 13 IEEE-cited sources, methodology, discussion, and conclusion sections.
- The relational schema is 3NF, with two dimension tables
  (`stations`, `wind_directions`) and two fact tables that share the
  `(station_id, ts)` grain. MongoDB embeds one document per station-hour for
  single-lookup reads. Both are queried with real results in `outputs/tables/`.
- The SQL and Mongo CRUD operations share one repository layer. The SQL repo is
  placeholder-parameterized (`%s` for MySQL, `?` for SQLite), so the same code
  runs in production and in the offline demo.
- All models are implemented in NumPy, so the whole pipeline runs with just
  numpy, pandas, matplotlib, and seaborn (no heavy ML dependencies).

---

## Deliverables

- Report: `Formative1_Report.pdf` (editable `.docx`) — submitted separately
  alongside this repository, not stored inside it. It documents all four tasks
  with a literature review, methodology, results, discussion, and references.
- Databases: `sql/schema_mysql.sql`, `mongo/collection_design.md`, and the query
  results in `outputs/tables/`.
- API: `api/main.py` (FastAPI) plus the `api/demo_crud.py` transcript.
- Forecast: `forecast/forecast.py`.

## Team contributions (Group 8)

Each of the four members owned one of the assignment's four tasks end to end.

| Member | Task owned |
|---|---|
| **Gaju Keane** | Task 1: preprocessing, EDA, analytical questions, and the next-day AQI classification model (tuning & diagnostics) |
| **Joella Teta** | Task 2: relational (MySQL) + MongoDB schema design, ERD, and the demonstration queries |
| **Serein Byiringiro Shima** | Task 3: FastAPI CRUD + time-series query endpoints for both databases |
| **Henry Christian Parfait UHIRIWE** | Task 4: consolidated next-day forecast script |

Shared: dataset selection, repository structure, literature review, report, and integration.

## Data source
Beijing Multi-Site Air-Quality Data, from Kaggle.
<https://www.kaggle.com/datasets/sid321axn/beijing-multisite-airquality-data-set>
