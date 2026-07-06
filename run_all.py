#!/usr/bin/env python3
"""
run_all.py — run the entire pipeline end-to-end, in order.

Reproduces every figure, table, trained model, database, API demo and
forecast from scratch. Idempotent: re-run any time. If data/raw/ contains the real
Beijing CSVs they are used automatically; otherwise a synthetic fixture is
generated on first use.

    python run_all.py
"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))

STEPS = [
    ("Task 1A — EDA",                       "src/eda.py"),
    ("Task 1B — analytical questions",      "src/analytical_questions.py"),
    ("Task 1C — model training & tuning",   "src/train_model.py"),
    ("Task 2  — build databases + queries", "db/build_databases.py"),
    ("Task 3  — CRUD demo (both DBs)",      "api/demo_crud.py"),
    ("Task 4  — forecast script",           "forecast/forecast.py"),
]


def main():
    print("Beijing Air-Quality pipeline — full run\n")
    for title, script in STEPS:
        print(f"{'=' * 72}\n> {title}   ({script})\n{'=' * 72}")
        t0 = time.time()
        result = subprocess.run([sys.executable, os.path.join(ROOT, script)],
                                cwd=ROOT)
        if result.returncode != 0:
            print(f"\nFAILED at: {script}")
            sys.exit(1)
        print(f"  done in {time.time() - t0:.1f}s\n")

    print("All steps complete.")
    print("Figures and tables are in outputs/; the trained model is in models/.")
    print("The written report (Formative1_Report.pdf) is a separate deliverable, "
          "submitted alongside this repository rather than stored in it.")


if __name__ == "__main__":
    main()
