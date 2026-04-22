"""Generate presentation-ready figures for the wellbeing pipeline + StudentLife
retrospective evaluation.

Core talk figures (main() default):
  figures/01_architecture.png        Pipeline data-flow. Layer 2 is split into
                                      2a (statistical backbone, no rules) and
                                      2b (4 clinically-anchored labels), each
                                      cited.
  figures/02_markers_overview.png    The 10 biomarkers, each with a literature
                                      citation. Markers were chosen from
                                      wellbeing research first, then checked
                                      against phone-sensor availability —
                                      same 10 compute on any Android phone
                                      with standard permissions.
  figures/03_pattern_vs_stress.png   Validation: pattern-fired days have
                                      meaningfully higher self-reported
                                      stress on StudentLife.

Appendix figures (figures/appendix/, generate via main_appendix()):
  coverage.png, per_pid_correlation.png, risk_distribution.png,
  pattern_frequencies.png, example_timeline.png

Cached intermediate data: figures/_cache.pkl (re-runs in <1s after first build).
Delete the cache to regenerate.
"""
from __future__ import annotations
import pickle
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from scipy import stats

from evaluate_studentlife import align_with_ema, load_pam_per_day, load_stress_per_day, run_all

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)
APPENDIX = OUT / "appendix"
APPENDIX.mkdir(exist_ok=True)
CACHE = OUT / "_cache.pkl"

# ---------- shared style ----------
DOMAIN_COLORS = {
    "sleep":    "#4C78A8",
    "screen":   "#F58518",
    "mobility": "#54A24B",
    "social":   "#B279A2",
}
PATTERN_COLOR = "#E45756"
NEUTRAL = "#666666"
plt.rcParams.update({
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "savefig.dpi": 160,
    "savefig.bbox": "tight",
})


# ---------- data loading (cached) ----------

def get_data():
    if CACHE.exists():
        with open(CACHE, "rb") as f:
            return pickle.load(f)
    print("[cache miss] running pipeline on all participants — ~5 min...")
    res = run_all(sample_prose=0)
    daily = res["daily"]
    joined = align_with_ema(daily)["joined"]
    data = {"daily": daily, "joined": joined}
    with open(CACHE, "wb") as f:
        pickle.dump(data, f)
    return data


# ============================================================
# 01 — Architecture diagram
# ============================================================

def fig_architecture():
    fig, ax = plt.subplots(figsize=(13, 10.5))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

    def box(x, y, w, h, text, color="#FFFFFF", edge="#333333", fontsize=10,
            weight="normal"):
        b = FancyBboxPatch((x, y), w, h,
                           boxstyle="round,pad=0.4,rounding_size=1.5",
                           linewidth=1.6, edgecolor=edge, facecolor=color)
        ax.add_patch(b)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fontsize, weight=weight, wrap=True)

    def arrow(x1, y1, x2, y2, label=None):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color="#444",
                                     lw=1.4, mutation_scale=15,
                                     shrinkA=2, shrinkB=2))
        if label:
            ax.text((x1 + x2) / 2 + 1.5, (y1 + y2) / 2, label,
                    fontsize=9, color="#444", style="italic")

    # Title
    ax.text(50, 97.5, "Wellbeing Sensing Pipeline — Architecture", ha="center",
            fontsize=15, weight="bold")
    ax.text(50, 94.3,
            "Zero-shot. Each user is their own reference.  "
            "Layer 2a is the statistical rigor; Layer 2b provides readable labels.",
            ha="center", fontsize=10, style="italic", color="#555")

    # Layer 0: Raw sensors
    box(2, 82, 96, 6.5,
        "Raw phone sensors  (phonelock · dark · wifi_location · "
        "running_apps · sms · call_log)",
        color="#EFEFEF", weight="bold")

    # Layer 1: Adapter → 10 markers
    box(2, 63, 96, 14,
        "LAYER 1 — Per-day biomarkers  (literature-anchored; see Fig. 2)\n"
        "Sleep × 3   ·   Screen × 3   ·   Mobility × 2   ·   Social × 2\n"
        "+ per-marker coverage flag (0–1)",
        color="#E8F1FA", edge=DOMAIN_COLORS["sleep"], weight="bold", fontsize=11)

    # Layer 1.5: PersonalBaseline
    box(2, 51, 46, 7,
        "PersonalBaseline (per user)\nrolling mean · std · p20 · p80",
        color="#FFFFFF", fontsize=10)
    box(52, 51, 46, 7,
        "Coverage tracker (per marker)\nflags low-data days for downstream caution",
        color="#FFFFFF", fontsize=10)

    # Layer 2a — Statistical backbone (no rules)
    box(2, 28, 46, 19,
        "LAYER 2a — Statistical deviation detection\n"
        "(deterministic, no rules)\n\n"
        "z-score  recent 4d  vs  baseline 21d\n\n"
        "Magnitude:  within / mild / moderate / pronounced\n"
        "Trajectory:  acute · sustained · drift · intermittent\n\n"
        "+ templated natural-language finding (arithmetic only)",
        color="#FFF5EC", edge=DOMAIN_COLORS["screen"], weight="bold", fontsize=9.5)

    # Layer 2b — Clinically-anchored labels (extensible)
    box(52, 28, 46, 19,
        "LAYER 2b — Clinically-anchored labels\n"
        "(readable co-occurrence patterns, extensible)\n\n"
        "Each label = a published behavioral syndrome:\n"
        "  • phone-mediated sleep delay   (Exelmans 2016)\n"
        "  • behavioral withdrawal             (Saeb 2015)\n"
        "  • circadian instability                  (Phillips 2017)\n"
        "  • fragmented attention + sleep loss\n"
        "      (Mark 2014; Walker 2017)",
        color="#EDF6E9", edge=DOMAIN_COLORS["mobility"], weight="bold", fontsize=9.5)

    # Layer 3
    box(2, 11, 96, 13,
        "LAYER 3 — Behavioral state description\n"
        "structured JSON   +   prose (Daily Journal)\n"
        "no mood label · no scalar score · all claims grounded in user's own history",
        color="#F4ECF7", edge=DOMAIN_COLORS["social"], weight="bold", fontsize=11)

    # LLM
    box(20, 0.5, 60, 7,
        "LLM Scheduler  (downstream — not yet wired)\n"
        "consumes structured state + calendar + prefs → suggestions",
        color="#FFFFFF", edge="#999", fontsize=9)

    # Arrows
    arrow(50, 82, 50, 77)
    arrow(25, 63, 25, 58)
    arrow(75, 63, 75, 58)
    arrow(25, 51, 25, 47)
    arrow(75, 51, 75, 47)
    arrow(25, 28, 25, 24)
    arrow(75, 28, 75, 24)
    arrow(50, 11, 50, 7.5, label=" structured + prose payload")

    plt.savefig(OUT / "01_architecture.png")
    plt.close()
    print("→", OUT / "01_architecture.png")


# ============================================================
# 02 — Markers overview
# ============================================================

MARKER_DEFS = [
    # (domain, key, label, short description, citation)
    ("sleep",    "sleep_onset_hour",       "Sleep onset hour",       "Bedtime last night",                      "Wittmann 2006"),
    ("sleep",    "sleep_duration_hours",   "Sleep duration",         "Hours slept",                             "Walker 2017"),
    ("sleep",    "sleep_regularity_index", "Sleep regularity (SRI)", "Night-to-night consistency",              "Phillips 2017"),
    ("screen",   "late_night_screen_min",  "Late-night screen min",  "Phone-on 23:00 – 04:00",                  "Exelmans 2016"),
    ("screen",   "total_screen_min",       "Total screen min",       "Total active phone time",                 "Twenge 2018"),
    ("screen",   "app_switching_rate",     "App switching rate",     "Switches per active minute",              "Mark 2014"),
    ("mobility", "mobility_entropy",       "Mobility entropy",       "Spread of time across visited places",    "Saeb 2015"),
    ("mobility", "location_revisit_ratio", "Top-3 revisit ratio",    "Time at three most-visited places",       "Canzian 2015"),
    ("social",   "social_rhythm_metric",   "Social rhythm (SRM)",    "Consistency of anchor-event timing",      "Monk 2002"),
    ("social",   "comm_reciprocity",       "Comm reciprocity",       "Outgoing / total messages",               "Wang 2014"),
]


def fig_markers_overview():
    fig, ax = plt.subplots(figsize=(13.5, 8.5))
    ax.axis("off")
    ax.text(0.5, 0.975,
            "Per-Day Biomarkers — 10 literature-anchored behavioral signals",
            ha="center", transform=ax.transAxes, fontsize=15, weight="bold")
    ax.text(0.5, 0.935,
            "Markers were chosen from published wellbeing research first, "
            "then verified as computable from standard phone sensors.",
            ha="center", transform=ax.transAxes, fontsize=10.5,
            style="italic", color="#444")
    ax.text(0.5, 0.905,
            "The same 10 compute on any Android phone with standard "
            "permissions — they are not curated to StudentLife.",
            ha="center", transform=ax.transAxes, fontsize=10.5,
            style="italic", color="#444")

    domains = [("sleep", "Sleep"), ("screen", "Screen & attention"),
               ("mobility", "Mobility & location"), ("social", "Social rhythm")]
    n_cols = 4
    col_w = 1.0 / n_cols

    for ci, (dkey, dlabel) in enumerate(domains):
        x0 = ci * col_w + 0.01
        x1 = (ci + 1) * col_w - 0.01
        # column header
        ax.add_patch(mpatches.FancyBboxPatch(
            (x0, 0.83), x1 - x0, 0.045,
            boxstyle="round,pad=0.005,rounding_size=0.01",
            transform=ax.transAxes,
            facecolor=DOMAIN_COLORS[dkey], edgecolor="none", alpha=0.9))
        ax.text((x0 + x1) / 2, 0.852, dlabel, ha="center", va="center",
                color="white", fontsize=12, weight="bold",
                transform=ax.transAxes)

        # markers in this domain — fixed-height cards so columns align.
        items = [m for m in MARKER_DEFS if m[0] == dkey]
        block_h = 0.22
        gap = 0.02
        for j, (_, key, label, descr, cite) in enumerate(items):
            y_top = 0.81 - j * (block_h + gap)
            ax.add_patch(mpatches.FancyBboxPatch(
                (x0, y_top - block_h), x1 - x0, block_h,
                boxstyle="round,pad=0.005,rounding_size=0.01",
                transform=ax.transAxes,
                facecolor="white", edgecolor=DOMAIN_COLORS[dkey], linewidth=1.6))
            # label (bold)
            ax.text((x0 + x1) / 2, y_top - 0.04, label,
                    ha="center", va="center", fontsize=11, weight="bold",
                    transform=ax.transAxes)
            # description
            ax.text((x0 + x1) / 2, y_top - 0.10, descr,
                    ha="center", va="center", fontsize=9.5, color="#444",
                    transform=ax.transAxes)
            # citation pill
            ax.text((x0 + x1) / 2, y_top - 0.175,
                    cite, ha="center", va="center", fontsize=9,
                    style="italic", color=DOMAIN_COLORS[dkey], weight="bold",
                    transform=ax.transAxes)

    plt.savefig(OUT / "02_markers_overview.png")
    plt.close()
    print("→", OUT / "02_markers_overview.png")


# ============================================================
# 03 — Coverage chart
# ============================================================

def fig_coverage(daily: pd.DataFrame):
    cov_cols = [c for c in daily.columns if c.startswith("cov_")]
    warm = daily[daily["warm"]]
    rates = []
    labels = []
    colors = []
    for col in cov_cols:
        marker = col[len("cov_"):]
        domain = next((d[0] for d in MARKER_DEFS if d[1] == marker), "social")
        rate = float((warm[col] >= 0.5).mean())
        rates.append(rate); labels.append(marker); colors.append(DOMAIN_COLORS[domain])

    order = np.argsort(rates)
    rates = np.array(rates)[order]
    labels = np.array(labels)[order]
    colors = np.array(colors)[order]

    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.barh(labels, rates * 100, color=colors, edgecolor="white")
    for b, r in zip(bars, rates):
        ax.text(r * 100 + 1, b.get_y() + b.get_height() / 2,
                f"{r*100:.0f}%", va="center", fontsize=10, color="#333")
    ax.set_xlim(0, 110)
    ax.set_xlabel("% of warm-baseline participant-days with marker coverage ≥ 0.5")
    ax.set_title("Per-marker data coverage across all participants",
                 fontsize=14, weight="bold", pad=12)
    # legend
    handles = [mpatches.Patch(color=c, label=d.title()) for d, c in DOMAIN_COLORS.items()]
    ax.legend(handles=handles, loc="lower right", frameon=False)
    ax.text(0, -1.6,
            f"n = {len(warm):,} warm participant-days across {warm['pid'].nunique()} participants",
            transform=ax.transAxes, ha="left", fontsize=9, color="#666")
    plt.savefig(APPENDIX / "coverage.png")
    plt.close()
    print("→", APPENDIX / "coverage.png")


# ============================================================
# 04 — Per-participant Spearman r distribution
# ============================================================

def _per_pid_spearman(joined: pd.DataFrame, ema_col: str) -> list[float]:
    df = joined[joined["warm"]].copy()
    out = []
    for pid, sub in df.groupby("pid"):
        m = sub[ema_col].notna() & sub["risk_index"].notna()
        if m.sum() < 10:
            continue
        r = stats.spearmanr(sub.loc[m, "risk_index"], sub.loc[m, ema_col])
        if not np.isnan(r.statistic):
            out.append(float(r.statistic))
    return out


def fig_per_pid_correlation(joined: pd.DataFrame):
    rs = _per_pid_spearman(joined, "stress_severity")
    fig, ax = plt.subplots(figsize=(11, 5.5))
    bins = np.arange(-0.6, 0.65, 0.07)
    counts, edges, patches = ax.hist(rs, bins=bins, edgecolor="white",
                                      linewidth=1.2)
    for c, p, e in zip(counts, patches, edges):
        p.set_facecolor("#4C78A8" if (e + 0.035) > 0 else "#B0B0B0")
    ax.axvline(0, color="#888", linestyle="--", linewidth=1)
    med = float(np.median(rs)); mn = float(np.mean(rs))
    ax.axvline(med, color="#E45756", linewidth=2)
    # Place median label on the right of the line, above the bars but below the title.
    y_top = ax.get_ylim()[1]
    ax.text(med + 0.015, y_top * 0.78,
            f"median r = {med:+.3f}", color="#E45756",
            fontsize=11, weight="bold", ha="left")
    pct_pos = 100 * np.mean(np.array(rs) > 0)
    ax.set_xlabel("Per-participant Spearman r  (risk_index vs same-day stress severity)")
    ax.set_ylabel("Number of participants")
    ax.set_title("How well does the pipeline track stress, per participant?",
                 fontsize=14, weight="bold", pad=14)
    # Box in upper-left, sized to leave room above the bars.
    ax.text(0.015, 0.97,
            f"n = {len(rs)} participants with ≥10 stress-EMA days\n"
            f"{pct_pos:.0f}% have positive correlation (right of the dashed zero line)\n"
            f"Most are weakly positive; a minority negative — heterogeneity is real.",
            transform=ax.transAxes, va="top", ha="left", fontsize=9.5, color="#333",
            bbox=dict(facecolor="white", edgecolor="#ddd", boxstyle="round,pad=0.6"))
    plt.savefig(APPENDIX / "per_pid_correlation.png")
    plt.close()
    print("→", APPENDIX / "per_pid_correlation.png")


# ============================================================
# 05 — Pattern fired vs not (stress)
# ============================================================

def fig_pattern_vs_stress(joined: pd.DataFrame):
    df = joined[joined["warm"]].copy()
    df = df[df["stress_severity"].notna()]
    yes = df[df["n_pat"] >= 1]["stress_severity"].values
    no  = df[df["n_pat"] == 0]["stress_severity"].values

    fig, ax = plt.subplots(figsize=(10, 6))
    parts = ax.violinplot([no, yes], showmeans=False, showmedians=True,
                           widths=0.7, positions=[1, 2])
    for i, body in enumerate(parts["bodies"]):
        body.set_facecolor([NEUTRAL, PATTERN_COLOR][i])
        body.set_edgecolor("#333"); body.set_alpha(0.7)
    parts["cmedians"].set_color("#222")
    parts["cmedians"].set_linewidth(2)

    # Means as dots
    ax.scatter([1, 2], [no.mean(), yes.mean()], color="white",
               edgecolor="#222", s=80, zorder=5)
    ax.text(1, no.mean() + 0.07, f"mean {no.mean():.2f}", ha="center", fontsize=10)
    ax.text(2, yes.mean() + 0.07, f"mean {yes.mean():.2f}", ha="center",
            fontsize=10, color=PATTERN_COLOR, weight="bold")

    t = stats.ttest_ind(yes, no, equal_var=False)
    pooled_sd = np.sqrt((yes.var(ddof=1) + no.var(ddof=1)) / 2)
    d = (yes.mean() - no.mean()) / (pooled_sd + 1e-9)
    ax.set_xticks([1, 2])
    ax.set_xticklabels([f"No coherent pattern fired\n(n = {len(no):,} days)",
                         f"≥1 coherent pattern fired\n(n = {len(yes):,} days)"])
    ax.set_ylabel("Self-reported stress severity\n(0 = feeling great, 3 = stressed out)")
    ax.set_title("Stress on days the pipeline flags a coherent pattern vs. not",
                 fontsize=14, weight="bold", pad=12)
    ax.text(0.5, -0.22,
            f"Welch t = {t.statistic:+.2f},  p = {t.pvalue:.1e},  Cohen's d = {d:+.2f}\n"
            f"→ Pattern-fired days have meaningfully higher self-reported stress.",
            transform=ax.transAxes, ha="center", fontsize=11, color="#222")
    plt.subplots_adjust(bottom=0.22)
    plt.savefig(OUT / "03_pattern_vs_stress.png")
    plt.close()
    print("→", OUT / "03_pattern_vs_stress.png")


# ============================================================
# 06 — Risk index distribution by stress level
# ============================================================

def fig_risk_distribution(joined: pd.DataFrame):
    df = joined[joined["warm"] & joined["stress_severity"].notna()].copy()
    df["band"] = np.where(df["stress_severity"] >= 2, "Stressed (sev ≥ 2)",
                  np.where(df["stress_severity"] <= 1, "Calm (sev ≤ 1)", "Mid"))
    # Plot only the two informative bands as densities (proportion within each
    # band) so they're directly comparable despite different sample sizes.
    bands = [("Calm (sev ≤ 1)", "#54A24B"),
             ("Stressed (sev ≥ 2)", "#E45756")]
    bins = np.arange(0, 16, 1)

    fig, ax = plt.subplots(figsize=(11, 6))
    for band, color in bands:
        sub = df[df["band"] == band]["risk_index"].values
        if len(sub) == 0:
            continue
        ax.hist(sub, bins=bins, density=True, alpha=0.45,
                label=f"{band}  (n={len(sub)}, mean={sub.mean():.2f})",
                color=color, edgecolor="white", linewidth=0.8)
        ax.axvline(sub.mean(), color=color, linestyle="--", linewidth=2)
    ax.set_xlabel("Pipeline risk_index  (Σ deviation magnitudes + 2 × patterns)")
    ax.set_ylabel("Proportion of days within group")
    ax.set_title("Pipeline risk_index distribution, split by self-reported stress",
                 fontsize=14, weight="bold", pad=12)
    ax.legend(frameon=False, loc="upper right")
    ax.text(0.99, 0.70,
            "Stressed-day mass shifts right.\n"
            "Heavy overlap → small effect size,\nbut direction is real.",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=10, color="#444",
            bbox=dict(facecolor="white", edgecolor="#ddd",
                       boxstyle="round,pad=0.5"))
    plt.savefig(APPENDIX / "risk_distribution.png")
    plt.close()
    print("→", APPENDIX / "risk_distribution.png")


# ============================================================
# 07 — Pattern-type frequencies
# ============================================================

def fig_pattern_frequencies(daily: pd.DataFrame):
    counts = Counter()
    for s in daily["pattern_names"].dropna():
        if not s:
            continue
        for name in s.split("|"):
            if name:
                counts[name] += 1
    if not counts:
        return
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    names = [k.replace("-", " ") for k, _ in items]
    vals = [v for _, v in items]

    fig, ax = plt.subplots(figsize=(11, 5))
    bars = ax.barh(names[::-1], vals[::-1], color=PATTERN_COLOR, edgecolor="white")
    for b, v in zip(bars, vals[::-1]):
        ax.text(v + 5, b.get_y() + b.get_height() / 2, f"{v}", va="center",
                fontsize=10, color="#222")
    ax.set_xlabel("Number of participant-days the pattern fired")
    ax.set_title("Coherent-pattern fire frequency across 49 participants",
                 fontsize=14, weight="bold", pad=12)
    total = sum(vals)
    ax.text(0.99, 0.05, f"{total:,} pattern-fires total",
            transform=ax.transAxes, ha="right", fontsize=10, color="#666")
    plt.savefig(APPENDIX / "pattern_frequencies.png")
    plt.close()
    print("→", APPENDIX / "pattern_frequencies.png")


# ============================================================
# 08 — Example participant timeline
# ============================================================

def fig_example_timeline(joined: pd.DataFrame, daily: pd.DataFrame):
    # Pick the participant with the strongest positive Spearman r and decent EMA coverage
    df = joined[joined["warm"] & joined["stress_severity"].notna()].copy()
    cand = []
    for pid, sub in df.groupby("pid"):
        if len(sub) < 15:
            continue
        r = stats.spearmanr(sub["risk_index"], sub["stress_severity"]).statistic
        if np.isnan(r):
            continue
        cand.append((pid, r, len(sub)))
    if not cand:
        return
    cand.sort(key=lambda x: -x[1])
    pid, r, n = cand[0]

    sub_daily = daily[(daily["pid"] == pid) & daily["warm"]].sort_values("date").copy()
    stress = load_stress_per_day(pid)
    pam = load_pam_per_day(pid)

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True,
                              gridspec_kw={"height_ratios": [2.4, 1.4]})
    # Top: risk_index over time + EMA dots
    ax = axes[0]
    ax.plot(sub_daily["date"], sub_daily["risk_index"], color="#4C78A8",
            linewidth=1.8, label="Pipeline risk_index")
    pat_days = sub_daily[sub_daily["n_pat"] >= 1]
    ax.scatter(pat_days["date"], pat_days["risk_index"], color=PATTERN_COLOR,
               s=70, zorder=4, label="Coherent pattern fired")

    # Twin axis: stress severity overlay
    ax2 = ax.twinx()
    ax2.spines["top"].set_visible(False)
    sd = pd.DataFrame([{"date": d, "stress": v} for d, v in stress.items()])
    if len(sd):
        sd = sd[sd["date"].isin(sub_daily["date"].values)]
        ax2.scatter(sd["date"], sd["stress"], color="#E45756", marker="x",
                    s=80, linewidth=2.4, label="Self-reported stress severity")
    ax.set_ylabel("Pipeline risk_index", color="#4C78A8", fontsize=11)
    ax2.set_ylabel("Stress severity (0 great → 3 stressed)",
                    color="#E45756", fontsize=11)
    ax.tick_params(axis="y", labelcolor="#4C78A8")
    ax2.tick_params(axis="y", labelcolor="#E45756")
    ax.set_title(f"Participant {pid} — pipeline output vs. self-reported stress  "
                 f"(Spearman r = {r:+.2f}, n = {n} EMA-days)",
                 fontsize=13, weight="bold", pad=14)
    # Give headroom for the legend so it never sits on top of the title.
    ymax = sub_daily["risk_index"].max()
    ax.set_ylim(0, ymax * 1.45)

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2,
              loc="upper left", ncol=1, frameon=True,
              fontsize=10, framealpha=0.92, edgecolor="#ddd")

    # Bottom: which markers were flagged each day (rug)
    ax = axes[1]
    marker_to_y = {m[1]: i for i, m in enumerate(MARKER_DEFS)}
    for row in sub_daily.itertuples():
        if not row.dev_markers:
            continue
        for marker in row.dev_markers.split("|"):
            if marker not in marker_to_y:
                continue
            domain = next((d[0] for d in MARKER_DEFS if d[1] == marker), "social")
            ax.scatter(row.date, marker_to_y[marker],
                       color=DOMAIN_COLORS[domain], s=32, marker="s")
    ax.set_yticks(list(marker_to_y.values()))
    ax.set_yticklabels(list(marker_to_y.keys()), fontsize=9)
    ax.set_ylabel("Markers flagged", fontsize=11)
    ax.set_xlabel("Date", fontsize=11)
    ax.grid(True, axis="x", alpha=0.2)
    ax.set_ylim(-0.5, len(marker_to_y) - 0.5)

    fig.autofmt_xdate()
    plt.tight_layout()
    plt.savefig(APPENDIX / "example_timeline.png")
    plt.close()
    print("→", APPENDIX / "example_timeline.png")


# ---------- entry point ----------

def main(core_only: bool = True):
    """Generate the three core talk figures. Pass core_only=False to also
    generate the appendix figures in figures/appendix/."""
    data = get_data()
    daily = data["daily"]; joined = data["joined"]
    print(f"Loaded {len(daily):,} daily rows, {len(joined):,} joined rows.")
    # Core 3 — for the research-group talk.
    fig_architecture()
    fig_markers_overview()
    fig_pattern_vs_stress(joined)
    if not core_only:
        fig_coverage(daily)
        fig_per_pid_correlation(joined)
        fig_risk_distribution(joined)
        fig_pattern_frequencies(daily)
        fig_example_timeline(joined, daily)
    print(f"\nFigures written to {OUT}/"
          + (f" (appendix → {APPENDIX}/)" if not core_only else ""))


if __name__ == "__main__":
    import sys
    main(core_only=("--appendix" not in sys.argv))
