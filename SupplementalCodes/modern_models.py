#!/usr/bin/env python3
"""
Modern Model Comparison for K-EmoPhone Phone-Only Pipeline
===========================================================
Compares LightGBM, CatBoost, and a Stacking Ensemble
against the baseline RF/XGBoost results.

Key design: Optuna tunes ONCE globally per label (not per fold),
then the tuned params are used across all LOSO folds.

Usage:
    ./venv/bin/python3.10 modern_models.py
"""

import os
import warnings
import time
import numpy as np
import pandas as pd
import cloudpickle

from sklearn.model_selection import LeaveOneGroupOut, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectFromModel
from sklearn.svm import LinearSVC
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score,
    precision_recall_fscore_support, matthews_corrcoef
)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, StackingClassifier
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier

import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

warnings.filterwarnings('ignore')

# ─── Config ─────────────────────────────────────────────────────────
PATH_INTERMEDIATE = './intermediate'
RANDOM_STATE = 42
LABELS = ['valence', 'arousal', 'stress', 'disturbance']

# ─── Utilities ──────────────────────────────────────────────────────

def load(path):
    with open(path, 'rb') as f:
        return cloudpickle.load(f)

def log(msg):
    from datetime import datetime
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def select_features(X_train, y_train, X_test):
    selector = SelectFromModel(
        estimator=LinearSVC(
            penalty='l1', loss='squared_hinge', dual=False,
            tol=1e-3, C=1e-2, max_iter=5000, random_state=RANDOM_STATE
        ), threshold=1e-5
    )
    selector.fit(X_train.values, y_train)
    mask = selector.get_support()
    cols = X_train.columns[mask]
    return X_train[cols], X_test[cols]

def normalize(X_train, X_test):
    C_bool = X_train.columns[X_train.dtypes == bool]
    C_num = X_train.columns[X_train.dtypes != bool]
    scaler = StandardScaler().fit(X_train[C_num].values)
    X_train_n = pd.DataFrame(
        np.hstack([X_train[C_bool].values, scaler.transform(X_train[C_num].values)]),
        columns=np.concatenate([C_bool, C_num])
    )
    X_test_n = pd.DataFrame(
        np.hstack([X_test[C_bool].values, scaler.transform(X_test[C_num].values)]),
        columns=np.concatenate([C_bool, C_num])
    )
    return X_train_n, X_test_n

def smote_oversample(X_train, y_train):
    from imblearn.over_sampling import SMOTE, SMOTENC
    C_bool = X_train.columns[X_train.dtypes == bool]
    if len(C_bool) > 0:
        M_idx = np.where(np.isin(X_train.columns, C_bool))[0].tolist()
        sampler = SMOTENC(categorical_features=M_idx, random_state=RANDOM_STATE)
    else:
        sampler = SMOTE(random_state=RANDOM_STATE)
    try:
        return sampler.fit_resample(X_train, y_train)
    except Exception:
        return X_train, y_train

# ─── Optuna: Tune ONCE globally per label ───────────────────────────

def tune_lgbm_globally(X, y, n_trials=25):
    """Tune LightGBM using 5-fold stratified CV on the FULL dataset.
    This runs ONCE per label, not per LOSO fold."""
    log(f"    Optuna: tuning LightGBM with {n_trials} trials (5-fold CV)...")

    # Quick feature selection on full data for tuning speed
    selector = SelectFromModel(
        estimator=LinearSVC(
            penalty='l1', loss='squared_hinge', dual=False,
            tol=1e-3, C=1e-2, max_iter=5000, random_state=RANDOM_STATE
        ), threshold=1e-5
    ).fit(X.values, y)
    X_sel = X[X.columns[selector.get_support()]]

    def objective(trial):
        params = {
            'objective': 'binary', 'metric': 'binary_logloss', 'verbosity': -1,
            'random_state': RANDOM_STATE,
            'n_estimators': trial.suggest_int('n_estimators', 100, 800),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2, log=True),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'num_leaves': trial.suggest_int('num_leaves', 16, 128),
            'min_child_samples': trial.suggest_int('min_child_samples', 5, 80),
            'subsample': trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.4, 1.0),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-6, 5.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-6, 5.0, log=True),
        }
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
        scores = []
        for ti, vi in cv.split(X_sel, y):
            m = LGBMClassifier(**params)
            m.fit(X_sel.iloc[ti], y[ti])
            pred = m.predict(X_sel.iloc[vi])
            _, _, f1, _ = precision_recall_fscore_support(y[vi], pred, average='macro', zero_division=0)
            scores.append(f1)
        return np.mean(scores)

    study = optuna.create_study(direction='maximize',
                                 sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best = study.best_params
    best.update({'objective': 'binary', 'metric': 'binary_logloss',
                 'verbosity': -1, 'random_state': RANDOM_STATE})
    log(f"    Optuna: best F1={study.best_value:.3f}, params={best}")
    return best

# ─── LOSO Pipeline ──────────────────────────────────────────────────

def run_loso(label, X, y, groups, model_name, make_model):
    logo = LeaveOneGroupOut()
    results = []
    n_folds = len(np.unique(groups))

    for fold_idx, (train_idx, test_idx) in enumerate(logo.split(X, y, groups)):
        pid = np.unique(groups[test_idx])[0]
        X_tr, y_tr = X.iloc[train_idx].copy(), y[train_idx].copy()
        X_te, y_te = X.iloc[test_idx].copy(), y[test_idx].copy()

        # Feature selection → Normalize → SMOTE
        X_tr, X_te = select_features(X_tr, y_tr, X_te)
        X_tr, X_te = normalize(X_tr, X_te)
        X_tr, y_tr = smote_oversample(X_tr, y_tr)

        # Train
        model = make_model()
        if model_name == 'catboost':
            from sklearn.model_selection import StratifiedShuffleSplit
            try:
                sss = StratifiedShuffleSplit(n_splits=1, test_size=0.15, random_state=RANDOM_STATE)
                ti, vi = next(sss.split(X_tr, y_tr))
                if isinstance(X_tr, pd.DataFrame):
                    model.fit(X_tr.iloc[ti], y_tr[ti], eval_set=(X_tr.iloc[vi], y_tr[vi]))
                else:
                    model.fit(X_tr[ti], y_tr[ti], eval_set=(X_tr[vi], y_tr[vi]))
            except Exception:
                model.fit(X_tr, y_tr)
        else:
            model.fit(X_tr, y_tr)

        y_pred = model.predict(X_te)
        acc = accuracy_score(y_te, y_pred)
        bac = balanced_accuracy_score(y_te, y_pred)
        _, _, f1, _ = precision_recall_fscore_support(y_te, y_pred, average='macro', zero_division=0)
        mcc = matthews_corrcoef(y_te, y_pred)

        results.append({
            'label': label, 'model': model_name, 'pid': pid,
            'acc': acc, 'bac': bac, 'f1_macro': f1, 'mcc': mcc
        })

        if (fold_idx + 1) % 10 == 0 or fold_idx == n_folds - 1:
            log(f"    {model_name}: fold {fold_idx+1}/{n_folds} done (pid={pid}, f1={f1:.3f})")

    return results

def load_baseline_results():
    DIR_EVAL = os.path.join(PATH_INTERMEDIATE, 'eval')
    results = []
    for l in LABELS:
        dir_l = os.path.join(DIR_EVAL, l)
        if not os.path.exists(dir_l):
            continue
        for f in os.listdir(dir_l):
            if not f.endswith('.pkl'):
                continue
            model, pid = f[:f.index('.pkl')].split('#')
            res = load(os.path.join(dir_l, f))
            y_test = res.y_test
            y_pred = res.estimator.predict(res.X_test)
            acc = accuracy_score(y_test, y_pred)
            bac = balanced_accuracy_score(y_test, y_pred)
            _, _, f1, _ = precision_recall_fscore_support(y_test, y_pred, average='macro', zero_division=0)
            mcc = matthews_corrcoef(y_test, y_pred)
            results.append({'label': l, 'model': model, 'pid': pid,
                            'acc': acc, 'bac': bac, 'f1_macro': f1, 'mcc': mcc})
    return results

# ─── Main ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    all_results = []

    log("Loading baseline results...")
    all_results.extend(load_baseline_results())
    log(f"Loaded {len(all_results)} baseline results.\n")

    total_start = time.time()

    for label in LABELS:
        log(f"{'='*60}")
        log(f"  LABEL: {label.upper()}")
        log(f"{'='*60}")

        X, y, groups, t, _ = load(os.path.join(PATH_INTERMEDIATE, f'{label}.pkl'))
        log(f"  Samples={len(y)}, Features={len(X.columns)}")

        # ── 1. LightGBM + Optuna (tune ONCE, then LOSO) ──
        log(f"\n  ── LightGBM + Optuna ──")
        t0 = time.time()
        best_params = tune_lgbm_globally(X, y, n_trials=25)
        log(f"    Tuning done in {time.time()-t0:.1f}s. Running LOSO...")

        r = run_loso(label, X, y, groups, 'lgbm_optuna',
                     lambda: LGBMClassifier(**best_params))
        all_results.extend(r)
        f1s = [x['f1_macro'] for x in r]
        log(f"  ✅ lgbm_optuna: F1={np.mean(f1s):.3f}±{np.std(f1s):.3f} ({time.time()-t0:.1f}s)")

        # ── 2. CatBoost ──
        log(f"\n  ── CatBoost ──")
        t0 = time.time()
        r = run_loso(label, X, y, groups, 'catboost',
                     lambda: CatBoostClassifier(
                         iterations=500, learning_rate=0.05, depth=7,
                         l2_leaf_reg=3, random_seed=RANDOM_STATE, verbose=0,
                         auto_class_weights='Balanced', early_stopping_rounds=30))
        all_results.extend(r)
        f1s = [x['f1_macro'] for x in r]
        log(f"  ✅ catboost: F1={np.mean(f1s):.3f}±{np.std(f1s):.3f} ({time.time()-t0:.1f}s)")

        # ── 3. Stacking Ensemble ──
        log(f"\n  ── Stacking Ensemble ──")
        t0 = time.time()
        r = run_loso(label, X, y, groups, 'stacking',
                     lambda: StackingClassifier(
                         estimators=[
                             ('rf', RandomForestClassifier(n_estimators=150, random_state=RANDOM_STATE)),
                             ('xgb', XGBClassifier(n_estimators=200, learning_rate=0.05, max_depth=6,
                                                    random_state=RANDOM_STATE, verbosity=0,
                                                    eval_metric='logloss')),
                             ('lgbm', LGBMClassifier(n_estimators=200, learning_rate=0.05,
                                                      max_depth=7, random_state=RANDOM_STATE, verbosity=-1)),
                         ],
                         final_estimator=LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
                         cv=3, stack_method='predict_proba', n_jobs=1))
        all_results.extend(r)
        f1s = [x['f1_macro'] for x in r]
        log(f"  ✅ stacking: F1={np.mean(f1s):.3f}±{np.std(f1s):.3f} ({time.time()-t0:.1f}s)")

    total_elapsed = time.time() - total_start
    log(f"\nTotal time: {total_elapsed/60:.1f} min")

    # ─── Results ────────────────────────────────────────────────────
    df = pd.DataFrame(all_results)
    summary = df.groupby(['label', 'model']).agg(
        acc_mean=('acc', 'mean'), acc_std=('acc', 'std'),
        bac_mean=('bac', 'mean'), bac_std=('bac', 'std'),
        f1_mean=('f1_macro', 'mean'), f1_std=('f1_macro', 'std'),
        mcc_mean=('mcc', 'mean'), mcc_std=('mcc', 'std'),
    ).reset_index()

    ORDER = ['dummy', 'rf_ns', 'rf_os', 'xgb_ns', 'xgb_os',
             'lgbm_optuna', 'catboost', 'stacking']
    NAMES = {
        'dummy': 'Dummy (baseline)',
        'rf_ns': 'Random Forest',
        'rf_os': 'RF + SMOTE',
        'xgb_ns': 'XGBoost',
        'xgb_os': 'XGB + SMOTE',
        'lgbm_optuna': '⭐ LightGBM+Optuna',
        'catboost': '⭐ CatBoost',
        'stacking': '⭐ Stacking Ensemble',
    }

    print("\n" + "=" * 80)
    print("  FULL COMPARISON: Baseline vs Modern Models (LOSO Cross-Validation)")
    print("=" * 80)

    for label in LABELS:
        sub = summary[summary['label'] == label].copy()
        sub['order'] = sub['model'].map({m: i for i, m in enumerate(ORDER)})
        sub = sub.sort_values('order')

        print(f"\n  {'─'*72}")
        print(f"  {label.upper()}")
        print(f"  {'─'*72}")
        print(f"  {'Model':<24} {'Accuracy':>14} {'Bal.Acc':>14} {'F1 Macro':>14} {'MCC':>10}")
        print(f"  {'─'*72}")
        for _, row in sub.iterrows():
            name = NAMES.get(row['model'], row['model'])
            print(f"  {name:<24} "
                  f"{row['acc_mean']:.3f}±{row['acc_std']:.3f}  "
                  f"{row['bac_mean']:.3f}±{row['bac_std']:.3f}  "
                  f"{row['f1_mean']:.3f}±{row['f1_std']:.3f}  "
                  f"{row['mcc_mean']:+.3f}")

    # Best per label
    print(f"\n{'='*80}")
    print("  BEST MODEL PER LABEL")
    print(f"{'='*80}")
    for label in LABELS:
        sub = summary[summary['label'] == label]
        best = sub.loc[sub['f1_mean'].idxmax()]
        print(f"  {label.upper():>14}: {NAMES.get(best['model'], best['model']):<24} "
              f"F1={best['f1_mean']:.3f}  Acc={best['acc_mean']:.3f}")

    # Improvement
    print(f"\n{'='*80}")
    print("  IMPROVEMENT OVER BEST BASELINE")
    print(f"{'='*80}")
    base_set = {'dummy', 'rf_ns', 'rf_os', 'xgb_ns', 'xgb_os'}
    new_set = {'lgbm_optuna', 'catboost', 'stacking'}
    for label in LABELS:
        sub = summary[summary['label'] == label]
        best_b = sub[sub['model'].isin(base_set)]['f1_mean'].max()
        best_n = sub[sub['model'].isin(new_set)]
        best_nr = best_n.loc[best_n['f1_mean'].idxmax()]
        imp = best_nr['f1_mean'] - best_b
        print(f"  {label.upper():>14}: {NAMES.get(best_nr['model']):<24} "
              f"F1 {best_b:.3f} → {best_nr['f1_mean']:.3f} "
              f"({'+'if imp>=0 else ''}{imp:.3f}, {imp/best_b*100:+.1f}%)")
    print()
