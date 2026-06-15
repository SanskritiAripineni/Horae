"""
Paper-oriented StudentLife validation analysis.

This script builds on evaluate_studentlife.py and reports construct-validity
evidence for the behavioral sensing pipeline:

1. Pattern-specific alignment with self-report.
2. Coverage-filtered pattern alignment.
3. Within-person pattern comparisons.
4. Simple ablations against weaker baselines.
5. Marker coverage/missingness.

The goal is not stress prediction accuracy. Stress/PAM labels are used as
external signals to sanity-check whether coherent behavioral states correspond
to meaningful lived variation.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from scipy import stats

from evaluate_studentlife import (
    load_pam_per_day,
    load_stress_per_day,
    run_pid,
)
from layer1 import MARKER_SPECS
from layer2 import COHERENCE_RULES
from studentlife_adapter import list_participants


RESULTS_DIR = Path(__file__).resolve().parent / "results"
RUN_DATE = date.today().isoformat()
BOOTSTRAP_REPS = 1000
RNG_SEED = 20260615

np.seterr(over="warn", divide="warn", invalid="warn", under="ignore")


def _pattern_names(value) -> set[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return set()
    text = str(value).strip()
    if not text:
        return set()
    return {part for part in text.split("|") if part}


def _cohen_d(a: pd.Series, b: pd.Series) -> float:
    a = pd.to_numeric(a, errors="coerce").dropna()
    b = pd.to_numeric(b, errors="coerce").dropna()
    if len(a) < 2 or len(b) < 2:
        return np.nan
    pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0)
    if pooled <= 0:
        return np.nan
    return float((a.mean() - b.mean()) / pooled)


def _welch_p(a: pd.Series, b: pd.Series) -> float:
    a = pd.to_numeric(a, errors="coerce").dropna()
    b = pd.to_numeric(b, errors="coerce").dropna()
    if len(a) < 5 or len(b) < 5:
        return np.nan
    return float(stats.ttest_ind(a, b, equal_var=False).pvalue)


def _spearman(a: pd.Series, b: pd.Series) -> tuple[float, float, int]:
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    mask = a.notna() & b.notna()
    if int(mask.sum()) < 10:
        return np.nan, np.nan, int(mask.sum())
    res = stats.spearmanr(a[mask], b[mask])
    return float(res.statistic), float(res.pvalue), int(mask.sum())


def _cluster_bootstrap_ci(
    df: pd.DataFrame,
    mask_fn: Callable[[pd.DataFrame], pd.Series],
    outcome: str = "stress_severity",
    reps: int = BOOTSTRAP_REPS,
    seed: int = RNG_SEED,
) -> tuple[float, float]:
    usable = df[df[outcome].notna()].copy()
    pids = sorted(usable["pid"].unique())
    if len(pids) < 3:
        return np.nan, np.nan

    by_pid = {pid: sub for pid, sub in usable.groupby("pid")}
    rng = np.random.default_rng(seed)
    diffs: list[float] = []
    for _ in range(reps):
        sampled = rng.choice(pids, size=len(pids), replace=True)
        boot = pd.concat([by_pid[pid] for pid in sampled], ignore_index=True)
        mask = mask_fn(boot)
        yes = boot.loc[mask, outcome].dropna()
        no = boot.loc[~mask, outcome].dropna()
        if len(yes) >= 5 and len(no) >= 5:
            diffs.append(float(yes.mean() - no.mean()))
    if len(diffs) < 20:
        return np.nan, np.nan
    return tuple(np.percentile(diffs, [2.5, 97.5]).astype(float))


def build_joined_daily() -> pd.DataFrame:
    pids = list_participants()
    print(f"[validation] Running pipeline on {len(pids)} participants")
    all_daily = []
    skipped = []
    for pid in pids:
        try:
            with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
                res = run_pid(pid)
        except Exception as exc:
            skipped.append((pid, type(exc).__name__, str(exc)))
            print(f"  {pid}: ERROR {type(exc).__name__}: {exc}")
            continue
        participant_daily = res.get("daily")
        if participant_daily is None or len(participant_daily) == 0:
            print(f"  {pid}: no days")
            continue
        all_daily.append(participant_daily)
        print(
            f"  {pid}: {len(participant_daily)} days, "
            f"warm:{int(participant_daily['warm'].sum())}, "
            f"dev>=1 days:{int((participant_daily['n_dev'] >= 1).sum())}, "
            f"pattern days:{int((participant_daily['n_pat'] >= 1).sum())}"
        )

    daily = pd.concat(all_daily, ignore_index=True) if all_daily else pd.DataFrame()
    if daily.empty:
        raise RuntimeError("StudentLife pipeline produced no daily rows.")
    if skipped:
        print(f"[validation] Skipped {len(skipped)} participants: {skipped}")

    rows = []
    for pid, sub in daily.groupby("pid"):
        stress = load_stress_per_day(pid)
        pam = load_pam_per_day(pid)
        tmp = sub.copy()
        tmp["stress_severity"] = tmp["date"].map(stress)
        tmp["pam_valence"] = tmp["date"].map(
            lambda d: pam.get(d, {}).get("valence") if pam.get(d) else None
        )
        tmp["pam_arousal"] = tmp["date"].map(
            lambda d: pam.get(d, {}).get("arousal") if pam.get(d) else None
        )
        rows.append(tmp)
    df = pd.concat(rows, ignore_index=True)
    df = df[df["warm"]].copy()

    pattern_list = [rule["name"] for rule in COHERENCE_RULES]
    for name in pattern_list:
        df[f"pattern__{name}"] = df["pattern_names"].apply(
            lambda value, n=name: n in _pattern_names(value)
        )

    df["any_pattern"] = df["n_pat"] >= 1
    df["any_deviation"] = df["n_dev"] >= 1

    for rule in COHERENCE_RULES:
        name = rule["name"]
        required = [marker for marker, _direction in rule["required"]]
        cov_cols = [f"cov_{marker}" for marker in required]
        existing = [col for col in cov_cols if col in df.columns]
        if existing:
            df[f"pattern_cov_min__{name}"] = df[existing].min(axis=1)
        else:
            df[f"pattern_cov_min__{name}"] = np.nan
        df[f"pattern_confident__{name}"] = (
            df[f"pattern__{name}"] & (df[f"pattern_cov_min__{name}"] >= 0.45)
        )

    pattern_cov_cols = [f"pattern_cov_min__{rule['name']}" for rule in COHERENCE_RULES]
    df["any_pattern_required_min_cov"] = df[pattern_cov_cols].where(df["any_pattern"]).min(axis=1)
    df["any_confident_pattern"] = df["any_pattern"] & (df["any_pattern_required_min_cov"] >= 0.45)
    return df


def binary_outcome_stats(
    df: pd.DataFrame,
    mask: pd.Series,
    label: str,
    outcome: str = "stress_severity",
    bootstrap: bool = True,
) -> dict:
    usable = df[df[outcome].notna()].copy()
    mask = mask.reindex(usable.index).fillna(False).astype(bool)
    yes = usable.loc[mask, outcome]
    no = usable.loc[~mask, outcome]
    diff = float(yes.mean() - no.mean()) if len(yes) and len(no) else np.nan
    ci_low, ci_high = (np.nan, np.nan)
    if bootstrap:
        marker_col = f"__mask_{abs(hash(label))}"
        usable[marker_col] = mask.values
        ci_low, ci_high = _cluster_bootstrap_ci(
            usable, lambda boot, col=marker_col: boot[col].astype(bool)
        )

    return {
        "label": label,
        "outcome": outcome,
        "n_yes": int(len(yes)),
        "n_no": int(len(no)),
        "mean_yes": float(yes.mean()) if len(yes) else np.nan,
        "mean_no": float(no.mean()) if len(no) else np.nan,
        "diff_yes_minus_no": diff,
        "diff_ci95_low": ci_low,
        "diff_ci95_high": ci_high,
        "welch_p": _welch_p(yes, no),
        "cohen_d": _cohen_d(yes, no),
    }


def pattern_specific_tables(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    conf_rows = []
    for rule in COHERENCE_RULES:
        name = rule["name"]
        rows.append(binary_outcome_stats(df, df[f"pattern__{name}"], name))
        conf_rows.append(
            binary_outcome_stats(
                df,
                df[f"pattern_confident__{name}"],
                f"{name} (required coverage >= 0.45)",
            )
        )
    rows.append(binary_outcome_stats(df, df["any_pattern"], "any coherent pattern"))
    conf_rows.append(
        binary_outcome_stats(
            df,
            df["any_confident_pattern"],
            "any coherent pattern (required coverage >= 0.45)",
        )
    )
    return pd.DataFrame(rows), pd.DataFrame(conf_rows)


def ablation_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = [
        binary_outcome_stats(df, df["any_deviation"], "any deviation", bootstrap=False),
        binary_outcome_stats(df, df["any_pattern"], "any coherent pattern", bootstrap=False),
        binary_outcome_stats(
            df,
            df["any_confident_pattern"],
            "any confident coherent pattern",
            bootstrap=False,
        ),
    ]

    for col in ["n_dev", "n_pat", "risk_index"]:
        r, p, n = _spearman(df[col], df["stress_severity"])
        rows.append({
            "label": col,
            "outcome": "stress_severity",
            "n_yes": n,
            "n_no": np.nan,
            "mean_yes": np.nan,
            "mean_no": np.nan,
            "diff_yes_minus_no": np.nan,
            "diff_ci95_low": np.nan,
            "diff_ci95_high": np.nan,
            "welch_p": p,
            "cohen_d": np.nan,
            "spearman_r": r,
            "spearman_p": p,
            "spearman_n": n,
        })
    return pd.DataFrame(rows)


def within_person_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    masks = {"any coherent pattern": df["any_pattern"]}
    for rule in COHERENCE_RULES:
        name = rule["name"]
        masks[name] = df[f"pattern__{name}"]

    stress_df = df[df["stress_severity"].notna()].copy()
    for label, global_mask in masks.items():
        stress_df["__mask"] = global_mask.reindex(stress_df.index).fillna(False).values
        diffs = []
        for _pid, sub in stress_df.groupby("pid"):
            yes = sub.loc[sub["__mask"], "stress_severity"]
            no = sub.loc[~sub["__mask"], "stress_severity"]
            if len(yes) >= 2 and len(no) >= 2:
                diffs.append(float(yes.mean() - no.mean()))
        n = len(diffs)
        n_positive = int(sum(d > 0 for d in diffs))
        p = float(stats.binomtest(n_positive, n, 0.5).pvalue) if n else np.nan
        rows.append({
            "label": label,
            "n_participants_with_both": n,
            "n_positive": n_positive,
            "percent_positive": 100.0 * n_positive / n if n else np.nan,
            "median_within_person_diff": float(np.median(diffs)) if diffs else np.nan,
            "mean_within_person_diff": float(np.mean(diffs)) if diffs else np.nan,
            "sign_test_p": p,
        })
    return pd.DataFrame(rows)


def marker_coverage_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for marker in MARKER_SPECS:
        col = f"cov_{marker}"
        if col not in df:
            continue
        cov = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        rows.append({
            "marker": marker,
            "domain": MARKER_SPECS[marker]["domain"],
            "mean_coverage": float(cov.mean()),
            "days_any_coverage_pct": float((cov > 0).mean() * 100.0),
            "days_medium_or_high_pct": float((cov >= 0.45).mean() * 100.0),
            "days_high_pct": float((cov >= 0.75).mean() * 100.0),
        })
    return pd.DataFrame(rows)


def fmt_table(df: pd.DataFrame, columns: list[str], n: int | None = None) -> str:
    sub = df[columns].copy()
    if n is not None:
        sub = sub.head(n)

    def fmt_cell(value) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, (float, np.floating)):
            return f"{float(value):.3f}"
        if isinstance(value, (int, np.integer)):
            return str(int(value))
        return str(value)

    headers = [str(col) for col in columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, row in sub.iterrows():
        lines.append("| " + " | ".join(fmt_cell(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def write_outputs(
    df: pd.DataFrame,
    pattern_df: pd.DataFrame,
    confident_pattern_df: pd.DataFrame,
    ablation_df: pd.DataFrame,
    within_df: pd.DataFrame,
    coverage_df: pd.DataFrame,
) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    prefix = f"studentlife_validation_{RUN_DATE}"

    pattern_df.to_csv(RESULTS_DIR / f"{prefix}_patterns.csv", index=False)
    confident_pattern_df.to_csv(RESULTS_DIR / f"{prefix}_coverage_filtered_patterns.csv", index=False)
    ablation_df.to_csv(RESULTS_DIR / f"{prefix}_ablations.csv", index=False)
    within_df.to_csv(RESULTS_DIR / f"{prefix}_within_person.csv", index=False)
    coverage_df.to_csv(RESULTS_DIR / f"{prefix}_marker_coverage.csv", index=False)

    stress_days = int(df["stress_severity"].notna().sum())
    pam_days = int(df["pam_valence"].notna().sum())
    pattern_days = int(df["any_pattern"].sum())
    confident_pattern_days = int(df["any_confident_pattern"].sum())

    best_patterns = pattern_df.sort_values("diff_yes_minus_no", ascending=False)
    best_confident = confident_pattern_df.sort_values("diff_yes_minus_no", ascending=False)

    md = f"""# StudentLife Construct-Validity Analysis ({RUN_DATE})

This analysis evaluates whether coherent behavioral states from the passive
sensing pipeline align with external self-report signals in StudentLife. It is
not a stress-prediction benchmark.

## Dataset Summary

| Quantity | Value |
|---|---:|
| Warm-baseline daily rows | {len(df)} |
| Participants | {df['pid'].nunique()} |
| Days with Stress EMA | {stress_days} |
| Days with PAM EMA | {pam_days} |
| Days with any coherent pattern | {pattern_days} |
| Days with confident coherent pattern | {confident_pattern_days} |

## Pattern-Specific Alignment With Stress

{fmt_table(best_patterns, [
    'label', 'n_yes', 'mean_yes', 'mean_no', 'diff_yes_minus_no',
    'diff_ci95_low', 'diff_ci95_high', 'welch_p', 'cohen_d'
])}

## Coverage-Filtered Pattern Alignment

Pattern days are retained here only when required marker coverage is at least
0.45.

{fmt_table(best_confident, [
    'label', 'n_yes', 'mean_yes', 'mean_no', 'diff_yes_minus_no',
    'diff_ci95_low', 'diff_ci95_high', 'welch_p', 'cohen_d'
])}

## Ablation Against Simpler Signals

{fmt_table(ablation_df, [
    'label', 'n_yes', 'mean_yes', 'mean_no', 'diff_yes_minus_no',
    'welch_p', 'cohen_d', 'spearman_r', 'spearman_p'
])}

## Within-Person Pattern Comparison

For each participant with both pattern and non-pattern stress days, this compares
their own mean stress on pattern days vs their own non-pattern days.

{fmt_table(within_df, [
    'label', 'n_participants_with_both', 'n_positive', 'percent_positive',
    'median_within_person_diff', 'mean_within_person_diff', 'sign_test_p'
])}

## Marker Coverage

{fmt_table(coverage_df, [
    'marker', 'domain', 'mean_coverage', 'days_any_coverage_pct',
    'days_medium_or_high_pct', 'days_high_pct'
])}

## Paper-Ready Interpretation

The strongest defensible claim is that the pipeline produces interpretable
behavioral states that show preliminary external alignment with self-report.
Avoid claiming stress prediction accuracy. The most relevant evidence is whether
coherent pattern days, especially coverage-filtered pattern days, have higher
same-day stress than non-pattern days and whether coherent patterns outperform
simpler ablations such as any deviation or a scalar risk index.
"""
    out_path = RESULTS_DIR / f"{prefix}_summary.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path


def main() -> int:
    df = build_joined_daily()
    pattern_df, confident_pattern_df = pattern_specific_tables(df)
    ablation_df = ablation_table(df)
    within_df = within_person_table(df)
    coverage_df = marker_coverage_table(df)
    out = write_outputs(df, pattern_df, confident_pattern_df, ablation_df, within_df, coverage_df)
    print(f"Wrote summary: {out}")
    print()
    print(out.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
