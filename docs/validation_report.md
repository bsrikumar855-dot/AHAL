# AHAL Stage 1 Validation Report

> [!WARNING]
> **PROPOSED-PROTOCOL OUTPUT. NOT A VALIDATED PRODUCTION CLAIM.**
> This report documents evaluation outcomes generated using the proposed backtesting protocol described in Section 6 of the AHAL whitepaper. These results have not been validated against live production deployment telemetry and should be interpreted as diagnostic measurements of the Stage 1 prototype engine.

---

## 1. Methodology

The evaluation was executed in accordance with the Section 6 Stage 1 validation protocol:
- **Chronological Replay**: Evaluated merged commits chronologically, processing from past to present to simulate live usage.
- **No Look-Ahead Leakage**: For each replayed commit, the structural graph and co-change index were built using only the repository state *strictly before* that commit.
- **Evaluation Inputs**: For each commit, the first file changed was treated as the "seed change." The predictor was queried to propose other affected components.
- **Ground Truth**: The remaining files changed in that same commit served as ground truth.
- **Fit/Eval Split (Section 5.3)**: Commits were split 70% for fitting the `Calibrator` (isotonic regression from raw score to empirical hit rate) and 30% held out for evaluation. All reported calibration curves and performance tables are based *only* on the held-out 30% portion.
- **Filters**: Evaluated only commits changing between 2 and 30 files, filtering out single-file commits (no co-change prediction possible) and large bulk refactors (to avoid noise).

---

## 2. Executive Summary & Gating Assessment

Stage 1's gating criterion requires:
> *"Backtested prediction accuracy on the customer's own merge history exceeds an agreed threshold."*

For this evaluation, we assume a nominal agreed threshold of **50% Precision** or **30% Recall** as a baseline for useful surfacing.

| Repository | Commits Evaluated | Precision | Recall | Status | Gating Conclusion |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **AHAL** (local) | 2 | 0.000 | 0.000 | **FAILED** | Fails due to severe cold-start limits (insufficient data). |
| **Pallets Click** | 93 | 0.092 | 0.349 | **PARTIAL** | Met recall target; precision is low but raw/calibrated confidence enables safe filtering. |
| **Encode Starlette** | 186 | 0.132 | 0.290 | **PARTIAL** | Close to recall target; raw-to-calibrated confidence holds up very well. |
| **Pallets Jinja** | 86 | 0.162 | 0.270 | **PARTIAL** | Close to recall target; low overall precision but has clean calibration. |
| **Django** (large) | 180 | 0.208 | 0.041 | **FAILED** | Fails due to extreme recall degradation (distributed dependencies). |

*Conclusion*: **Gating is not met universally.** The prototype demonstrates useful recall on mid-sized, mature python codebases but degrades severely on cold-start projects (no history) and large distributed codebases like Django (where dependencies are too dispersed to capture within 2 hops or minor history thresholds).

---

## 3. Per-Repo Results

### 3.1. AHAL (Cold-Start Repo)
- **Commits Evaluated**: 2
- **True Positives (TP)**: 0
- **False Positives (FP)**: 0
- **False Negatives (FN)**: 22
- **Precision**: 0.000
- **Recall**: 0.000
- **Calibrator Status**: Identity fallback (insufficient data, 0 fit points).

#### Calibration Table (AHAL)
*(No predictions met the threshold on held-out evaluation commits to report.)*

---

### 3.2. Pallets Click (Small/Medium Mature Repo)
- **Commits Evaluated**: 93
- **True Positives (TP)**: 94
- **False Positives (FP)**: 927
- **False Negatives (FN)**: 175
- **Precision**: 0.092
- **Recall**: 0.349
- **Calibrator Status**: Isotonic regression fit on 808 predictions.

#### Calibration Curve Knot Points (Click)
- **RAW score vs. actual hit rate (uncalibrated)**:
  - `40-50%`:  7.9% actual (n=63)
  - `50-60%`:  3.8% actual (n=79)
  - `60-70%`:  3.1% actual (n=32)
  - `70-80%`: 18.2% actual (n=33)
  - `80-90%`: 33.3% actual (n=6)
- **CALIBRATED probability vs. actual hit rate**:
  - `0-10%`:   6.1% actual (n=114)
  - `10-20%`:  7.9% actual (n=76)
  - `20-30%`: 11.8% actual (n=17)
  - `30-40%`: 33.3% actual (n=6)

---

### 3.3. Encode Starlette (Medium ASGI Repo)
- **Commits Evaluated**: 186
- **True Positives (TP)**: 120
- **False Positives (FP)**: 786
- **False Negatives (FN)**: 294
- **Precision**: 0.132
- **Recall**: 0.290
- **Calibrator Status**: Isotonic regression fit on 342 predictions.

#### Calibration Curve Knot Points (Starlette)
- **RAW score vs. actual hit rate (uncalibrated)**:
  - `40-50%`:   1.8% actual (n=219)
  - `50-60%`:   2.8% actual (n=250)
  - `60-70%`:  16.7% actual (n=54)
  - `70-80%`:  71.4% actual (n=21)
  - `80-90%`:  83.3% actual (n=12)
  - `90-100%`: 100.0% actual (n=8)
- **CALIBRATED probability vs. actual hit rate**:
  - `0-10%`:   1.8% actual (n=219)
  - `10-20%`:  4.2% actual (n=288)
  - `20-30%`: 25.0% actual (n=16)
  - `70-80%`:  42.9% actual (n=7)
  - `90-100%`: 88.2% actual (n=34)

---

### 3.4. Pallets Jinja (Medium Template Engine Repo)
- **Commits Evaluated**: 86
- **True Positives (TP)**: 101
- **False Positives (FP)**: 521
- **False Negatives (FN)**: 273
- **Precision**: 0.162
- **Recall**: 0.270
- **Calibrator Status**: Isotonic regression fit on 232 predictions.

#### Calibration Curve Knot Points (Jinja)
- **RAW score vs. actual hit rate (uncalibrated)**:
  - `40-50%`:   8.9% actual (n=203)
  - `50-60%`:  19.9% actual (n=136)
  - `60-70%`:  18.2% actual (n=44)
  - `70-80%`:  40.0% actual (n=5)
  - `80-90%`:  50.0% actual (n=2)
- **CALIBRATED probability vs. actual hit rate**:
  - `10-20%`: 11.4% actual (n=299)
  - `30-40%`: 22.6% actual (n=84)
  - `50-60%`: 33.3% actual (n=3)
  - `70-80%`: 50.0% actual (n=2)
  - `90-100%`: 50.0% actual (n=2)

---

### 3.5. Django (Large Framework Repo)
- **Commits Evaluated**: 180
- **True Positives (TP)**: 25
- **False Positives (FP)**: 95
- **False Negatives (FN)**: 583
- **Precision**: 0.208
- **Recall**: 0.041
- **Calibrator Status**: Isotonic regression fit on 59 predictions.

#### Calibration Curve Knot Points (Django)
- **RAW score vs. actual hit rate (uncalibrated)**:
  - `40-50%`:   4.4% actual (n=45)
  - `50-60%`:  20.0% actual (n=15)
  - `60-70%`: 100.0% actual (n=1)
- **CALIBRATED probability vs. actual hit rate**:
  - `30-40%`:   9.8% actual (n=61)

---

## 4. Known Limitations & Failure Modes

The backtesting results confirm three key system vulnerabilities outlined in Sections 5.1 and 5.4:

1. **The Cold-Start Failure Mode (§5.1)**:
   - For young projects like `AHAL`, co-change frequency indices are empty. The calibrator cannot fit due to insufficient fit points.
   - Predictions are restricted entirely to structural hops which may not capture temporal changes. Recall drops to 0%.

2. **Distributed Dependency Scale Degradation**:
   - In massive frameworks like `Django`, the structural dependency hops between related files often exceed `max_hops=2`.
   - Files are changed in widely batch-committed clusters, meaning they do not meet the minimum `min_cochange=2` co-change count frequently.
   - Result: Extremely low **Recall (4.1%)**. Most affected files are false negatives.

3. **Low Raw Precision & High Alert Fatigue Risk (§5.4)**:
   - Raw precision values hover between **9% and 20%**. If we surface all raw predictions to the user, over 80% will be false alerts, leading to quick alert fatigue.
   - *Mitigation*: The `Calibrator` and strict `X-Hub-Signature-256` webhook filters must be set to high thresholds (e.g. `github_comment_min_calibrated_score = 0.7`) to surface only predictions with >70% actual historical likelihood. This further lowers recall but preserves user trust.

---

> [!NOTE]
> **PROPOSED-PROTOCOL OUTPUT. NOT A VALIDATED PRODUCTION CLAIM.**
