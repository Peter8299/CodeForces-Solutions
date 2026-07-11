#!/usr/bin/env python3
"""
Pulls solved problems + submission activity for a Codeforces handle and:
  1. Regenerates the "Problems Solved" table in README.md
  2. Regenerates a GitHub-style activity heatmap SVG (assets/heatmap.svg)

Designed to run on a schedule via GitHub Actions (see .github/workflows/update-readme.yml).
No external Python packages required — uses only the standard library.
"""

import json
import os
import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from collections import defaultdict

HANDLE = os.environ.get("CF_HANDLE", "Peter8299")
README_PATH = "README.md"
HEATMAP_PATH = "assets/heatmap.svg"

TABLE_START = "<!-- PROBLEMS-TABLE:START -->"
TABLE_END = "<!-- PROBLEMS-TABLE:END -->"


def fetch_submissions(handle):
    url = f"https://codeforces.com/api/user.status?handle={urllib.parse.quote(handle)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    if data.get("status") != "OK":
        print(f"CF API error: {data.get('comment')}", file=sys.stderr)
        sys.exit(1)
    return data["result"]


def build_solved_table(submissions):
    """Dedup by problem, keep earliest AC, sort newest-first by submission id."""
    solved = {}
    for sub in submissions:
        if sub.get("verdict") != "OK":
            continue
        p = sub["problem"]
        contest_id = p.get("contestId")
        index = p.get("index")
        if contest_id is None or index is None:
            continue
        key = f"{contest_id}{index}"
        if key not in solved or sub["id"] > solved[key]["id"]:
            solved[key] = {
                "id": sub["id"],
                "contestId": contest_id,
                "index": index,
                "name": p.get("name", key),
            }

    # Sort by submission id descending (most recently solved first)
    ordered = sorted(solved.values(), key=lambda x: x["id"], reverse=True)

    rows = [
        "| # | Problem | Solution |",
        "|---|---------|----------|",
    ]
    for i, prob in enumerate(ordered, 1):
        code = f"{prob['contestId']}{prob['index']}"
        name = prob["name"]
        folder = f"{code} - {name}".replace(" ", "%20")
        problem_url = f"https://codeforces.com/problemset/problem/{prob['contestId']}/{prob['index']}"
        rows.append(
            f"| {i} | [{code} - {name}]({problem_url}) | [Link](./{folder}/) |"
        )
    return "\n".join(rows), len(ordered)


def update_readme_table(table_md):
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if TABLE_START not in content or TABLE_END not in content:
        print("Table markers not found in README.md — skipping table update.", file=sys.stderr)
        return

    pattern = re.compile(
        re.escape(TABLE_START) + r".*?" + re.escape(TABLE_END), re.DOTALL
    )
    replacement = f"{TABLE_START}\n{table_md}\n{TABLE_END}"
    new_content = pattern.sub(replacement, content)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)


def build_heatmap_svg(submissions, weeks=53):
    """Generate a GitHub-style contribution heatmap SVG from submission timestamps."""
    day_counts = defaultdict(int)
    for sub in submissions:
        if sub.get("verdict") != "OK":
            continue
        ts = sub.get("creationTimeSeconds")
        if not ts:
            continue
        day = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        day_counts[day] += 1

    today = datetime.now(timezone.utc).date()
    # Align end date to the upcoming Saturday so the grid is clean, start = weeks*7 days back
    end = today
    start = end - timedelta(days=weeks * 7 - 1)
    # Shift start back to the previous Sunday for column alignment
    start -= timedelta(days=(start.weekday() + 1) % 7)

    cell = 11
    gap = 3
    step = cell + gap
    left_pad = 20
    top_pad = 20

    max_count = max(day_counts.values(), default=1)

    def color_for(count):
        if count == 0:
            return "#161b22"
        ratio = count / max_count
        if ratio > 0.75:
            return "#39d353"
        if ratio > 0.5:
            return "#26a641"
        if ratio > 0.25:
            return "#006d32"
        return "#0e4429"

    total_days = (end - start).days + 1
    num_weeks = (total_days // 7) + 1
    width = left_pad + num_weeks * step + 20
    height = top_pad + 7 * step + 30

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Segoe UI, Helvetica, Arial, sans-serif">',
        f'<rect width="100%" height="100%" fill="#0d1117"/>',
        f'<text x="{left_pad}" y="14" fill="#c9d1d9" font-size="12">'
        f'Codeforces activity — last {weeks} weeks (handle: {HANDLE})</text>',
    ]

    month_labels_drawn = set()
    d = start
    week_idx = 0
    while d <= end:
        month_key = (d.year, d.month)
        if d.weekday() == 6 and month_key not in month_labels_drawn and d.day <= 7:
            month_labels_drawn.add(month_key)
            svg_parts.append(
                f'<text x="{left_pad + week_idx * step}" y="{top_pad - 6}" '
                f'fill="#8b949e" font-size="10">{d.strftime("%b")}</text>'
            )
        for wd in range(7):
            cur = d + timedelta(days=wd)
            if cur > end:
                break
            count = day_counts.get(cur, 0)
            x = left_pad + week_idx * step
            y = top_pad + wd * step
            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" ry="2" '
                f'fill="{color_for(count)}"><title>{cur.isoformat()}: {count} solved</title></rect>'
            )
        d += timedelta(days=7)
        week_idx += 1

    legend_y = top_pad + 7 * step + 14
    svg_parts.append(f'<text x="{left_pad}" y="{legend_y}" fill="#8b949e" font-size="10">Less</text>')
    legend_colors = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
    lx = left_pad + 32
    for c in legend_colors:
        svg_parts.append(
            f'<rect x="{lx}" y="{legend_y - 9}" width="{cell}" height="{cell}" rx="2" ry="2" fill="{c}"/>'
        )
        lx += step
    svg_parts.append(f'<text x="{lx + 4}" y="{legend_y}" fill="#8b949e" font-size="10">More</text>')

    svg_parts.append("</svg>")

    os.makedirs(os.path.dirname(HEATMAP_PATH), exist_ok=True)
    with open(HEATMAP_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_parts))


def main():
    submissions = fetch_submissions(HANDLE)
    table_md, total = build_solved_table(submissions)
    update_readme_table(table_md)
    build_heatmap_svg(submissions)
    print(f"Updated README table ({total} problems) and heatmap for handle '{HANDLE}'.")


if __name__ == "__main__":
    main()
