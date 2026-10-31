"""Build the profile cards in assets/.

streak.svg: from github.com/users/<user>/contributions (same data as the profile
graph), since the GraphQL API drops some private-org contributions.
activity.svg, heatmap.svg: same grid data, with exact daily counts.
stats.svg, langs.svg: from the GraphQL API using $GITHUB_TOKEN.
"""
import json
import math
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import date

USER = "afnanahmad"
HIDE_LANGS = set()  # e.g. {"Jupyter Notebook", "CSS"}
BG, ACCENT, TEXT, STROKE = "#0C1714", "#BCF4CF", "#E5EBE7", "#24352F"
FONT = "text{font-family:'Segoe UI',Ubuntu,sans-serif}"
# Flame icon from DenverCoder1/github-readme-streak-stats (MIT)
FIRE = ("M1.5 0.67C1.5 0.67 2.24 3.32 2.24 5.47C2.24 7.53 0.89 9.2-1.17 9.2C-3.23 9.2-4.79 7.53-4.79 5.47L-4.76 5.11"
        "C-6.78 7.51-8 10.62-8 13.99C-8 18.41-4.42 22 0 22C4.42 22 8 18.41 8 13.99C8 8.6 5.41 3.79 1.5 0.67Z"
        "M-0.29 19C-2.07 19-3.51 17.6-3.51 15.86C-3.51 14.24-2.46 13.1-0.7 12.74C1.07 12.38 2.9 11.53 3.92 10.16"
        "C4.31 11.45 4.51 12.81 4.51 14.2C4.51 16.85 2.36 19-0.29 19Z")


def fetch_days(user):
    req = urllib.request.Request(f"https://github.com/users/{user}/contributions",
                                 headers={"User-Agent": "streak-card"})
    html = urllib.request.urlopen(req, timeout=30).read().decode()
    days = sorted((date.fromisoformat(d), int(lv)) for d, lv in
                  re.findall(r'data-date="([\d-]+)"[^>]*data-level="(\d)"', html))
    total = int(re.search(r"([\d,]+)\s+contributions?\s+in the last year", html)[1].replace(",", ""))
    ids = dict(re.findall(r'data-date="([\d-]+)" id="([^"]+)"', html))
    tips = dict(re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>(\d+|No) contributions?', html))
    counts = {date.fromisoformat(d): int(tips.get(i, "0").replace("No", "0")) for d, i in ids.items()}
    return days, total, counts


def streaks(days):
    """days: sorted [(date, level)]. Returns (current, longest) as (length, start, end)."""
    # ponytail: grid only covers the last ~12 months, so "longest" is longest in that window
    runs, start = [], None
    for i, (d, lv) in enumerate(days):
        if lv and start is None:
            start = i
        if not lv and start is not None:
            runs.append((start, i - 1)); start = None
    if start is not None:
        runs.append((start, len(days) - 1))
    as_tuple = lambda r: (r[1] - r[0] + 1, days[r[0]][0], days[r[1]][0]) if r else (0, None, None)
    longest = max(runs, key=lambda r: r[1] - r[0], default=None)
    # today still empty doesn't break the streak
    last = len(days) - 1 if days[-1][1] else len(days) - 2
    current = runs[-1] if runs and runs[-1][1] == last else None
    return as_tuple(current), as_tuple(longest)


def fmt(d):
    return d.strftime("%b %-d") if d else ""


def span(s):
    return f"{fmt(s[1])} – {fmt(s[2])}" if s[0] else "No streak"


def svg(total, cur, best):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195">
<style>{FONT}text{{text-anchor:middle}}.n{{font-size:28px;font-weight:700;fill:#F3F4E9}}.l{{font-size:14px;fill:{ACCENT}}}.d{{font-size:12px;fill:#A8BDB0}}</style>
<rect width="495" height="195" rx="12" fill="{BG}"/>
<line x1="165" y1="28" x2="165" y2="170" stroke="{STROKE}"/><line x1="330" y1="28" x2="330" y2="170" stroke="{STROKE}"/>
<text class="n" x="82.5" y="79">{total:,}</text><text class="l" x="82.5" y="115">Total Contributions</text><text class="d" x="82.5" y="140">Last 12 Months</text>
<mask id="m"><rect width="495" height="195" fill="white"/><ellipse cx="247.5" cy="32" rx="13" ry="18" fill="black"/></mask>
<circle cx="247.5" cy="71" r="40" fill="none" stroke="{ACCENT}" stroke-width="5" mask="url(#m)"/>
<path transform="translate(247.5 19.5)" fill="#FFB094" d="{FIRE}"/>
<text class="n" x="247.5" y="81">{cur[0]}</text><text class="l" x="247.5" y="140" style="font-weight:700">Current Streak</text><text class="d" x="247.5" y="160">{span(cur)}</text>
<text class="n" x="412.5" y="79">{best[0]}</text><text class="l" x="412.5" y="115">Longest Streak</text><text class="d" x="412.5" y="140">{span(best)}</text>
</svg>
"""


def graphql(query):
    req = urllib.request.Request("https://api.github.com/graphql", json.dumps({"query": query}).encode(),
                                 {"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    if "errors" in data:
        sys.exit(data["errors"])
    return data["data"]["user"]


def fetch_stats(user):
    # ponytail: first 100 owned repos only, paginate if that's ever exceeded
    return graphql(f"""{{user(login:"{user}"){{createdAt
      publicRepos:repositories(ownerAffiliations:OWNER,privacy:PUBLIC,isFork:false){{totalCount}}
      repositories(ownerAffiliations:OWNER,isFork:false,first:100){{totalCount nodes{{stargazerCount
        languages(first:10,orderBy:{{field:SIZE,direction:DESC}}){{edges{{size node{{name color}}}}}}}}}}
      pullRequests{{totalCount}} issues{{totalCount}}
      repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,REPOSITORY]){{totalCount}}}}}}""")


def top_langs(repos, n=6):
    sizes = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            if name not in HIDE_LANGS:
                size = sizes.get(name, (0,))[0]
                sizes[name] = (size + e["size"], e["node"]["color"] or "#8B949E")
    top = sorted(sizes.items(), key=lambda kv: -kv[1][0])[:n]
    total = sum(size for _, (size, _) in top) or 1
    return [(name, color, size / total * 100) for name, (size, color) in top]


def stats_svg(u):
    rows = [("Total Stars", sum(r["stargazerCount"] for r in u["repositories"]["nodes"])),
            ("Repositories", u["repositories"]["totalCount"]),
            ("Pull Requests", u["pullRequests"]["totalCount"]),
            ("Issues", u["issues"]["totalCount"]),
            ("Contributed To", u["repositoriesContributedTo"]["totalCount"])]
    body = "".join(f'<circle cx="34" cy="{y - 5}" r="4" fill="{ACCENT}"/>'
                   f'<text x="50" y="{y}" class="t">{label}:</text><text x="310" y="{y}" class="t b">{value:,}</text>'
                   for (label, value), y in zip(rows, range(75, 200, 25)))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="340" height="195" viewBox="0 0 340 195">
<style>{FONT}.h{{font-size:18px;font-weight:600;fill:{ACCENT}}}.t{{font-size:14px;fill:{TEXT}}}.b{{font-weight:700;text-anchor:end}}</style>
<rect width="340" height="195" rx="12" fill="{BG}"/>
<text x="25" y="38" class="h">GitHub Stats</text>{body}
</svg>
"""


def langs_svg(langs):
    # full-width strip: 835 = stats (340) + streak (495) side by side
    bar, x = "", 25.0
    for _, color, pct in langs:
        w = 785 * pct / 100
        bar += f'<rect x="{x:.1f}" y="55" width="{w:.1f}" height="8" fill="{color}"/>'
        x += w
    legend = "".join(f'<circle cx="{30 + (i % 3) * 265}" cy="{88 + (i // 3) * 25}" r="5" fill="{color}"/>'
                     f'<text x="{40 + (i % 3) * 265}" y="{92 + (i // 3) * 25}" class="t">{name} {pct:.1f}%</text>'
                     for i, (name, color, pct) in enumerate(langs))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="835" height="140" viewBox="0 0 835 140">
<style>{FONT}.h{{font-size:18px;font-weight:600;fill:{ACCENT}}}.t{{font-size:13px;fill:{TEXT}}}</style>
<rect width="835" height="140" rx="12" fill="{BG}"/>
<text x="25" y="38" class="h">Most Used Languages</text>
<clipPath id="c"><rect x="25" y="55" width="785" height="8" rx="4"/></clipPath><g clip-path="url(#c)">{bar}</g>{legend}
</svg>
"""


LEVELS = ["#16241F", "#1F4A3A", "#2F6F55", "#5FAE86", ACCENT]
WEEKDAYS = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"]


def patterns(counts):
    busiest = max(counts, key=counts.get)
    by_weekday = Counter()
    for d, c in counts.items():
        by_weekday[d.weekday()] += c
    active = sum(1 for c in counts.values() if c)
    return [(f"{counts[busiest]:,}", f"Busiest day · {fmt(busiest)}"),
            (WEEKDAYS[by_weekday.most_common(1)[0][0]], "Most active weekday"),
            (f"{active}/{len(counts)}", "Active days"),
            (f"{sum(counts.values()) / len(counts):.1f}", "Average per day")]


def smooth(pts):
    """Catmull-Rom through pts as an SVG cubic path."""
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1, p2 = pts[max(i - 1, 0)], pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d


def activity_svg(counts, u):
    """Weekly area chart with a stats strip, over the last 365 days."""
    # the grid shows 53 whole weeks (up to 371 days); trim to a calendar year
    counts = dict(sorted(counts.items())[-365:])
    days = sorted(counts)
    # whole weeks ending today, so the line doesn't dip on a half-finished week
    starts = range(len(days) % 7, len(days), 7)
    weeks = [sum(counts[d] for d in days[i:i + 7]) for i in starts]
    # round the axis max up to a half-step of its magnitude, e.g. 412 -> 450
    mag = 10 ** (len(str(max(weeks) or 1)) - 1)
    top = math.ceil(max(weeks) / mag * 2) / 2 * mag or 1
    x_of = lambda i: 60 + 750 * i / (len(weeks) - 1)
    pts = [(x_of(i), 205 - 85 * w / top) for i, w in enumerate(weeks)]
    line = smooth(pts)
    dash = ' stroke-dasharray="3 4"'
    grid = "".join(f'<line x1="60" y1="{205 - 85 * f}" x2="810" y2="{205 - 85 * f}" stroke="{STROKE}"{dash if f else ""}/>'
                   f'<text x="50" y="{209 - 85 * f}" class="m" text-anchor="end">{top * f:g}</text>'
                   for f in (0, 0.5, 1))
    ticks = "".join(f'<text x="{x_of(i):.1f}" y="225" class="m">{days[s].strftime("%b")}</text>'
                    for i, s in enumerate(starts) if days[s].day <= 7)
    joined = date.fromisoformat(u["createdAt"][:10])
    years = (date.today() - joined).days // 365
    profile = f'{u["publicRepos"]["totalCount"]} public repos · {years} years on GitHub (since {joined.year})'
    strip = "".join(f'<text x="{25 + i * 200}" y="80" class="v">{v}</text><text x="{25 + i * 200}" y="99" class="k">{k}</text>'
                    for i, (v, k) in enumerate(patterns(counts)))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="835" height="240" viewBox="0 0 835 240">
<style>{FONT}.h{{font-size:18px;font-weight:600;fill:{ACCENT}}}.v{{font-size:20px;font-weight:700;fill:#F3F4E9}}.k{{font-size:12px;fill:#A8BDB0}}.m{{font-size:11px;fill:#A8BDB0}}</style>
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity=".45"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient></defs>
<rect width="835" height="240" rx="12" fill="{BG}"/>
<text x="25" y="38" class="h">Contribution Activity</text><text x="810" y="38" class="k" text-anchor="end">{profile}</text>
<line x1="25" y1="52" x2="810" y2="52" stroke="{STROKE}"/>{strip}
{grid}
<path d="{line}L{pts[-1][0]:.1f},205L{pts[0][0]:.1f},205Z" fill="url(#g)"/>
<path d="{line}" fill="none" stroke="{ACCENT}" stroke-width="2"/>{ticks}
</svg>
"""


def heatmap_svg(days):
    """Option: GitHub-style grid in theme colors."""
    first = days[0][0]
    offset = (first.weekday() + 1) % 7  # grid weeks start on Sunday
    cells, months = "", ""
    for i, (d, lv) in enumerate(days):
        col, row = (i + offset) // 7, (i + offset) % 7
        cells += f'<rect x="{25 + col * 14.5}" y="{60 + row * 15}" width="11.5" height="12" rx="2" fill="{LEVELS[lv]}"/>'
        if d.day == 1:
            months += f'<text x="{25 + col * 14.5}" y="52" class="m">{d.strftime("%b")}</text>'
    legend = "".join(f'<rect x="{705 + i * 15}" y="173" width="12" height="12" rx="2" fill="{c}"/>' for i, c in enumerate(LEVELS))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="835" height="200" viewBox="0 0 835 200">
<style>{FONT}.h{{font-size:18px;font-weight:600;fill:{ACCENT}}}.m{{font-size:11px;fill:#A8BDB0}}</style>
<rect width="835" height="200" rx="12" fill="{BG}"/>
<text x="25" y="30" class="h">Contribution Graph</text>{months}{cells}
<text x="697" y="183" class="m" text-anchor="end">Less</text>{legend}<text x="786" y="183" class="m">More</text>
</svg>
"""


def check():
    d = lambda n: date(2026, 10, n)
    assert streaks([(d(1), 1), (d(2), 0), (d(3), 1), (d(4), 2), (d(5), 0)]) == ((2, d(3), d(4)), (2, d(3), d(4)))
    assert streaks([(d(1), 1), (d(2), 1), (d(3), 1), (d(4), 0), (d(5), 1)])[0] == (1, d(5), d(5))
    assert streaks([(d(1), 1), (d(2), 0), (d(3), 0)])[0] == (0, None, None)
    lang = lambda name, size: {"size": size, "node": {"name": name, "color": "#000"}}
    langs = top_langs([{"languages": {"edges": [lang("Swift", 300), lang("CSS", 100)]}},
                       {"languages": {"edges": [lang("Swift", 100)]}}])
    assert [(n, round(p)) for n, _, p in langs] == [("Swift", 80), ("CSS", 20)]
    p = patterns({d(5): 3, d(6): 0, d(12): 5, d(13): 1})  # Oct 5 and 12 are Mondays
    assert p[0][0] == "5" and p[1][0] == "Mondays" and p[2][0] == "3/4" and p[3][0] == "2.2"
    print("ok")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        days, total, counts = fetch_days(USER)
        cur, best = streaks(days)
        open("assets/streak.svg", "w").write(svg(total, cur, best))
        print(f"total={total} current={cur} longest={best}")
        open("assets/heatmap.svg", "w").write(heatmap_svg(days))
        u = fetch_stats(USER)
        open("assets/stats.svg", "w").write(stats_svg(u))
        open("assets/langs.svg", "w").write(langs_svg(top_langs(u["repositories"]["nodes"])))
        open("assets/activity.svg", "w").write(activity_svg(counts, u))
