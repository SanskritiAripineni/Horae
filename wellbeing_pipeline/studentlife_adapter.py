"""
Adapter: StudentLife raw sensors → per-day MARKER_SPECS DayRecords.

Per-day markers derived per participant:
  sleep_onset_hour, sleep_duration_hours, sleep_regularity_index,
  late_night_screen_min, total_screen_min, app_switching_rate,
  mobility_entropy, location_revisit_ratio,
  social_rhythm_metric, comm_reciprocity

All times are local (Hanover NH, UTC-4 EDT — the StudentLife data spans
Mar–Jun 2013, entirely within DST). EMA labels are also converted to local
time before being aligned with these per-day marker dates.

This is the swap point referenced by HANDOFF.md §10(a). Layer 2 / Layer 3
remain unchanged.
"""
from __future__ import annotations
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from layer1 import DayRecord, MARKER_SPECS

# ---------- Paths ----------
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DATASET_ROOT = _REPO_ROOT / "data" / "studentlife" / "dataset"
DATASET_ROOT = Path(os.environ.get("STUDENTLIFE_DATASET_ROOT", _DEFAULT_DATASET_ROOT)).expanduser()
SENSING = DATASET_ROOT / "sensing"
APP_USAGE = DATASET_ROOT / "app_usage"
CALL_LOG = DATASET_ROOT / "call_log"
SMS_DIR = DATASET_ROOT / "sms"

# StudentLife was Mar–Jun 2013 → entirely within US Eastern Daylight Time.
LOCAL_TZ = timezone(timedelta(hours=-4))


def dataset_help() -> str:
    """Human-readable setup instructions for local StudentLife evaluation."""
    return (
        "StudentLife dataset not found or incomplete.\n"
        f"Current STUDENTLIFE_DATASET_ROOT: {DATASET_ROOT}\n"
        "Expected directories under that root include:\n"
        "  - sensing/phonelock\n"
        "  - sensing/wifi_location\n"
        "  - EMA/response/Stress\n"
        "  - EMA/response/PAM\n"
        "\n"
        "Set the dataset root before running validation, for example:\n"
        "  export STUDENTLIFE_DATASET_ROOT=/path/to/studentlife/dataset\n"
        "  python3 wellbeing_pipeline/evaluate_studentlife.py\n"
    )


# ---------- Loading helpers ----------

def _to_local(ts: pd.Series) -> pd.Series:
    """UTC tz-aware → local naive."""
    return ts.dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)


def _read_intervals(p: Path) -> pd.DataFrame:
    if not p.exists():
        return pd.DataFrame(columns=["start", "end"])
    df = pd.read_csv(p)
    df.columns = [c.strip() for c in df.columns]
    if df.shape[1] < 2:
        return pd.DataFrame(columns=["start", "end"])
    s = pd.to_numeric(df.iloc[:, 0], errors="coerce")
    e = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    out = pd.DataFrame({
        "start": pd.to_datetime(s, unit="s", utc=True),
        "end":   pd.to_datetime(e, unit="s", utc=True),
    }).dropna()
    out = out[out["end"] > out["start"]]
    out["start"] = _to_local(out["start"])
    out["end"]   = _to_local(out["end"])
    return out.sort_values("start").reset_index(drop=True)


def _read_wifi_location(pid: str) -> pd.DataFrame:
    p = SENSING / "wifi_location" / f"wifi_location_{pid}.csv"
    if not p.exists():
        return pd.DataFrame(columns=["time", "location"])
    # Trailing-comma quirk → use explicit column names.
    df = pd.read_csv(p, index_col=False,
                     names=["time", "location", "_extra"], header=0)
    df = df.drop(columns=["_extra"], errors="ignore")
    df["time"] = pd.to_numeric(df["time"], errors="coerce")
    df = df.dropna(subset=["time"])
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["time"] = _to_local(df["time"])
    df["location"] = df["location"].fillna("").astype(str).str.strip()
    df = df[df["location"] != ""]
    return df.sort_values("time").reset_index(drop=True)


def _read_running_apps(pid: str) -> pd.DataFrame:
    p = APP_USAGE / f"running_app_{pid}.csv"
    if not p.exists():
        return pd.DataFrame(columns=["time", "package"])
    df = pd.read_csv(p, low_memory=False, encoding="utf-8-sig")
    pkg_col = "RUNNING_TASKS_topActivity_mPackage"
    if pkg_col not in df.columns or "timestamp" not in df.columns:
        return pd.DataFrame(columns=["time", "package"])
    df = df[["timestamp", pkg_col]].rename(columns={pkg_col: "package"}).dropna()
    df["timestamp"] = pd.to_datetime(
        pd.to_numeric(df["timestamp"], errors="coerce"), unit="s", utc=True
    )
    df = df.dropna(subset=["timestamp"])
    df["time"] = _to_local(df["timestamp"])
    return df[["time", "package"]].sort_values("time").reset_index(drop=True)


def _read_sms(pid: str) -> pd.DataFrame:
    p = SMS_DIR / f"sms_{pid}.csv"
    if not p.exists():
        return pd.DataFrame(columns=["time", "outgoing"])
    try:
        df = pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
    except Exception:
        return pd.DataFrame(columns=["time", "outgoing"])
    if "MESSAGES_date" not in df.columns or "MESSAGES_type" not in df.columns:
        return pd.DataFrame(columns=["time", "outgoing"])
    md = pd.to_numeric(df["MESSAGES_date"], errors="coerce") / 1000.0
    mt = pd.to_numeric(df["MESSAGES_type"], errors="coerce")
    out = pd.DataFrame({
        "time": pd.to_datetime(md, unit="s", utc=True),
        "mtype": mt,
    }).dropna()
    out["time"] = _to_local(out["time"])
    out["outgoing"] = (out["mtype"] == 2)  # Android: 1=inbox, 2=sent
    return out[["time", "outgoing"]].sort_values("time").reset_index(drop=True)


def _read_calls(pid: str) -> pd.DataFrame:
    p = CALL_LOG / f"call_log_{pid}.csv"
    if not p.exists():
        return pd.DataFrame(columns=["time", "outgoing"])
    try:
        df = pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
    except Exception:
        return pd.DataFrame(columns=["time", "outgoing"])
    if "CALLS_date" not in df.columns or "CALLS_type" not in df.columns:
        return pd.DataFrame(columns=["time", "outgoing"])
    cd = pd.to_numeric(df["CALLS_date"], errors="coerce") / 1000.0
    ct = pd.to_numeric(df["CALLS_type"], errors="coerce")
    out = pd.DataFrame({
        "time": pd.to_datetime(cd, unit="s", utc=True),
        "ctype": ct,
    }).dropna()
    out["time"] = _to_local(out["time"])
    out["outgoing"] = (out["ctype"] == 2)  # Android: 1=in, 2=out, 3=missed
    return out[["time", "outgoing"]].sort_values("time").reset_index(drop=True)


def load_pid_sensors(pid: str) -> dict:
    return {
        "locked": _read_intervals(SENSING / "phonelock" / f"phonelock_{pid}.csv"),
        "dark":   _read_intervals(SENSING / "dark"      / f"dark_{pid}.csv"),
        "wloc":   _read_wifi_location(pid),
        "apps":   _read_running_apps(pid),
        "sms":    _read_sms(pid),
        "calls":  _read_calls(pid),
    }


# ---------- Sleep detection ----------

def _merge_intervals(intervals: list[tuple[datetime, datetime]],
                     gap_minutes: float = 30.0) -> list[tuple[datetime, datetime]]:
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: x[0])
    out = [intervals[0]]
    for s, e in intervals[1:]:
        ps, pe = out[-1]
        if (s - pe).total_seconds() / 60.0 <= gap_minutes:
            out[-1] = (ps, max(pe, e))
        else:
            out.append((s, e))
    return out


def _clip(s: datetime, e: datetime, lo: datetime, hi: datetime) -> Optional[tuple]:
    a, b = max(s, lo), min(e, hi)
    return (a, b) if b > a else None


def detect_sleep_per_day(locked: pd.DataFrame, dark: pd.DataFrame,
                         dates: list[date]) -> dict[date, dict]:
    """For each wake-date D, find the night sleep block.

    Window: [D-1 20:00, D 11:00]. Sleep candidate = longest merged locked-block
    ≥ 2.5h, optionally intersected with darkness, with onset before D 04:00 and
    duration ≤ 12h (rejects daytime phone-off periods that can otherwise look
    like a multi-hour locked block).
    """
    locked_intervals = list(zip(locked["start"], locked["end"])) if len(locked) else []
    dark_intervals = list(zip(dark["start"], dark["end"])) if len(dark) else []

    out: dict[date, dict] = {}
    for D in dates:
        lo = datetime.combine(D - timedelta(days=1), time(20, 0))
        hi = datetime.combine(D, time(11, 0))
        onset_latest = datetime.combine(D, time(4, 0))
        # Clip locked intervals into window and merge
        clipped = []
        for s, e in locked_intervals:
            c = _clip(s, e, lo, hi)
            if c:
                clipped.append(c)
        merged = _merge_intervals(clipped, gap_minutes=30.0)
        if not merged:
            out[D] = {"onset": None, "duration": None, "coverage": 0.0,
                      "sleep_minutes": []}
            continue

        # Intersect each candidate with darkness; if any darkness exists in window,
        # that gives a tighter sleep estimate. If no dark data, fall back to locked.
        dark_in_win = []
        for s, e in dark_intervals:
            c = _clip(s, e, lo, hi)
            if c:
                dark_in_win.append(c)

        def _intersect_with_dark(s, e):
            if not dark_in_win:
                return [(s, e)]
            chunks = []
            for ds, de in dark_in_win:
                a, b = max(s, ds), min(e, de)
                if b > a:
                    chunks.append((a, b))
            return chunks

        def _accept(s, e):
            dur = (e - s).total_seconds()
            return (dur >= 2.5 * 3600 and dur <= 12 * 3600 and s <= onset_latest)

        best = None  # (duration_seconds, start, end)
        for s, e in merged:
            chunks = _intersect_with_dark(s, e)
            for cs, ce in chunks:
                if _accept(cs, ce):
                    dur = (ce - cs).total_seconds()
                    if best is None or dur > best[0]:
                        best = (dur, cs, ce)
        if best is None:
            for s, e in merged:
                if _accept(s, e):
                    dur = (e - s).total_seconds()
                    if best is None or dur > best[0]:
                        best = (dur, s, e)
        if best is None:
            out[D] = {"onset": None, "duration": None, "coverage": 0.0,
                      "sleep_minutes": []}
            continue

        dur_s, s, e = best
        # Onset hour: hours-of-day, with +24 if onset crosses past midnight to D
        if s.date() == D:
            onset_hour = 24.0 + s.hour + s.minute / 60.0
        else:
            onset_hour = s.hour + s.minute / 60.0
        out[D] = {
            "onset": onset_hour,
            "duration": dur_s / 3600.0,
            "coverage": 1.0,
            "sleep_minutes": [(s, e)],
        }
    return out


# ---------- Sleep regularity index (Phillips et al. 2017) ----------

def compute_sri_series(sleep_per_day: dict[date, dict],
                       dates: list[date]) -> dict[date, tuple[Optional[float], float]]:
    """SRI(D) over a 7-day rolling window ending at D (inclusive).

    Build a per-minute sleep/wake binary across the study (1=sleep, 0=wake).
    SRI = 100 * P(state(t) == state(t-24h)) over minute pairs in the
    7 days [D-6, D].

    Returns {date: (sri, coverage)}.
    """
    if not dates:
        return {}
    dmin, dmax = min(dates), max(dates)
    # Build per-minute binary covering all required pair days: from dmin-7 to dmax
    span_start = datetime.combine(dmin - timedelta(days=7), time(0, 0))
    span_end   = datetime.combine(dmax + timedelta(days=1), time(0, 0))
    n_minutes  = int((span_end - span_start).total_seconds() // 60)
    sleep = np.zeros(n_minutes, dtype=np.uint8)
    valid = np.zeros(n_minutes, dtype=np.uint8)  # 1 if we have evidence (sleep or known wake)

    # Mark sleep minutes
    for D, info in sleep_per_day.items():
        for s, e in info.get("sleep_minutes", []):
            i0 = max(0, int((s - span_start).total_seconds() // 60))
            i1 = min(n_minutes, int((e - span_start).total_seconds() // 60))
            if i1 > i0:
                sleep[i0:i1] = 1

    # Mark a day as "had a sleep detection" → all minutes in [D-1 18:00, D+1 06:00] valid
    for D, info in sleep_per_day.items():
        if info["coverage"] <= 0:
            continue
        a = datetime.combine(D - timedelta(days=1), time(18, 0))
        b = datetime.combine(D, time(12, 0))
        i0 = max(0, int((a - span_start).total_seconds() // 60))
        i1 = min(n_minutes, int((b - span_start).total_seconds() // 60))
        if i1 > i0:
            valid[i0:i1] = 1

    minutes_per_day = 24 * 60
    out: dict[date, tuple[Optional[float], float]] = {}
    for D in dates:
        # Window of 7 wake-days ending at D inclusive: [D-6, D]
        # For each minute t in [D-6, D+1) compare to t - 1440
        a = datetime.combine(D - timedelta(days=6), time(0, 0))
        b = datetime.combine(D + timedelta(days=1), time(0, 0))
        i0 = int((a - span_start).total_seconds() // 60)
        i1 = int((b - span_start).total_seconds() // 60)
        # pair indices: t and t - minutes_per_day
        if i0 - minutes_per_day < 0:
            out[D] = (None, 0.0); continue
        cur = sleep[i0:i1]
        prev = sleep[i0 - minutes_per_day : i1 - minutes_per_day]
        cur_v = valid[i0:i1]
        prev_v = valid[i0 - minutes_per_day : i1 - minutes_per_day]
        both_valid = (cur_v == 1) & (prev_v == 1)
        n = int(both_valid.sum())
        if n < minutes_per_day * 2:  # require ≥ 2 days of valid pairs
            out[D] = (None, 0.0); continue
        agree = float(((cur == prev) & both_valid).sum()) / n
        coverage = float(n) / float(7 * minutes_per_day)
        out[D] = (100.0 * agree, min(1.0, coverage))
    return out


# ---------- Screen, mobility, app, comm per day ----------

def _day_window(D: date, day_start_hour: int = 4) -> tuple[datetime, datetime]:
    """Day boundary at 04:00 to keep late-night screen attached to the right date."""
    return (datetime.combine(D, time(day_start_hour, 0)),
            datetime.combine(D + timedelta(days=1), time(day_start_hour, 0)))


def screen_minutes_unlocked(locked: pd.DataFrame, lo: datetime, hi: datetime) -> float:
    """Active-screen minutes within [lo, hi].

    StudentLife `phonelock` rows record (start_locked, unlocked_at). Between
    consecutive rows the phone is unlocked. We only count unlock time we have
    direct evidence for: the gap between row[i].end and row[i+1].start,
    clipped into [lo, hi]. This is more conservative than `total_window -
    locked_minutes` (which silently treats unrecorded periods as unlocked).
    """
    if len(locked) == 0:
        return 0.0
    # Collect locked intervals within or touching the window
    starts = locked["start"].values
    ends = locked["end"].values
    # Use only rows whose unlock time (end) ≤ next row's lock time (start) is within window
    n = len(starts)
    unlock_min = 0.0
    for i in range(n - 1):
        unlock_s = ends[i]
        unlock_e = starts[i + 1]
        if unlock_e <= unlock_s:
            continue
        c = _clip(pd.Timestamp(unlock_s).to_pydatetime(),
                  pd.Timestamp(unlock_e).to_pydatetime(), lo, hi)
        if c:
            unlock_min += (c[1] - c[0]).total_seconds() / 60.0
    return float(unlock_min)


def screen_coverage(locked: pd.DataFrame, lo: datetime, hi: datetime) -> float:
    """Coverage: fraction of [lo, hi] bracketed by locked-interval evidence.

    Defined as (last_locked_end_in_window - first_locked_start_in_window) /
    window_length. 0 if no rows touch the window.
    """
    if len(locked) == 0:
        return 0.0
    mask = (locked["start"] < hi) & (locked["end"] > lo)
    seg = locked.loc[mask]
    if len(seg) == 0:
        return 0.0
    span_lo = max(lo, seg["start"].min())
    span_hi = min(hi, seg["end"].max())
    win = (hi - lo).total_seconds()
    if win <= 0:
        return 0.0
    return float(max(0.0, (span_hi - span_lo).total_seconds()) / win)


def mobility_markers(wloc: pd.DataFrame, lo: datetime, hi: datetime
                     ) -> tuple[Optional[float], Optional[float], float]:
    """Returns (entropy_nats, top3_revisit_ratio, coverage)."""
    if len(wloc) == 0:
        return None, None, 0.0
    seg = wloc[(wloc["time"] >= lo) & (wloc["time"] < hi)].copy()
    if len(seg) < 5:
        return None, None, 0.0
    # Dwell = time until next sample, capped at 30 min to avoid huge gaps dominating.
    seg = seg.sort_values("time").reset_index(drop=True)
    nxt = seg["time"].shift(-1).fillna(pd.Timestamp(hi))
    dwell = (nxt - seg["time"]).dt.total_seconds().clip(lower=0, upper=30 * 60)
    counts = Counter()
    for loc, d in zip(seg["location"], dwell):
        counts[loc] += float(d)
    total = sum(counts.values())
    if total <= 0:
        return None, None, 0.0
    probs = np.array([c / total for c in counts.values()], dtype=float)
    probs = probs[probs > 0]
    entropy = float(-np.sum(probs * np.log(probs)))
    top3 = sorted(counts.values(), reverse=True)[:3]
    revisit = float(sum(top3) / total)
    coverage = min(1.0, total / (12 * 3600.0))  # 12 active hours = full coverage
    return entropy, revisit, coverage


def app_switching_markers(apps: pd.DataFrame, locked: pd.DataFrame,
                          lo: datetime, hi: datetime) -> tuple[Optional[float], float]:
    """Switches per active (unlocked) minute, plus coverage."""
    if len(apps) == 0:
        return None, 0.0
    seg = apps[(apps["time"] >= lo) & (apps["time"] < hi)]
    if len(seg) < 5:
        return None, 0.0
    pkgs = seg["package"].values
    switches = int(np.sum(pkgs[1:] != pkgs[:-1]))
    active_min = screen_minutes_unlocked(locked, lo, hi)
    if active_min < 5:
        return None, 0.0
    rate = switches / active_min
    return float(rate), 1.0


def comm_reciprocity(sms: pd.DataFrame, calls: pd.DataFrame,
                     lo: datetime, hi: datetime) -> tuple[Optional[float], float]:
    seg_sms  = sms[(sms["time"] >= lo) & (sms["time"] < hi)] if len(sms) else sms
    seg_call = calls[(calls["time"] >= lo) & (calls["time"] < hi)] if len(calls) else calls
    out = int(seg_sms["outgoing"].sum() + seg_call["outgoing"].sum())
    inc = int((~seg_sms["outgoing"]).sum() + (~seg_call["outgoing"]).sum())
    total = out + inc
    if total < 3:
        return None, 0.0
    return out / total, 1.0


def social_rhythm_metric(sensors: dict, D: date,
                         history_days: int = 7) -> tuple[Optional[float], float]:
    """Proxy for Monk SRM-5: count of today's daily anchor events that fall
    within ±90 minutes of their own 7-day median.

    Anchors used (whichever exist on the day): first phone unlock, first
    non-home location, first communication event, last phone unlock.
    SRM = #anchors_within_band / #anchors_today_with_history. Range [0, 1].
    """
    locked = sensors["locked"]; wloc = sensors["wloc"]
    sms = sensors["sms"]; calls = sensors["calls"]

    def _anchors(day: date) -> dict[str, float]:
        a = {}
        lo = datetime.combine(day, time(4, 0))
        hi = datetime.combine(day + timedelta(days=1), time(4, 0))
        # First unlock today: end of first locked interval intersecting day window
        if len(locked):
            seg = locked[(locked["start"] < hi) & (locked["end"] > lo)]
            if len(seg):
                first_unlock = seg["end"].min()
                if lo <= first_unlock < hi:
                    a["first_unlock"] = (first_unlock - lo).total_seconds() / 3600.0
                last_unlock = seg["end"].max()
                if lo <= last_unlock < hi:
                    a["last_unlock"] = (last_unlock - lo).total_seconds() / 3600.0
        # First non-dorm location event
        if len(wloc):
            seg = wloc[(wloc["time"] >= lo) & (wloc["time"] < hi)]
            non_dorm = seg[~seg["location"].str.contains(
                "wheelock|mclaughlin|dorm|north-park|south-park|ripley|woodward|"
                "topliff|streeter|andres|morton|latin-way|fahey|gile|judge|"
                "butterfield|zimmerman|channing-cox|lord|cohen|russell-sage|"
                "massrow|maxwell|richardson|smith|brace-commons|new-hamp",
                case=False, regex=True, na=False)]
            if len(non_dorm):
                t = non_dorm["time"].iloc[0]
                a["first_outside"] = (t - lo).total_seconds() / 3600.0
        # First communication
        comm_times = []
        if len(sms):
            seg = sms[(sms["time"] >= lo) & (sms["time"] < hi)]
            if len(seg): comm_times.append(seg["time"].iloc[0])
        if len(calls):
            seg = calls[(calls["time"] >= lo) & (calls["time"] < hi)]
            if len(seg): comm_times.append(seg["time"].iloc[0])
        if comm_times:
            t = min(comm_times)
            a["first_comm"] = (t - lo).total_seconds() / 3600.0
        return a

    today = _anchors(D)
    if not today:
        return None, 0.0
    # Build history of last N days
    history: dict[str, list[float]] = {k: [] for k in today}
    n_hist_days = 0
    for k in range(1, history_days + 1):
        Dh = D - timedelta(days=k)
        ah = _anchors(Dh)
        if not ah:
            continue
        n_hist_days += 1
        for kk, v in ah.items():
            if kk in history:
                history[kk].append(v)
    if n_hist_days < 3:
        return None, 0.0
    band_h = 1.5
    used = 0
    hits = 0
    for kk, v in today.items():
        if len(history[kk]) >= 3:
            med = float(np.median(history[kk]))
            used += 1
            if abs(v - med) <= band_h:
                hits += 1
    if used == 0:
        return None, 0.0
    return hits / used, min(1.0, n_hist_days / history_days)


# ---------- Main: build per-day records ----------

def participant_date_range(sensors: dict) -> list[date]:
    starts, ends = [], []
    for key in ("locked", "dark"):
        df = sensors[key]
        if len(df):
            starts.append(df["start"].min()); ends.append(df["end"].max())
    for key in ("wloc", "apps", "sms", "calls"):
        df = sensors[key]
        if len(df):
            starts.append(df["time"].min()); ends.append(df["time"].max())
    if not starts:
        return []
    d0 = min(starts).date()
    d1 = max(ends).date()
    return [d0 + timedelta(days=i) for i in range((d1 - d0).days + 1)]


def build_daily_records(pid: str,
                        sensors: Optional[dict] = None) -> list[dict]:
    """Return a list of raw_day dicts (input shape expected by markers_from_raw),
    one per date in the participant's data range."""
    if sensors is None:
        sensors = load_pid_sensors(pid)
    dates = participant_date_range(sensors)
    if not dates:
        return []

    locked = sensors["locked"]
    dark   = sensors["dark"]
    wloc   = sensors["wloc"]
    apps   = sensors["apps"]
    sms    = sensors["sms"]
    calls  = sensors["calls"]

    sleep_info = detect_sleep_per_day(locked, dark, dates)
    sri_info   = compute_sri_series(sleep_info, dates)

    raw_days = []
    for D in dates:
        lo, hi = _day_window(D, day_start_hour=4)
        # Sleep markers (assigned to wake-date D)
        si = sleep_info.get(D, {"onset": None, "duration": None, "coverage": 0.0})
        sri_val, sri_cov = sri_info.get(D, (None, 0.0))

        # Late-night screen window: [D-1 23:00, D 04:00]
        lnlo = datetime.combine(D - timedelta(days=1), time(23, 0))
        lnhi = datetime.combine(D, time(4, 0))
        late_screen = screen_minutes_unlocked(locked, lnlo, lnhi)
        late_cov = screen_coverage(locked, lnlo, lnhi)

        # Total screen for D
        total_screen = screen_minutes_unlocked(locked, lo, hi)
        total_cov = screen_coverage(locked, lo, hi)

        # App switching
        app_rate, app_cov = app_switching_markers(apps, locked, lo, hi)

        # Mobility
        ent, revisit, mob_cov = mobility_markers(wloc, lo, hi)

        # Comm reciprocity
        recip, recip_cov = comm_reciprocity(sms, calls, lo, hi)

        # Social rhythm
        srm, srm_cov = social_rhythm_metric(sensors, D)

        raw_day = {
            "date": D,
            "sleep_onset_hour":       si["onset"],
            "sleep_duration_hours":   si["duration"],
            "sleep_regularity_index": sri_val,
            "late_night_screen_min":  late_screen if late_cov > 0 else None,
            "total_screen_min":       total_screen if total_cov > 0 else None,
            "app_switching_rate":     app_rate,
            "mobility_entropy":       ent,
            "location_revisit_ratio": revisit,
            "social_rhythm_metric":   srm,
            "comm_reciprocity":       recip,
            "_coverage": {
                "sleep_onset_hour":       si["coverage"],
                "sleep_duration_hours":   si["coverage"],
                "sleep_regularity_index": sri_cov,
                "late_night_screen_min":  late_cov,
                "total_screen_min":       total_cov,
                "app_switching_rate":     app_cov,
                "mobility_entropy":       mob_cov,
                "location_revisit_ratio": mob_cov,
                "social_rhythm_metric":   srm_cov,
                "comm_reciprocity":       recip_cov,
            },
        }
        raw_days.append(raw_day)
    return raw_days


def list_participants() -> list[str]:
    """All pids that have phonelock + Stress EMA available."""
    lock_pids = {p.stem.replace("phonelock_", "")
                 for p in (SENSING / "phonelock").glob("phonelock_*.csv")}
    return sorted(lock_pids)
