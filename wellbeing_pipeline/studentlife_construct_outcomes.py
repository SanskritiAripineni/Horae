"""
Pre-specified StudentLife construct-validity state/outcome tests.

This extends studentlife_validation_analysis.py without searching over outcomes:
each behavioral state is tested only against the pre-committed primary and
secondary EMA outcomes. The primary alignment matches the existing stress
analysis: pipeline state date == EMA local response date.
"""
from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import chi2
import statsmodels.formula.api as smf

from evaluate_studentlife import EMA_DIR, load_pam_per_day, load_stress_per_day
from studentlife_adapter import DATASET_ROOT, LOCAL_TZ, list_participants
import studentlife_validation_analysis as sva


RESULTS_DIR = Path(__file__).resolve().parent / "results"
OUT_PREFIX = "studentlife_construct_outcomes_tight_circadian_1f1dfb2"
TARGET_COMMIT = "1f1dfb27f0814f1f25f237ed238719750ff616af"

STATES = {
    "phone-mediated-sleep-delay": [
        ("PRIMARY", "sleep_hours", "same_day"),
        ("SECONDARY", "sleep_quality", "same_day"),
    ],
    "behavioral-withdrawal": [
        ("PRIMARY", "stress_severity", "same_day"),
        ("SECONDARY", "pam_valence", "same_day"),
    ],
    "circadian-instability": [
        ("PRIMARY", "sleep_quality", "same_day"),
        ("SECONDARY", "sleep_hours", "same_day"),
    ],
    "fragmented-attention-with-sleep-loss": [
        ("PRIMARY", "sleep_hours", "same_day"),
        ("SECONDARY", "stress_severity", "same_day"),
    ],
}

SLEEP_SECONDARY_ALIGNMENT_STATES = {
    ("phone-mediated-sleep-delay", "sleep_hours"),
    ("phone-mediated-sleep-delay", "sleep_quality"),
    ("circadian-instability", "sleep_quality"),
    ("circadian-instability", "sleep_hours"),
    ("fragmented-attention-with-sleep-loss", "sleep_hours"),
}

OUTCOMES = {
    "sleep_hours": {
        "ema_field": "Sleep.hour",
        "coding": "1=<3 hours, 2=3.5, 3=4, ..., 19=12; code 1 is approximated as 2.5 hours.",
        "raw_label": "sleep_hours_numeric",
        "oriented_label": "-sleep_hours_numeric",
        "hypothesis": "state present -> shorter sleep; larger oriented value means fewer hours.",
        "worse_direction": "lower raw hours / higher -hours",
    },
    "sleep_quality": {
        "ema_field": "Sleep.rate",
        "coding": "1=Very good, 2=Fairly good, 3=Fairly bad, 4=Very bad.",
        "raw_label": "sleep_quality_rate",
        "oriented_label": "sleep_quality_rate",
        "hypothesis": "state present -> worse sleep quality; larger value means worse quality.",
        "worse_direction": "higher rating",
    },
    "stress_severity": {
        "ema_field": "Stress.level",
        "coding": "1=A little stressed, 2=Definitely stressed, 3=Stressed out, 4=Feeling good, 5=Feeling great; recoded to severity 1->3, 2->2, 3->1, 4/5->0.",
        "raw_label": "stress_severity",
        "oriented_label": "stress_severity",
        "hypothesis": "state present -> higher stress severity; larger value means worse stress.",
        "worse_direction": "higher severity",
    },
    "pam_valence": {
        "ema_field": "PAM.picture_idx",
        "coding": "4x4 grid; valence is column ((picture_idx-1) % 4)+1, 1=more negative, 4=more positive.",
        "raw_label": "pam_valence",
        "oriented_label": "-pam_valence",
        "hypothesis": "state present -> lower/more negative valence; larger oriented value means worse affect.",
        "worse_direction": "lower raw valence / higher -valence",
    },
}


@dataclass(frozen=True)
class OutcomeSeries:
    raw: dict[date, float]
    oriented: dict[date, float]


def _to_local_date(epoch: float) -> date:
    return pd.to_datetime(float(epoch), unit="s", utc=True).tz_convert(LOCAL_TZ).date()


def _to_local_hour(epoch: float) -> float:
    ts = pd.to_datetime(float(epoch), unit="s", utc=True).tz_convert(LOCAL_TZ)
    return float(ts.hour + ts.minute / 60.0 + ts.second / 3600.0)


def _sleep_hour_to_numeric(code: int) -> float:
    if code == 1:
        return 2.5
    return float(code + 1.5)


def load_sleep_per_day(pid: str) -> dict[date, dict[str, float]]:
    path = EMA_DIR / "Sleep" / f"Sleep_u{pid[1:]}.json"
    if not path.exists():
        return {}
    items = json.loads(path.read_text(encoding="utf-8"))
    by_day_hours: dict[date, list[float]] = {}
    by_day_rate: dict[date, list[float]] = {}
    for item in items:
        if "resp_time" not in item:
            continue
        d = _to_local_date(item["resp_time"])
        if "hour" in item:
            try:
                code = int(item["hour"])
            except (TypeError, ValueError):
                code = -1
            if 1 <= code <= 19:
                by_day_hours.setdefault(d, []).append(_sleep_hour_to_numeric(code))
        if "rate" in item:
            try:
                rate = int(item["rate"])
            except (TypeError, ValueError):
                rate = -1
            if 1 <= rate <= 4:
                by_day_rate.setdefault(d, []).append(float(rate))
    days = set(by_day_hours) | set(by_day_rate)
    return {
        d: {
            "sleep_hours": float(np.mean(by_day_hours[d])) if d in by_day_hours else np.nan,
            "sleep_quality": float(np.mean(by_day_rate[d])) if d in by_day_rate else np.nan,
        }
        for d in days
    }


def sleep_response_timing_summary() -> dict:
    hours = []
    for pid in list_participants():
        path = EMA_DIR / "Sleep" / f"Sleep_u{pid[1:]}.json"
        if not path.exists():
            continue
        for item in json.loads(path.read_text(encoding="utf-8")):
            if "resp_time" in item and ("hour" in item or "rate" in item):
                hours.append(_to_local_hour(item["resp_time"]))
    arr = np.array(hours, dtype=float)
    return {
        "n_responses_with_sleep_fields": int(len(arr)),
        "median_local_response_hour": float(np.median(arr)) if len(arr) else np.nan,
        "p10_local_response_hour": float(np.percentile(arr, 10)) if len(arr) else np.nan,
        "p90_local_response_hour": float(np.percentile(arr, 90)) if len(arr) else np.nan,
        "pct_before_noon": float(100.0 * np.mean(arr < 12.0)) if len(arr) else np.nan,
    }


def pam_response_timing_summary() -> dict:
    hours = []
    for pid in list_participants():
        path = EMA_DIR / "PAM" / f"PAM_u{pid[1:]}.json"
        if not path.exists():
            continue
        for item in json.loads(path.read_text(encoding="utf-8")):
            if "resp_time" in item and "picture_idx" in item:
                hours.append(_to_local_hour(item["resp_time"]))
    arr = np.array(hours, dtype=float)
    return {
        "n_responses": int(len(arr)),
        "median_local_response_hour": float(np.median(arr)) if len(arr) else np.nan,
        "p10_local_response_hour": float(np.percentile(arr, 10)) if len(arr) else np.nan,
        "p90_local_response_hour": float(np.percentile(arr, 90)) if len(arr) else np.nan,
    }


def load_outcomes(pid: str) -> dict[str, OutcomeSeries]:
    stress = load_stress_per_day(pid)
    pam = load_pam_per_day(pid)
    sleep = load_sleep_per_day(pid)

    sleep_hours_raw = {d: v["sleep_hours"] for d, v in sleep.items() if not pd.isna(v["sleep_hours"])}
    sleep_quality_raw = {d: v["sleep_quality"] for d, v in sleep.items() if not pd.isna(v["sleep_quality"])}
    pam_valence_raw = {
        d: float(v["valence"])
        for d, v in pam.items()
        if v and v.get("valence") is not None and not pd.isna(v.get("valence"))
    }

    return {
        "sleep_hours": OutcomeSeries(
            raw=sleep_hours_raw,
            oriented={d: -v for d, v in sleep_hours_raw.items()},
        ),
        "sleep_quality": OutcomeSeries(
            raw=sleep_quality_raw,
            oriented=sleep_quality_raw,
        ),
        "stress_severity": OutcomeSeries(
            raw=stress,
            oriented=stress,
        ),
        "pam_valence": OutcomeSeries(
            raw=pam_valence_raw,
            oriented={d: -v for d, v in pam_valence_raw.items()},
        ),
    }


def add_outcome_columns(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pid, sub in df.groupby("pid"):
        outcomes = load_outcomes(pid)
        tmp = sub.copy()
        for outcome_name, series in outcomes.items():
            tmp[f"{outcome_name}_raw_same_day"] = tmp["date"].map(series.raw)
            tmp[f"{outcome_name}_oriented_same_day"] = tmp["date"].map(series.oriented)
            tmp[f"{outcome_name}_raw_next_day"] = tmp["date"].map(lambda d, s=series: s.raw.get(d + timedelta(days=1)))
            tmp[f"{outcome_name}_oriented_next_day"] = tmp["date"].map(lambda d, s=series: s.oriented.get(d + timedelta(days=1)))
        rows.append(tmp)
    return pd.concat(rows, ignore_index=True)


def _cohen_d(yes: pd.Series, no: pd.Series) -> float:
    yes = pd.to_numeric(yes, errors="coerce").dropna()
    no = pd.to_numeric(no, errors="coerce").dropna()
    if len(yes) < 2 or len(no) < 2:
        return np.nan
    pooled = np.sqrt((yes.var(ddof=1) + no.var(ddof=1)) / 2.0)
    if pooled <= 0:
        return np.nan
    return float((yes.mean() - no.mean()) / pooled)


def _welch_p(yes: pd.Series, no: pd.Series) -> float:
    yes = pd.to_numeric(yes, errors="coerce").dropna()
    no = pd.to_numeric(no, errors="coerce").dropna()
    if len(yes) < 2 or len(no) < 2:
        return np.nan
    return float(stats.ttest_ind(yes, no, equal_var=False).pvalue)


def _mixedlm_stats(data: pd.DataFrame) -> dict:
    usable = data[["pid", "state_present", "y"]].dropna().copy()
    usable["state_present"] = usable["state_present"].astype(float)
    if usable["state_present"].nunique() < 2 or usable["pid"].nunique() < 3:
        return {
            "lmm_estimate": np.nan,
            "lmm_se": np.nan,
            "lmm_p": np.nan,
            "lmm_ci_low": np.nan,
            "lmm_ci_high": np.nan,
            "random_intercept_variance": np.nan,
            "residual_variance": np.nan,
            "icc": np.nan,
            "lrt_p": np.nan,
            "lmm_converged": False,
            "lmm_error": "insufficient variation",
        }

    def fit(formula: str):
        model = smf.mixedlm(formula, usable, groups=usable["pid"])
        last_exc = None
        for method in ("lbfgs", "powell", "cg", "bfgs"):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    res = model.fit(reml=False, method=method, maxiter=1000, disp=False)
                return res
            except Exception as exc:  # pragma: no cover - diagnostic fallback
                last_exc = exc
        raise last_exc

    try:
        full = fit("y ~ state_present")
        null = fit("y ~ 1")
        est = float(full.params.get("state_present", np.nan))
        se = float(full.bse.get("state_present", np.nan))
        p = float(full.pvalues.get("state_present", np.nan))
        ci = full.conf_int().loc["state_present"].astype(float)
        random_var = float(full.cov_re.iloc[0, 0]) if full.cov_re.size else np.nan
        resid_var = float(full.scale)
        icc = random_var / (random_var + resid_var) if (random_var + resid_var) > 0 else np.nan
        lr = max(0.0, 2.0 * (float(full.llf) - float(null.llf)))
        return {
            "lmm_estimate": est,
            "lmm_se": se,
            "lmm_p": p,
            "lmm_ci_low": float(ci.iloc[0]),
            "lmm_ci_high": float(ci.iloc[1]),
            "random_intercept_variance": random_var,
            "residual_variance": resid_var,
            "icc": float(icc),
            "lrt_p": float(chi2.sf(lr, df=1)),
            "lmm_converged": bool(getattr(full, "converged", False)),
            "lmm_error": "",
        }
    except Exception as exc:
        return {
            "lmm_estimate": np.nan,
            "lmm_se": np.nan,
            "lmm_p": np.nan,
            "lmm_ci_low": np.nan,
            "lmm_ci_high": np.nan,
            "random_intercept_variance": np.nan,
            "residual_variance": np.nan,
            "icc": np.nan,
            "lrt_p": np.nan,
            "lmm_converged": False,
            "lmm_error": f"{type(exc).__name__}: {exc}",
        }


def _per_participant_corr(data: pd.DataFrame) -> dict:
    vals = []
    for _pid, sub in data.groupby("pid"):
        sub = sub[["state_present", "y"]].dropna()
        if len(sub) < 3 or sub["state_present"].nunique() < 2 or sub["y"].nunique() < 2:
            continue
        res = stats.spearmanr(sub["state_present"], sub["y"])
        if not pd.isna(res.statistic):
            vals.append(float(res.statistic))
    arr = np.array(vals, dtype=float)
    return {
        "participant_corr_median_r": float(np.median(arr)) if len(arr) else np.nan,
        "participant_corr_pct_hypothesized_direction": float(100.0 * np.mean(arr > 0)) if len(arr) else np.nan,
        "participant_corr_n": int(len(arr)),
    }


def analyze_pair(df: pd.DataFrame, state: str, outcome: str, role: str, alignment: str) -> dict:
    suffix = "same_day" if alignment == "same_day" else "next_day"
    state_col = f"pattern__{state}"
    raw_col = f"{outcome}_raw_{suffix}"
    y_col = f"{outcome}_oriented_{suffix}"
    usable = pd.DataFrame({
        "pid": df["pid"],
        "state_present": df[state_col].astype(bool),
        "raw": pd.to_numeric(df[raw_col], errors="coerce"),
        "y": pd.to_numeric(df[y_col], errors="coerce"),
    }).dropna(subset=["y"])

    yes = usable.loc[usable["state_present"], "y"]
    no = usable.loc[~usable["state_present"], "y"]
    raw_yes = usable.loc[usable["state_present"], "raw"]
    raw_no = usable.loc[~usable["state_present"], "raw"]
    mixed = _mixedlm_stats(usable)
    corr = _per_participant_corr(usable)
    meta = OUTCOMES[outcome]
    return {
        "state": state,
        "role": role,
        "outcome": outcome,
        "alignment": alignment,
        "ema_field": meta["ema_field"],
        "coding": meta["coding"],
        "tested_value_oriented": meta["oriented_label"],
        "hypothesized_direction": meta["hypothesis"],
        "n_yes": int(len(yes)),
        "n_no": int(len(no)),
        "mean_yes": float(yes.mean()) if len(yes) else np.nan,
        "mean_no": float(no.mean()) if len(no) else np.nan,
        "raw_mean_yes": float(raw_yes.mean()) if len(raw_yes) else np.nan,
        "raw_mean_no": float(raw_no.mean()) if len(raw_no) else np.nan,
        "welch_p": _welch_p(yes, no),
        "cohen_d": _cohen_d(yes, no),
        "yes_day_participants": int(usable.loc[usable["state_present"], "pid"].nunique()),
        "n_obs": int(len(usable)),
        "n_participants": int(usable["pid"].nunique()),
        **mixed,
        **corr,
    }


def coverage_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for outcome in OUTCOMES:
        for alignment in ("same_day", "next_day"):
            raw_col = f"{outcome}_raw_{alignment}"
            usable = df[df[raw_col].notna()]
            rows.append({
                "outcome": outcome,
                "alignment": alignment,
                "participant_days_with_ema": int(len(usable)),
                "participants_with_ema": int(usable["pid"].nunique()),
            })
    return pd.DataFrame(rows)


def build_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for state, pairings in STATES.items():
        for role, outcome, alignment in pairings:
            rows.append(analyze_pair(df, state, outcome, role, alignment))
            if (state, outcome) in SLEEP_SECONDARY_ALIGNMENT_STATES:
                rows.append(analyze_pair(df, state, outcome, f"{role}_NEXT_NIGHT_ALIGNMENT", "next_day"))
    return pd.DataFrame(rows)


def _fmt(value) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.4g}"
    return str(value)


def to_markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print("[construct] building tightened circadian daily table")
    df = sva.build_joined_daily(circadian_min_markers=2)
    df = add_outcome_columns(df)
    table = build_rows(df)
    cov = coverage_table(df)

    table_path = RESULTS_DIR / f"{OUT_PREFIX}_table.csv"
    cov_path = RESULTS_DIR / f"{OUT_PREFIX}_coverage.csv"
    json_path = RESULTS_DIR / f"{OUT_PREFIX}_metadata.json"
    md_path = RESULTS_DIR / f"{OUT_PREFIX}_summary.md"

    table.to_csv(table_path, index=False)
    cov.to_csv(cov_path, index=False)
    metadata = {
        "target_commit": TARGET_COMMIT,
        "dataset_root": str(DATASET_ROOT),
        "config": {
            "circadian_min_markers": 2,
            "warmup_days": 10,
            "recent_days": 4,
            "baseline_days": 21,
            "min_magnitude": "mild",
        },
        "alignment": {
            "primary": "same_day: pipeline state date == EMA local response date, matching existing stress analysis",
            "sleep_reference": "Sleep EMA hour/rate questions ask about last night; response local date D refers to the prior night ending on D.",
            "pam_reference": "PAM is momentary affect at response time; local response date D is same-day affect.",
            "stress_reference": "Stress is momentary at response time; local response date D is same-day stress.",
            "secondary_sleep_alignment": "next_day rows test state date D against Sleep EMA response date D+1, i.e. the following night's sleep.",
        },
        "outcomes": OUTCOMES,
        "sleep_response_timing": sleep_response_timing_summary(),
        "pam_response_timing": pam_response_timing_summary(),
    }
    json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    columns = [
        "state", "role", "outcome", "alignment", "tested_value_oriented",
        "n_yes", "n_no", "raw_mean_yes", "raw_mean_no", "mean_yes", "mean_no",
        "welch_p", "cohen_d", "lmm_estimate", "lmm_se", "lmm_p",
        "lmm_ci_low", "lmm_ci_high", "random_intercept_variance", "icc",
        "lrt_p", "n_obs", "n_participants", "yes_day_participants",
        "participant_corr_median_r", "participant_corr_pct_hypothesized_direction",
        "participant_corr_n",
    ]
    md = [
        "# StudentLife Construct-Appropriate Outcome Tests",
        "",
        f"Target commit: `{TARGET_COMMIT}`",
        f"Dataset root: `{DATASET_ROOT}`",
        "",
        "Primary alignment matches the existing stress analysis: pipeline state date equals EMA local response date.",
        "Sleep EMA `hour` and `rate` ask about last night, so a Sleep response on local date D refers to the prior night ending on D. Labeled `*_NEXT_NIGHT_ALIGNMENT` rows test state date D against Sleep response date D+1.",
        "PAM and Stress are momentary responses assigned to their local response date.",
        "",
        "All model outcomes are oriented so larger values are worse / in the hypothesized state-present direction. Raw means are also included for interpretability.",
        "",
        "## Coverage",
        to_markdown_table(cov, list(cov.columns)),
        "",
        "## Comparison Table",
        to_markdown_table(table, columns),
        "",
        "## Outcome Coding",
    ]
    for name, meta in OUTCOMES.items():
        md.extend([
            f"### {name}",
            f"- EMA field: `{meta['ema_field']}`",
            f"- Coding: {meta['coding']}",
            f"- Tested/oriented value: `{meta['oriented_label']}`",
            f"- Direction: {meta['hypothesis']}",
            "",
        ])
    md.extend([
        "## Timing Summary",
        f"- Sleep responses with sleep fields: {metadata['sleep_response_timing']['n_responses_with_sleep_fields']}; median local hour {metadata['sleep_response_timing']['median_local_response_hour']:.2f}; p10-p90 {metadata['sleep_response_timing']['p10_local_response_hour']:.2f}-{metadata['sleep_response_timing']['p90_local_response_hour']:.2f}; {metadata['sleep_response_timing']['pct_before_noon']:.1f}% before noon.",
        f"- PAM responses: {metadata['pam_response_timing']['n_responses']}; median local hour {metadata['pam_response_timing']['median_local_response_hour']:.2f}; p10-p90 {metadata['pam_response_timing']['p10_local_response_hour']:.2f}-{metadata['pam_response_timing']['p90_local_response_hour']:.2f}.",
    ])
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"[construct] wrote {table_path}")
    print(f"[construct] wrote {cov_path}")
    print(f"[construct] wrote {json_path}")
    print(f"[construct] wrote {md_path}")
    print(table[["state", "role", "outcome", "alignment", "n_yes", "n_no", "welch_p", "lmm_estimate", "lmm_p"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
