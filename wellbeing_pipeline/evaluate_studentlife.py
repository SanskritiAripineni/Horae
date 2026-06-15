"""
Run the wellbeing pipeline (Layer 1 → 2 → 3) on StudentLife data and check
whether the days/participants we flag with deviations or coherent patterns
line up with elevated stress and lower-valence PAM responses.

Why this is the right framing (per HANDOFF.md §11):
  The pipeline is descriptive, not predictive. It does not output
  {"stress": 0.82}. It outputs natural-language deviations and curated
  coherent patterns. So the validation question is:
    "Do the days we flag with more / stronger deviations also have
     more 'stressed' Stress EMA responses and lower-valence PAM responses
     than days we don't flag?"

Outputs (printed):
  • per-marker coverage stats across all participants
  • sample Layer 3 prose for a few participant-weeks
  • alignment metrics:
      - pooled Spearman r between daily risk index and EMA stress severity
      - per-participant median Spearman r
      - mean stress severity on pattern-fired days vs other days (paired t,
        cohen's d)
      - same alignment for PAM valence (low-valence = bad day) and arousal
"""
from __future__ import annotations
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
from scipy import stats

from layer1 import PersonalBaseline, markers_from_raw
from layer2 import detect_deviations, find_coherent_patterns
from layer3 import build_state_description
from studentlife_adapter import (
    DATASET_ROOT, LOCAL_TZ, build_daily_records, dataset_help,
    list_participants, load_pid_sensors,
)

EMA_DIR = DATASET_ROOT / "EMA" / "response"


# ---------- EMA loading (per local date) ----------

def _to_local_date(epoch: float) -> date:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(LOCAL_TZ).date()


def load_stress_per_day(pid: str) -> dict[date, float]:
    """Mean stress severity per local date.

    Stress EMA level: 1=A little stressed … 3=Stressed out, 4=Feeling good,
    5=Feeling great. We recode to severity in [0, 3]: 1→3, 2→2, 3→1, 4→0, 5→0.
    """
    p = EMA_DIR / "Stress" / f"Stress_u{pid[1:]}.json" if pid.startswith("u") else None
    if p is None or not p.exists():
        return {}
    with open(p) as f:
        items = json.load(f)
    by_day: dict[date, list[float]] = defaultdict(list)
    for it in items:
        if "level" not in it or "resp_time" not in it:
            continue
        try:
            level = int(it["level"])
        except (TypeError, ValueError):
            continue
        if not 1 <= level <= 5:
            continue
        sev = max(0.0, 4 - level)  # 4 - level so higher = more stressed
        d = _to_local_date(float(it["resp_time"]))
        by_day[d].append(sev)
    return {d: float(np.mean(v)) for d, v in by_day.items()}


def load_pam_per_day(pid: str) -> dict[date, dict]:
    """For each local date, mean valence and arousal scores.
    PAM 4×4 grid, picture_idx 1..16. Column = valence (1 neg .. 4 pos),
    row = arousal (1 low .. 4 high).
    """
    p = EMA_DIR / "PAM" / f"PAM_u{pid[1:]}.json"
    if not p.exists():
        return {}
    with open(p) as f:
        items = json.load(f)
    by_day_v: dict[date, list[float]] = defaultdict(list)
    by_day_a: dict[date, list[float]] = defaultdict(list)
    for it in items:
        if "picture_idx" not in it or "resp_time" not in it:
            continue
        try:
            idx = int(it["picture_idx"])
        except (TypeError, ValueError):
            continue
        if not 1 <= idx <= 16:
            continue
        col = ((idx - 1) % 4) + 1  # valence 1..4
        row = ((idx - 1) // 4) + 1  # arousal 1..4
        d = _to_local_date(float(it["resp_time"]))
        by_day_v[d].append(float(col))
        by_day_a[d].append(float(row))
    days = set(by_day_v) | set(by_day_a)
    return {d: {"valence": float(np.mean(by_day_v[d])) if by_day_v.get(d) else None,
                "arousal": float(np.mean(by_day_a[d])) if by_day_a.get(d) else None}
            for d in days}


# ---------- Risk index from pipeline output ----------

_MAG_WEIGHT = {"within-typical": 0.0, "mild": 1.0, "moderate": 2.0, "pronounced": 3.0}


def compute_risk_index(devs, patterns) -> float:
    """A small, transparent scalar summary of a day's pipeline output.
    Used ONLY for retrospective alignment, not for the production output
    (which is the Layer 3 structured + prose payload)."""
    score = 0.0
    for d in devs:
        score += _MAG_WEIGHT.get(d.magnitude, 0.0)
    score += 2.0 * len(patterns)
    return score


# ---------- Main pipeline run per participant ----------

def run_pid(pid: str, dump_prose_dates: list[date] | None = None,
            warmup_days: int = 10, recent_days: int = 4,
            baseline_days: int = 21,
            min_magnitude: str = "mild") -> dict:
    sensors = load_pid_sensors(pid)
    raw_days = build_daily_records(pid, sensors)
    if not raw_days:
        return {"pid": pid, "n_days": 0}

    baseline = PersonalBaseline(warmup_days=warmup_days)
    daily_rows = []
    prose_dump = {}

    for raw in raw_days:
        rec = markers_from_raw(raw)
        baseline.add(rec)
        as_of = raw["date"]
        # We need at least baseline_days + a few recent_days of history
        pattern_names: list[str] = []
        dev_markers: list[str] = []
        if not baseline.is_warm():
            risk = 0.0; n_dev = 0; n_pat = 0
        else:
            devs = detect_deviations(baseline, as_of=as_of,
                                     recent_days=recent_days,
                                     baseline_days=baseline_days,
                                     min_magnitude=min_magnitude)
            patterns = find_coherent_patterns(devs)
            risk = compute_risk_index(devs, patterns)
            n_dev = len(devs); n_pat = len(patterns)
            pattern_names = [p.name for p in patterns]
            dev_markers = [d.marker for d in devs]
            if dump_prose_dates and as_of in dump_prose_dates:
                state = build_state_description(baseline, devs, patterns, as_of)
                prose_dump[as_of] = state["prose"]

        # Pull marker coverage summary for this day
        cov = raw["_coverage"]
        n_markers_present = sum(1 for v in cov.values() if v >= 0.5)

        row = {
            "pid": pid, "date": as_of,
            "risk_index": risk,
            "n_dev": n_dev, "n_pat": n_pat,
            "warm": baseline.is_warm(),
            "n_markers_present": n_markers_present,
            "pattern_names": "|".join(pattern_names),
            "dev_markers": "|".join(dev_markers),
        }
        # Embed per-marker coverage so we can chart it later
        for m, v in cov.items():
            row[f"cov_{m}"] = v
        daily_rows.append(row)

    df = pd.DataFrame(daily_rows)
    return {"pid": pid, "daily": df, "prose_dump": prose_dump,
            "n_days": len(df)}


def run_all(pids: list[str] | None = None, max_pids: int | None = None,
            sample_prose: int = 3) -> dict:
    if pids is None:
        pids = list_participants()
    if max_pids:
        pids = pids[:max_pids]

    print(f"[run_all] Running pipeline on {len(pids)} participants")
    all_daily = []
    prose_samples: list[tuple[str, date, str]] = []
    coverage_acc = defaultdict(list)

    for pid in pids:
        try:
            res = run_pid(pid)
        except Exception as e:
            print(f"  {pid}: ERROR {type(e).__name__}: {e}")
            continue
        df = res.get("daily")
        if df is None or len(df) == 0:
            print(f"  {pid}: no days")
            continue
        all_daily.append(df)
        # collect coverage from raw markers
        # (cheap: re-read markers_from_raw via baseline — skip here)

        # prose: dump first 3 patterns-fired days
        warm_days = df[df["warm"]]
        pat_days = warm_days[warm_days["n_pat"] >= 1]
        if len(pat_days) >= 1 and sample_prose > 0 and len(prose_samples) < sample_prose:
            for d_row in pat_days.head(2).itertuples():
                # re-run to get prose for this date
                res2 = run_pid(pid, dump_prose_dates=[d_row.date])
                p = res2["prose_dump"].get(d_row.date)
                if p:
                    prose_samples.append((pid, d_row.date, p))
                if len(prose_samples) >= sample_prose:
                    break
        print(f"  {pid}: {len(df)} days, "
              f"warm:{int(df['warm'].sum())}, dev≥1 days:{int((df['n_dev']>=1).sum())}, "
              f"pattern days:{int((df['n_pat']>=1).sum())}")

    daily = pd.concat(all_daily, ignore_index=True) if all_daily else pd.DataFrame()
    return {"daily": daily, "prose_samples": prose_samples, "pids": pids}


# ---------- Alignment with EMA ----------

def align_with_ema(daily: pd.DataFrame) -> dict:
    """Join the per-day pipeline output with same-day Stress and PAM."""
    rows = []
    for pid, sub in daily.groupby("pid"):
        stress = load_stress_per_day(pid)
        pam = load_pam_per_day(pid)
        for r in sub.itertuples():
            d = r.date
            stress_today = stress.get(d)
            pam_today = pam.get(d, {})
            rows.append({
                "pid": pid, "date": d,
                "risk_index": r.risk_index, "n_dev": r.n_dev, "n_pat": r.n_pat,
                "warm": r.warm,
                "stress_severity": stress_today,
                "valence": pam_today.get("valence") if pam_today else None,
                "arousal": pam_today.get("arousal") if pam_today else None,
            })
    return {"joined": pd.DataFrame(rows)}


def report_alignment(joined: pd.DataFrame) -> None:
    df = joined[joined["warm"]].copy()
    print("\n" + "=" * 78)
    print("  ALIGNMENT METRICS")
    print("=" * 78)
    print(f"Warm-baseline days total: {len(df)}")
    print(f"Days with Stress EMA:     {df['stress_severity'].notna().sum()}")
    print(f"Days with PAM EMA:        {df['valence'].notna().sum()}")

    def _spearman(a, b):
        m = (~a.isna()) & (~b.isna())
        if m.sum() < 10:
            return None
        return stats.spearmanr(a[m], b[m])

    for label, ema_col in [("Stress severity", "stress_severity"),
                           ("PAM valence (higher = more positive)", "valence"),
                           ("PAM arousal", "arousal")]:
        print("\n— Pooled risk_index vs", label, "—")
        r = _spearman(df["risk_index"], df[ema_col])
        if r is None:
            print("  (insufficient data)")
        else:
            print(f"  Spearman r = {r.statistic:+.3f}, p = {r.pvalue:.2e}, "
                  f"n = {((~df['risk_index'].isna()) & (~df[ema_col].isna())).sum()}")

        # Per-participant Spearman r
        per_pid = []
        for pid, sub in df.groupby("pid"):
            r2 = _spearman(sub["risk_index"], sub[ema_col])
            if r2 is not None and not np.isnan(r2.statistic):
                per_pid.append(r2.statistic)
        if per_pid:
            print(f"  Per-participant Spearman r: median {np.median(per_pid):+.3f}, "
                  f"mean {np.mean(per_pid):+.3f}, n_pids = {len(per_pid)}, "
                  f"% positive: {100*np.mean(np.array(per_pid)>0):.0f}%")
        # Pattern-fired vs not (paired comparison via mean diff)
        if df[ema_col].notna().any():
            pat_yes = df[(df["n_pat"] >= 1) & df[ema_col].notna()][ema_col]
            pat_no  = df[(df["n_pat"] == 0) & df[ema_col].notna()][ema_col]
            if len(pat_yes) >= 5 and len(pat_no) >= 5:
                t = stats.ttest_ind(pat_yes, pat_no, equal_var=False)
                d = (pat_yes.mean() - pat_no.mean()) / (
                    np.sqrt((pat_yes.var(ddof=1) + pat_no.var(ddof=1)) / 2) + 1e-9)
                print(f"  Pattern-fired days mean = {pat_yes.mean():.3f} (n={len(pat_yes)})  "
                      f"vs no-pattern mean = {pat_no.mean():.3f} (n={len(pat_no)})")
                print(f"  Welch t = {t.statistic:+.2f}, p = {t.pvalue:.2e}, "
                      f"Cohen's d ≈ {d:+.2f}")


# ---------- Entry point ----------

def main(argv) -> int:
    max_pids = None
    if len(argv) > 1:
        try:
            max_pids = int(argv[1])
        except ValueError:
            pass
    print(f"[config] STUDENTLIFE_DATASET_ROOT={DATASET_ROOT}")
    res = run_all(max_pids=max_pids, sample_prose=4)
    daily = res["daily"]
    if len(daily) == 0:
        print("\nNo StudentLife daily rows were produced.")
        print(dataset_help())
        return 1
    print(f"\n[run_all] total daily rows: {len(daily)}")

    # Show sample prose
    print("\n" + "=" * 78)
    print("  SAMPLE LAYER 3 PROSE — face-validity check")
    print("=" * 78)
    for pid, d, prose in res["prose_samples"]:
        print(f"\n--- {pid}  {d.isoformat()} ---")
        print(prose)

    # Align with EMA
    j = align_with_ema(daily)
    report_alignment(j["joined"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
