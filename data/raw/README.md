# Real data

The 12 `PRSA_Data_<Station>_20130301-20170228.csv` files of the **Beijing
Multi-Site Air-Quality** dataset are **already committed in this folder**, so the
repository reproduces every number, figure, and table on a fresh clone with no
extra download step.

Source / attribution:

- Kaggle: https://www.kaggle.com/datasets/sid321axn/beijing-multisite-airquality-data-set
- UCI (original): https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data

The data loader (`src/data_loader.py`) **prefers the files in this directory**,
so every script runs on the real data automatically. If the folder is ever
emptied, the pipeline falls back to an auto-generated synthetic stand-in with the
identical schema (see `src/generate_synthetic.py`), so it still runs out of the box.
