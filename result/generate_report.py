#!/usr/bin/env python3
"""Generate the NexLev new-high-earners report: PNG charts + Markdown + a disposable HTML viewer.

Reusable: reads result/data/channels.json (durable). On first run it can also parse the raw
NexLev MCP result file if you pass its path as argv[1]. Re-run anytime: `python result/generate_report.py`.
Outputs (all under result/): charts/*.png, report.md, channels_full.csv, view.html (disposable).
"""
from __future__ import annotations
import sys, os, json, csv, datetime as dt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parent           # result/
CHARTS = ROOT / "charts"; DATA = ROOT / "data"
CHARTS.mkdir(exist_ok=True); DATA.mkdir(exist_ok=True)
JSON_PATH = DATA / "channels.json"

# ── Load data ────────────────────────────────────────────────────────────────
def _name(v):
    return (v.get("name") or v.get("title") or "") if isinstance(v, dict) else (v or "")

def load_from_raw(path: str) -> list[dict]:
    outer = json.load(open(path))
    chs = json.loads(outer[1]["text"])["channels"]
    rows = []
    for c in chs:
        s = c.get("stats", {}) or {}; rpm = s.get("rpm", {}) or {}
        rows.append({
            "title": c.get("title", ""), "ytChannelId": c.get("ytChannelId", ""),
            "subs": int(s.get("subscribers") or 0),
            "monthlyRevenue": round(float(s.get("monthlyRevenue") or 0)),
            "monthlyViews": int(s.get("monthlyViews") or 0),
            "totalVideos": int(s.get("totalVideos") or 0),
            "uploadsPerWeek": float(s.get("uploadsPerWeek") or 0),
            "rpm": round(float((rpm.get("total") if isinstance(rpm, dict) else rpm) or 0), 2),
            "firstVideoDate": s.get("firstVideoDate", ""),
            "category": _name(c.get("category")), "format": _name(c.get("format")),
            "outlier": c.get("outlierScore"),
            "faceless": bool(c.get("isFaceless")), "ai": bool(c.get("isAiChannel")),
            "url": f"https://youtube.com/channel/{c.get('ytChannelId','')}",
        })
    return rows

if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
    rows = load_from_raw(sys.argv[1]); json.dump(rows, open(JSON_PATH, "w"), indent=1)
else:
    rows = json.load(open(JSON_PATH))
rows.sort(key=lambda r: r["monthlyRevenue"], reverse=True)

# ── Automation-fit classifier (balanced lens; faceless-AI production target) ──
# Inferred from NexLev category/format — not from watching the videos (caveat noted in report).
def classify(r) -> tuple[str, int, str]:
    blob = f"{r['category']} {r['format']}".lower()
    if any(k in blob for k in ("compilation", "clip", "celebrity")):
        return ("Weak", 65, "Reused clips → copyright/reused-content risk; quality tied to source footage")
    if any(k in blob for k in ("gaming", "minecraft", "gameplay", "cooking", "recipe", "review", "food")):
        return ("Weak", 70, "Needs original/captured footage (gameplay/product/food) → not pure faceless-AI")
    if any(k in blob for k in ("animation", "animated")):
        return ("Moderate", 82, "Animation quality is hard to fully automate at par (AI animation still maturing)")
    if any(k in blob for k in ("news", "politic")):
        return ("Moderate", 82, "Automatable but timeliness + factual-accuracy QC raise the human share")
    if any(k in blob for k in ("health", "medical")):
        return ("Moderate", 80, "YMYL accuracy: script must be fact-checked by a human → higher QC")
    return ("Strong", 92, "Narration-over-stock/AI-visuals: AI script+voice+B-roll covers it cleanly")

for r in rows:
    r["fit"], r["autopct"], r["fit_why"] = classify(r)

FIT_COLOR = {"Strong": "#2e7d32", "Moderate": "#f9a825", "Weak": "#c62828"}

# ── Helpers ──────────────────────────────────────────────────────────────────
def kfmt(n, _=None):
    n = float(n)
    return f"{n/1e6:.1f}M" if n >= 1e6 else (f"{n/1e3:.0f}K" if n >= 1e3 else f"{n:.0f}")

plt.rcParams.update({"figure.dpi": 130, "font.size": 9, "axes.grid": True,
                     "grid.alpha": .25, "axes.axisbelow": True, "savefig.bbox": "tight"})

# Chart 1 — monthly revenue by channel (colored by fit)
fig, ax = plt.subplots(figsize=(9, 8))
y = range(len(rows))
ax.barh([i for i in y], [r["monthlyRevenue"] for r in rows],
        color=[FIT_COLOR[r["fit"]] for r in rows])
ax.set_yticks(list(y)); ax.set_yticklabels([r["title"][:26] for r in rows], fontsize=7.5)
ax.invert_yaxis(); ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x/1000:.0f}K"))
ax.set_xlabel("Estimated monthly revenue (USD)")
ax.set_title("Estimated monthly revenue by channel  (color = automation fit)", fontweight="bold")
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=c, label=l) for l, c in FIT_COLOR.items()],
          title="Automation fit", fontsize=8, loc="lower right")
fig.savefig(CHARTS / "revenue_by_channel.png"); plt.close(fig)

# Chart 2 — start-date distribution (channel creation)
dates = [dt.date.fromisoformat(r["firstVideoDate"]) for r in rows if r["firstVideoDate"]]
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.hist([d.toordinal() for d in dates], bins=10, color="#1565c0", edgecolor="white")
locs = sorted({dt.date(d.year, d.month, 1) for d in dates})
ax.set_xticks([d.toordinal() for d in locs])
ax.set_xticklabels([d.strftime("%b %Y") for d in locs])
ax.set_ylabel("# channels"); ax.set_xlabel("First upload (channel start)")
ax.set_title("When these channels started — all 1–3 months old", fontweight="bold")
fig.savefig(CHARTS / "start_dates.png"); plt.close(fig)

# Chart 3 — niche breakdown
from collections import Counter
cats = Counter(r["category"].title() for r in rows if r["category"])
items = cats.most_common()
fig, ax = plt.subplots(figsize=(8, 4.6))
ax.barh([k for k, _ in items][::-1], [v for _, v in items][::-1], color="#00838f")
ax.set_xlabel("# channels"); ax.set_title("Niche breakdown (NexLev category)", fontweight="bold")
for i, (_, v) in enumerate(items[::-1]):
    ax.text(v + .05, i, str(v), va="center", fontsize=8)
fig.savefig(CHARTS / "niche_breakdown.png"); plt.close(fig)

# Chart 4 — RPM vs monthly views (the two money models), size=revenue, color=fit
fig, ax = plt.subplots(figsize=(8, 5))
for r in rows:
    ax.scatter(r["monthlyViews"], r["rpm"], s=max(20, r["monthlyRevenue"] / 30),
               color=FIT_COLOR[r["fit"]], alpha=.7, edgecolor="white", linewidth=.5)
for r in rows:
    if r["monthlyRevenue"] > 9000 or r["rpm"] >= 7 or r["monthlyViews"] > 5e6:
        ax.annotate(r["title"][:16], (r["monthlyViews"], r["rpm"]), fontsize=6.5,
                    xytext=(3, 3), textcoords="offset points")
ax.set_xscale("log"); ax.xaxis.set_major_formatter(FuncFormatter(kfmt))
ax.set_xlabel("Monthly views (log)"); ax.set_ylabel("RPM (USD / 1k views)")
ax.set_title("Two money models: high-RPM docs vs high-volume compilations\n(bubble = monthly $)",
             fontweight="bold")
fig.savefig(CHARTS / "rpm_vs_views.png"); plt.close(fig)

# Chart 5 — subs vs revenue
fig, ax = plt.subplots(figsize=(8, 5))
for r in rows:
    ax.scatter(r["subs"], r["monthlyRevenue"], s=60, color=FIT_COLOR[r["fit"]],
               alpha=.75, edgecolor="white", linewidth=.5)
for r in rows:
    if r["monthlyRevenue"] > 9000 or r["subs"] < 6000 or r["subs"] > 38000:
        ax.annotate(r["title"][:16], (r["subs"], r["monthlyRevenue"]), fontsize=6.5,
                    xytext=(3, 3), textcoords="offset points")
ax.xaxis.set_major_formatter(FuncFormatter(kfmt))
ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x/1000:.0f}K"))
ax.set_xlabel("Subscribers"); ax.set_ylabel("Monthly revenue")
ax.set_title("Subscribers vs revenue — subs ≠ money (all < 100k subs)", fontweight="bold")
fig.savefig(CHARTS / "subs_vs_revenue.png"); plt.close(fig)

# Chart 6 — automation fit: count + revenue by tier
tiers = ["Strong", "Moderate", "Weak"]
cnt = [sum(1 for r in rows if r["fit"] == t) for t in tiers]
rev = [sum(r["monthlyRevenue"] for r in rows if r["fit"] == t) for t in tiers]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.6))
a1.bar(tiers, cnt, color=[FIT_COLOR[t] for t in tiers]); a1.set_title("# channels by fit"); a1.set_ylabel("count")
for i, v in enumerate(cnt): a1.text(i, v + .1, str(v), ha="center", fontsize=9)
a2.bar(tiers, rev, color=[FIT_COLOR[t] for t in tiers]); a2.set_title("Total monthly $ by fit")
a2.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x/1000:.0f}K"))
fig.suptitle("Automation-fit distribution", fontweight="bold")
fig.savefig(CHARTS / "automation_fit.png"); plt.close(fig)

# ── Stats for prose ──────────────────────────────────────────────────────────
revs = [r["monthlyRevenue"] for r in rows]
strong = [r for r in rows if r["fit"] == "Strong"]
n_strong = len(strong); n_mod = sum(1 for r in rows if r["fit"] == "Moderate")
n_weak = sum(1 for r in rows if r["fit"] == "Weak")
med = sorted(revs)[len(revs)//2]
strong_rev = sum(r["monthlyRevenue"] for r in strong)
top_cats = ", ".join(f"{k} ({v})" for k, v in cats.most_common(6))

# ── CSV ──────────────────────────────────────────────────────────────────────
cols = ["title","subs","monthlyRevenue","monthlyViews","rpm","firstVideoDate","totalVideos",
        "uploadsPerWeek","category","format","outlier","faceless","ai","fit","autopct","url"]
with open(ROOT / "channels_full.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)

# ── Markdown report ──────────────────────────────────────────────────────────
def md_table(headers, line_rows):
    out = "| " + " | ".join(headers) + " |\n| " + " | ".join("---" for _ in headers) + " |\n"
    for lr in line_rows:
        out += "| " + " | ".join(str(x) for x in lr) + " |\n"
    return out

shortlist = [r for r in rows if r["fit"] in ("Strong", "Moderate")]
appendix_rows = [(i+1, r["title"], kfmt(r["subs"]), f"${r['monthlyRevenue']:,}", kfmt(r["monthlyViews"]),
                  f"${r['rpm']:.2f}", r["firstVideoDate"], r["category"], r["format"],
                  ("—" if r["outlier"] is None else f"{r['outlier']:.1f}"),
                  r["fit"], f"{r['autopct']}%") for i, r in enumerate(rows)]
sl_rows = [(r["title"], r["category"], f"${r['monthlyRevenue']:,}", f"${r['rpm']:.2f}",
            r["fit"], f"{r['autopct']}%", r["fit_why"]) for r in shortlist]

report = f"""# Report — Brand-New YouTube Channels Already Earning $5k+/mo
*Generated {dt.date.today().isoformat()} · source: NexLev niche-finder · 0 additional credits (built from one query)*

**One-line:** 30 channels that are **<100k subscribers**, **started 1–3 months ago**, and **estimated >$5,000/month** —
a screen for "breakout rockets" worth modeling. **All 30 are faceless.** The dominant, most-automatable pattern is the
**faceless documentary / explainer** (history, space, science, stories).

## Methodology & caveats
- **Query (NexLev `search_niche_finder_channels`, filter-only):** `maxSubscribers=100000`, `firstUploadAfter=2026-03-27`,
  `firstUploadBefore=2026-05-27`, `minMonthlyRevenue=5000`, `limit=30`. 53 channels matched; the top 30 by revenue are shown.
- **Revenue/RPM are NexLev *estimates*** (AdSense = views × RPM), not actuals; treat as directional.
- **Automation-fit is inferred from each channel's niche/format**, not from watching the videos. Verifying a specific
  channel (sample video + transcript) is a 1-credit follow-up.
- Defaults used (per your steer): existing data only (no extra credits); **balanced** shortlist lens; production target =
  **fully-automated faceless AI**, with automation % assessed **per channel**.

## Key findings
- **100% faceless** — to reach $5k/mo within 1–3 months, no-face is effectively mandatory.
- **Revenue range ${min(revs):,}–${max(revs):,}/mo** (median **${med:,}**), on **<100k subs** (3K–42K).
- **Faceless documentary/explainer dominates** — niches: {top_cats}. These also carry the **higher RPMs ($5–$8)**.
- **Two money models** (see chart): high-RPM docs (~$5–8 RPM, ~1M views) vs high-volume compilations (~$1.5–3 RPM, 3–9M views).
- **Automation fit:** **{n_strong} Strong**, {n_mod} Moderate, {n_weak} Weak — Strong-fit channels alone represent
  **${strong_rev:,}/mo** of estimated revenue.

![Revenue by channel](charts/revenue_by_channel.png)

![Start dates](charts/start_dates.png)

![Niche breakdown](charts/niche_breakdown.png)

![RPM vs views](charts/rpm_vs_views.png)

![Subs vs revenue](charts/subs_vs_revenue.png)

![Automation fit](charts/automation_fit.png)

## The automation thesis (can we hit "equivalent or better" at 80–95% automation?)
**Yes — for the documentary/explainer/story lane.** That format is *narration over visuals*, which maps cleanly to a
faceless-AI pipeline:

| Stage | Automated? | How |
|---|---|---|
| Topic / trend pick | ✅ | LLM + NexLev outliers/niche signals |
| Script | ✅ | LLM (long-form narration) |
| Voice | ✅ | AI TTS (e.g. ElevenLabs-class) — the quality lever |
| Visuals (B-roll/images) | ✅/🟡 | stock footage + AI images + Ken-Burns; curation is light-touch |
| Edit / assemble | ✅ | templated FFmpeg / editor |
| Title · thumbnail · captions | ✅ | LLM + template (thumbnail = the other quality lever) |
| Publish + analytics loop | ✅ | platform API + feedback to weights |
| **Human 5–20%** | — | **fact-check (esp. history/health), voice/thumbnail QC** |

**Quality is not compromised** because the two things viewers judge — *voice* and *thumbnail/hook* — get the human's
small share of attention, while everything mechanical is automated. **Weak-fit** channels (compilations, gaming, cooking)
are excluded: they need reused/captured footage (copyright + quality risk) or original on-camera material.

## Shortlist — good fits for 80–95% automation ({len(shortlist)} of 30)
*Strong = ~92% automatable, clean original-script narration. Moderate = ~80–85%, extra human QC (accuracy/animation).*

{md_table(["Channel","Niche","$/mo","RPM","Fit","Auto%","Why"], sl_rows)}

**Excluded ({n_weak}):** compilation/celebrity/clip channels (reused-content + copyright risk), gaming, and cooking/reviews
(need captured footage) — automatable in parts, but not without compromising quality or rights.

## Recommendation
Model the **faceless documentary/explainer** lane — specifically the **Strong-fit, higher-RPM** examples
({", ".join(r["title"] for r in strong[:5])}). It is the niche with (a) the most fresh winners here, (b) RPM that clears
$5k/mo on ~1M views, and (c) a format that a faceless-AI pipeline can match or beat. Next step: pick ONE target and
reverse-engineer it (template `01`) — I can pull its sample videos + transcript (1 credit) to confirm the format before building.

## Appendix A — all 30 channels
{md_table(["#","Channel","Subs","$/mo","Mo views","RPM","Started","Category","Format","Outlier","Fit","Auto%"], appendix_rows)}

*Full machine-readable data: `result/channels_full.csv` · `result/data/channels.json`. Regenerate: `python result/generate_report.py`.*
"""
(ROOT / "report.md").write_text(report)

# ── Disposable HTML viewer ───────────────────────────────────────────────────
import markdown as md
body = md.markdown(report, extensions=["tables", "fenced_code", "toc"])
html = f"""<!doctype html><html><head><meta charset="utf-8"><title>NexLev Report (preview — deletable)</title>
<style>
body{{max-width:960px;margin:2rem auto;padding:0 1.2rem;font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;color:#1a1a1a}}
h1,h2,h3{{font-weight:650;line-height:1.25}} h1{{border-bottom:2px solid #eee;padding-bottom:.3rem}}
h2{{margin-top:2rem;border-bottom:1px solid #eee;padding-bottom:.2rem}}
img{{max-width:100%;height:auto;border:1px solid #eee;border-radius:8px;margin:.6rem 0}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:.6rem 0}}
th,td{{border:1px solid #ddd;padding:5px 8px;text-align:left}} th{{background:#f6f8fa}}
tr:nth-child(even){{background:#fbfbfb}} code{{background:#f3f3f3;padding:1px 4px;border-radius:4px}}
.banner{{background:#fff8e1;border:1px solid #ffe082;padding:.5rem .8rem;border-radius:8px;font-size:13px}}
</style></head><body>
<div class="banner">🗑️ <b>Disposable preview.</b> This <code>view.html</code> just renders <code>report.md</code> +
the PNG charts for easy viewing — safe to delete. The durable artifacts are <code>report.md</code>,
<code>charts/</code>, and <code>channels_full.csv</code>.</div>
{body}
</body></html>"""
(ROOT / "view.html").write_text(html)

print("OK — wrote:")
for p in ["report.md", "view.html", "channels_full.csv", "data/channels.json"]:
    print("  result/" + p)
print(f"  result/charts/  ({len(list(CHARTS.glob('*.png')))} PNGs)")
print(f"\nfit: {n_strong} Strong · {n_mod} Moderate · {n_weak} Weak | shortlist={len(shortlist)}")
