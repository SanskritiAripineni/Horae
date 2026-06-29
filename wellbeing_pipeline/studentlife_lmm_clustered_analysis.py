from __future__ import annotations

from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tools.sm_exceptions import ConvergenceWarning
import statsmodels.formula.api as smf

import studentlife_validation_analysis as validation


RESULTS_DIR = Path(__file__).resolve().parent / "results"
OUT_PREFIX = "studentlife_lmm_clustered_1f1dfb2"


PREDICTORS = [
    {
        "label": "any_coherent_pattern",
        "column": "any_coherent_pattern",
        "kind": "binary",
        "pooled_label": "Welch diff",
    },
    {
        "label": "confident_coherent_pattern",
        "column": "confident_coherent_pattern",
        "kind": "binary",
        "pooled_label": "Welch diff",
    },
    {
        "label": "risk_index",
        "column": "risk_index",
        "kind": "continuous",
        "pooled_label": "Spearman r",
    },
    {
        "label": "behavioral_withdrawal",
        "column": "behavioral_withdrawal",
        "kind": "binary",
        "pooled_label": "Welch diff",
    },
]


def prepare_daily() -> pd.DataFrame:
    df = validation.build_joined_daily().copy()
    df["participant_id"] = df["pid"].astype(str)
    df["day"] = df["date"]
    df["any_coherent_pattern"] = df["any_pattern"].astype(int)
    df["confident_coherent_pattern"] = df["any_confident_pattern"].astype(int)
    df["behavioral_withdrawal"] = df["pattern__behavioral-withdrawal"].astype(int)
    df["coverage"] = df["any_pattern_required_min_cov"]
    return df


def fit_mixedlm(formula: str, data: pd.DataFrame):
    methods = ["lbfgs", "bfgs", "cg", "powell", "nm"]
    attempts = []
    model = smf.mixedlm(formula, data, groups=data["participant_id"], re_formula="1")
    for method in methods:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ConvergenceWarning)
            warnings.simplefilter("always", RuntimeWarning)
            warnings.simplefilter("always", UserWarning)
            try:
                result = model.fit(reml=False, method=method, maxiter=1000, disp=False)
            except Exception as exc:
                attempts.append(
                    {
                        "method": method,
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "warnings": "; ".join(str(w.message) for w in caught),
                    }
                )
                continue
        attempts.append(
            {
                "method": method,
                "ok": True,
                "converged": bool(getattr(result, "converged", False)),
                "warnings": "; ".join(str(w.message) for w in caught),
            }
        )
        if getattr(result, "converged", False):
            return result, attempts
    return None, attempts


def pooled_binary(df: pd.DataFrame, col: str) -> dict:
    yes = pd.to_numeric(df.loc[df[col].astype(bool), "stress_severity"], errors="coerce").dropna()
    no = pd.to_numeric(df.loc[~df[col].astype(bool), "stress_severity"], errors="coerce").dropna()
    ttest = stats.ttest_ind(yes, no, equal_var=False) if len(yes) >= 5 and len(no) >= 5 else None
    diff = float(yes.mean() - no.mean()) if len(yes) and len(no) else np.nan
    return {
        "pooled_result_type": "Welch diff",
        "pooled_estimate": diff,
        "pooled_p": float(ttest.pvalue) if ttest is not None else np.nan,
        "n_yes": int(len(yes)),
        "n_no": int(len(no)),
        "mean_yes": float(yes.mean()) if len(yes) else np.nan,
        "mean_no": float(no.mean()) if len(no) else np.nan,
    }


def pooled_continuous(df: pd.DataFrame, col: str) -> dict:
    x = pd.to_numeric(df[col], errors="coerce")
    y = pd.to_numeric(df["stress_severity"], errors="coerce")
    mask = x.notna() & y.notna()
    if int(mask.sum()) < 10:
        r = p = np.nan
    else:
        res = stats.spearmanr(x[mask], y[mask])
        r, p = float(res.statistic), float(res.pvalue)
    return {
        "pooled_result_type": "Spearman r",
        "pooled_estimate": r,
        "pooled_p": p,
        "n_yes": np.nan,
        "n_no": np.nan,
        "mean_yes": np.nan,
        "mean_no": np.nan,
    }


def per_participant_spearman(df: pd.DataFrame, col: str) -> dict:
    values = []
    for _pid, sub in df.groupby("participant_id"):
        x = pd.to_numeric(sub[col], errors="coerce")
        y = pd.to_numeric(sub["stress_severity"], errors="coerce")
        mask = x.notna() & y.notna()
        if int(mask.sum()) < 5:
            continue
        if x[mask].nunique() < 2 or y[mask].nunique() < 2:
            continue
        res = stats.spearmanr(x[mask], y[mask])
        if np.isfinite(res.statistic):
            values.append(float(res.statistic))
    return {
        "spearman_median_r": float(np.median(values)) if values else np.nan,
        "spearman_pct_positive": float(np.mean(np.array(values) > 0) * 100.0) if values else np.nan,
        "spearman_n_participants": int(len(values)),
    }


def summarize_lmm(result, null_result, predictor: str, n_obs: int, n_participants: int) -> dict:
    estimate = float(result.params[predictor])
    se = float(result.bse[predictor])
    p = float(result.pvalues[predictor])
    ci_low, ci_high = [float(v) for v in result.conf_int().loc[predictor]]
    random_var = float(result.cov_re.iloc[0, 0]) if result.cov_re.shape else np.nan
    residual_var = float(result.scale)
    denom = random_var + residual_var
    icc = float(random_var / denom) if denom > 0 else np.nan
    lr = float(2.0 * (result.llf - null_result.llf)) if null_result is not None else np.nan
    if np.isfinite(lr) and lr < 0:
        lr = 0.0
    lrt_p = float(stats.chi2.sf(lr, 1)) if np.isfinite(lr) else np.nan
    return {
        "lmm_estimate": estimate,
        "lmm_se": se,
        "lmm_p": p,
        "lmm_ci95_low": ci_low,
        "lmm_ci95_high": ci_high,
        "random_intercept_variance": random_var,
        "icc": icc,
        "n_observations": int(n_obs),
        "n_participants": int(n_participants),
        "lrt_chi2_vs_intercept": lr,
        "lrt_p_vs_intercept": lrt_p,
        "lmm_converged": bool(getattr(result, "converged", False)),
    }


def format_table(df: pd.DataFrame, columns: list[str]) -> str:
    def fmt(value):
        if pd.isna(value):
            return ""
        if isinstance(value, (float, np.floating)):
            if abs(float(value)) < 0.001 and float(value) != 0.0:
                return f"{float(value):.2e}"
            return f"{float(value):.4f}"
        if isinstance(value, (int, np.integer)):
            return str(int(value))
        return str(value)

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in df[columns].iterrows():
        lines.append("| " + " | ".join(fmt(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = prepare_daily()
    stress_df = df[df["stress_severity"].notna()].copy()

    null_result, null_attempts = fit_mixedlm("stress_severity ~ 1", stress_df)
    if null_result is None or not getattr(null_result, "converged", False):
        raise RuntimeError(f"Intercept-only MixedLM failed: {null_attempts}")

    rows = []
    attempts_rows = [{"model": "intercept_only", **attempt} for attempt in null_attempts]
    spearman_rows = []

    for spec in PREDICTORS:
        col = spec["column"]
        if spec["kind"] == "binary":
            pooled = pooled_binary(stress_df, col)
        else:
            pooled = pooled_continuous(stress_df, col)

        model_df = stress_df[["participant_id", "stress_severity", col]].dropna().copy()
        result, attempts = fit_mixedlm(f"stress_severity ~ {col}", model_df)
        attempts_rows.extend({"model": spec["label"], **attempt} for attempt in attempts)

        if result is None or not getattr(result, "converged", False):
            row = {
                "predictor": spec["label"],
                **pooled,
                "lmm_estimate": np.nan,
                "lmm_se": np.nan,
                "lmm_p": np.nan,
                "lmm_ci95_low": np.nan,
                "lmm_ci95_high": np.nan,
                "random_intercept_variance": np.nan,
                "icc": np.nan,
                "n_observations": int(len(model_df)),
                "n_participants": int(model_df["participant_id"].nunique()),
                "lrt_chi2_vs_intercept": np.nan,
                "lrt_p_vs_intercept": np.nan,
                "lmm_converged": False,
            }
        else:
            row = {
                "predictor": spec["label"],
                **pooled,
                **summarize_lmm(
                    result,
                    null_result if len(model_df) == len(stress_df) else None,
                    col,
                    len(model_df),
                    model_df["participant_id"].nunique(),
                ),
            }
        rows.append(row)

        spearman_rows.append(
            {
                "predictor": spec["label"],
                **per_participant_spearman(stress_df, col),
            }
        )

    comparison = pd.DataFrame(rows)
    spearman_df = pd.DataFrame(spearman_rows)
    attempts_df = pd.DataFrame(attempts_rows)

    comparison_path = RESULTS_DIR / f"{OUT_PREFIX}_comparison.csv"
    spearman_path = RESULTS_DIR / f"{OUT_PREFIX}_per_participant_spearman.csv"
    attempts_path = RESULTS_DIR / f"{OUT_PREFIX}_fit_attempts.csv"
    markdown_path = RESULTS_DIR / f"{OUT_PREFIX}_summary.md"

    comparison.to_csv(comparison_path, index=False)
    spearman_df.to_csv(spearman_path, index=False)
    attempts_df.to_csv(attempts_path, index=False)

    table_cols = [
        "predictor",
        "pooled_result_type",
        "pooled_estimate",
        "pooled_p",
        "lmm_estimate",
        "lmm_se",
        "lmm_p",
        "lmm_ci95_low",
        "lmm_ci95_high",
        "random_intercept_variance",
        "icc",
        "lrt_p_vs_intercept",
        "n_observations",
        "n_participants",
        "n_yes",
    ]
    spearman_cols = [
        "predictor",
        "spearman_median_r",
        "spearman_pct_positive",
        "spearman_n_participants",
    ]

    md = "\n".join(
        [
            "# StudentLife LMM Clustered Analysis",
            "",
            "Commit: 1f1dfb27f0814f1f25f237ed238719750ff616af",
            "Outcome: same-day stress_severity. MixedLMs use ML with a random intercept per participant_id.",
            "",
            "## Dataset Check",
            "",
            f"- Warm rows: {len(df)}",
            f"- Stress rows: {int(stress_df['stress_severity'].notna().sum())}",
            f"- Participants: {int(df['participant_id'].nunique())}",
            f"- Any coherent pattern stress days: {int(stress_df['any_coherent_pattern'].sum())}",
            f"- Confident coherent pattern stress days: {int(stress_df['confident_coherent_pattern'].sum())}",
            f"- Behavioral-withdrawal stress days: {int(stress_df['behavioral_withdrawal'].sum())}",
            "",
            "## Comparison",
            "",
            format_table(comparison, table_cols),
            "",
            "## Per-Participant Spearman Distribution",
            "",
            format_table(spearman_df, spearman_cols),
            "",
            "## Output Files",
            "",
            f"- {comparison_path}",
            f"- {spearman_path}",
            f"- {attempts_path}",
        ]
    )
    markdown_path.write_text(md + "\n", encoding="utf-8")

    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
