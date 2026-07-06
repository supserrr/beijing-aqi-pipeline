# Task 1C: Experiment comparison (next-day AQI category, source=real)

_Split: train/val/test = 12180/2616/2616 station-days (70/15/15), strictly temporal by date. Macro-F1 weights all six classes equally, so it reflects minority-class skill; accuracy does not._

| experiment                                 | hyperparameters               |   train acc |   test acc |   macro-F1 | observation                                                               |
|:-------------------------------------------|:------------------------------|------------:|-----------:|-----------:|:--------------------------------------------------------------------------|
| Baseline: persistence (today's category)   | none                          |       0.41  |      0.377 |      0.335 | Tomorrow = today's category; only ~41% right                              |
| Baseline: majority class                   | always 'Unhlth'               |       0.434 |      0.354 |      0.087 | Predicts the most common class; high acc, zero minority recall            |
| Exp1: Logistic regression — lags only      | 5 lag features                |       0.483 |      0.419 |      0.216 | PM2.5 history alone clearly beats persistence                             |
| Exp2: Logistic regression — full features  | 29 features                   |       0.519 |      0.483 |      0.276 | Co-pollutants + weather + calendar add a clear lift                       |
| Exp3: Logistic regression — tuned L2       | L2=0.001                      |       0.518 |      0.488 |      0.296 | Light L2 gives the best-calibrated linear model                           |
| Exp4: k-NN classifier (tuned)              | k=15                          |       0.755 |      0.376 |      0.306 | Overfits (train > test); balanced votes lift macro-F1                     |
| Exp5: MLP classifier (small, h=8)          | hidden=8, lr=0.1, L2=0.0001   |       0.549 |      0.491 |      0.329 | Limited capacity underfits the minority classes                           |
| Exp6: MLP classifier (tuned, h=32)         | hidden=32, lr=0.05, L2=0.0001 |       0.589 |      0.453 |      0.34  | Non-linear model; nonlinearity helps the minority classes                 |
| Exp7: MLP classifier (large, h=64 + L2)    | hidden=64, lr=0.05, L2=0.001  |       0.605 |      0.448 |      0.335 | Extra capacity + L2 gives no further gain                                 |
| Exp8: Logistic regression — class-balanced | L2=0.001, balanced(b=0.75)    |       0.465 |      0.403 |      0.355 | Class weights recover minority recall: best macro-F1, at an accuracy cost |

## Hyper-parameter tuning detail

```
{
  "logreg_l2_val_macroF1": {
    "0.0001": 0.256,
    "0.001": 0.256,
    "0.01": 0.248,
    "0.1": 0.216,
    "1.0": 0.105
  },
  "knn_k_val_macroF1": {
    "15": 0.252,
    "35": 0.234,
    "75": 0.233
  },
  "mlp_val_macroF1": {
    "h16_lr0.1": 0.286,
    "h32_lr0.1": 0.285,
    "h32_lr0.05": 0.301,
    "h64_lr0.05": 0.265
  },
  "balanced_logreg_beta_val_macroF1": {
    "0.5": 0.341,
    "0.75": 0.349,
    "1.0": 0.345
  }
}
```
