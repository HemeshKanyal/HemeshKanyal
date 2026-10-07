#!/usr/bin/env python3
"""Draws every SVG on the profile from the GitHub GraphQL API.

Standard library only, so nothing can break in CI. Run by
.github/workflows/refresh.yml once a day; it rewrites a file only when its
contents change, so quiet days produce no commit.

    GITHUB_TOKEN=... GH_LOGIN=HemeshKanyal python3 scripts/generate.py
"""
import base64
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.request
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
FONTS = OUT / "fonts"
LOGIN = os.environ.get("GH_LOGIN", "HemeshKanyal")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

W = 620  # every graphic shares one width so the page lines up
PAD = 4  # just enough room for the pending block's halo

# Notebooks are mostly embedded output, so their byte counts drown out
# every real language. They still count toward "by repos".
SKIP_LANG_BYTES = {"Jupyter Notebook"}

# ---------------------------------------------------------------- data


def gql(query, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": LOGIN,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if body.get("errors"):
        sys.exit(f"graphql error: {body['errors']}")
    return body["data"]


Q_PROFILE = """
query($login: String!) {
  user(login: $login) {
    createdAt
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
      nodes { languages(first: 20) { edges { size node { name } } } }
    }
  }
}"""

Q_DAYS = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""


def fetch(today):
    profile = gql(Q_PROFILE, login=LOGIN)["user"]
    created = dt.date.fromisoformat(profile["createdAt"][:10])

    # The API caps a window at one year. Windows are pinned to whole UTC days:
    # left to itself "the past year" is measured from the request time, and
    # two runs minutes apart would bucket days differently.
    days = {}
    start = created
    while start <= today:
        end = min(start + dt.timedelta(days=364), today)
        cal = gql(
            Q_DAYS,
            login=LOGIN,
            **{"from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"},
        )["user"]["contributionsCollection"]["contributionCalendar"]
        for week in cal["weeks"]:
            for d in week["contributionDays"]:
                day = dt.date.fromisoformat(d["date"])
                if start <= day <= end:
                    days[day] = d["contributionCount"]
        start = end + dt.timedelta(days=1)

    by_bytes, by_repos = {}, {}
    for repo in profile["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name not in SKIP_LANG_BYTES:
                by_bytes[name] = by_bytes.get(name, 0) + edge["size"]
            by_repos[name] = by_repos.get(name, 0) + 1

    return created, days, by_bytes, by_repos


# ---------------------------------------------------------------- drawing


def font_face(weight, filename):
    data = base64.b64encode((FONTS / filename).read_bytes()).decode()
    return (
        f"@font-face{{font-family:'JBM';font-weight:{weight};"
        f"src:url(data:font/woff2;base64,{data}) format('woff2')}}"
    )


STYLE = (
    font_face(400, "JetBrainsMono-Regular.subset.woff2")
    + font_face(700, "JetBrainsMono-Bold.subset.woff2")
    + "text{font-family:'JBM',ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre}"
    + ".b{font-weight:700}"
    # light
    + ".fg{fill:#1f2328}.mu{fill:#59636e}.ac{fill:#9a6700}.bg{fill:#ffffff}"
    + ".s-fa{stroke:#d1d9e0}.s-mu{stroke:#818b98}.s-ac{stroke:#9a6700}"
    # dark: the SVG follows the viewer's system theme
    + "@media (prefers-color-scheme:dark){"
    + ".fg{fill:#e6edf3}.mu{fill:#9198a1}.ac{fill:#e3b341}.bg{fill:#0d1117}"
    + ".s-fa{stroke:#3d444d}.s-mu{stroke:#656c76}.s-ac{stroke:#e3b341}}"
)


def svg(height, body, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
        f'viewBox="0 0 {W} {height}" role="img" aria-label="{escape(title)}">'
        f"<title>{escape(title)}</title><style>{STYLE}</style>{body}</svg>\n"
    )


def text(x, y, s, cls, size, anchor="start", extra=""):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return f'<text x="{x:g}" y="{y:g}" font-size="{size}" class="{cls}"{a}{extra}>{escape(s)}</text>'


def appear(at):
    """Hidden until `at` seconds, then shown for good. Nothing loops."""
    return f'<set attributeName="opacity" to="1" begin="{at:.2f}s" fill="freeze"/>'


def fmt_day(d, year=False):
    s = f"{d:%b} {d.day}".lower()
    return f"{s}, {d.year}" if year else s


# -- header: a terminal that types itself


def draw_header():
    size, cw = 14, 14 * 0.6
    x0, step = PAD, 0.055
    lines = [
        ("cmd", "whoami"),
        ("name", "hemesh kanyal"),
        ("out", "blockchain & full-stack developer · india"),
        ("cmd", "ls ~/building"),
        ("acc", "trustchain  bharatrwa  risklens  ascent"),
        ("prompt", ""),
    ]
    ys = {"cmd": 26, "name": 30, "out": 22, "acc": 26, "prompt": 30}
    body, defs = [], []
    y, t = 0, 0.4
    for i, (kind, s) in enumerate(lines):
        y += ys[kind] if kind != "cmd" or i == 0 else 34
        if kind in ("cmd", "prompt"):
            body.append(f'<g opacity="0">{appear(t)}{text(x0, y, "$", "ac b", size)}</g>')
            tx = x0 + 2 * cw
            if kind == "prompt":
                body.append(
                    f'<rect x="{tx:g}" y="{y - 12}" width="{cw:g}" height="15" class="fg" opacity="0">'
                    f'<animate attributeName="opacity" values="1;0;1" keyTimes="0;0.5;1" calcMode="discrete" '
                    f'dur="1.1s" begin="{t:.2f}s" repeatCount="5" fill="freeze"/></rect>'
                )
                break
            # type character by character: a clip rect that grows one cell at a time
            n = len(s)
            widths = ";".join(f"{k * cw:g}" for k in range(n + 1))
            dur = n * step
            defs.append(
                f'<clipPath id="c{i}"><rect x="{tx:g}" y="{y - 16}" height="22" width="0">'
                f'<animate attributeName="width" values="{widths}" calcMode="discrete" '
                f'dur="{dur:.2f}s" begin="{t:.2f}s" fill="freeze"/></rect></clipPath>'
            )
            body.append(f'<g clip-path="url(#c{i})">{text(tx, y, s, "fg", size)}</g>')
            xs = ";".join(f"{tx + k * cw:g}" for k in range(n + 1))
            body.append(
                f'<rect y="{y - 12}" width="{cw:g}" height="15" class="fg" opacity="0" x="{tx:g}">'
                f'<set attributeName="opacity" to="1" begin="{t:.2f}s" dur="{dur + 0.15:.2f}s"/>'
                f'<animate attributeName="x" values="{xs}" calcMode="discrete" dur="{dur:.2f}s" '
                f'begin="{t:.2f}s" fill="freeze"/></rect>'
            )
            t += dur + 0.3
        else:
            cls, sz = {"name": ("fg b", 28), "out": ("mu", 14), "acc": ("ac", 14)}[kind]
            body.append(f'<g opacity="0">{appear(t)}{text(x0, y, s, cls, sz)}</g>')
            t += 0.12
    height = y + 16
    return svg(height, f"<defs>{''.join(defs)}</defs>{''.join(body)}", "Hemesh Kanyal: blockchain and full-stack developer, India")


# -- chain: the last 52 weeks as a chain of blocks


def week_start(d):
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)  # weeks begin on Sunday


def draw_chain(created, days, today):
    tip = week_start(today)
    weeks = [tip - dt.timedelta(weeks=51 - i) for i in range(52)]
    counts = [sum(days.get(w + dt.timedelta(days=k), 0) for k in range(7)) for w in weeks]
    height_no = (tip - week_start(created)).days // 7 + 1

    nonzero = sorted(c for c in counts if c)
    cuts = [nonzero[int(len(nonzero) * q)] for q in (0.25, 0.5, 0.75)] if nonzero else []

    def level(c):
        return 0 if not c else 1 + sum(c > cut for cut in cuts)

    cols, bw, bh, row_pitch = 13, 36, 26, 40
    gap = (W - 2 * PAD - cols * bw) / (cols - 1)
    top = 44

    def cell(i):
        r, c = divmod(i, cols)
        if r % 2:
            c = cols - 1 - c  # snake: odd rows run right to left
        return PAD + c * (bw + gap), top + r * row_pitch

    body = []
    total = sum(counts)
    body.append(text(PAD, 20, f"{len(weeks)} blocks · {total:,} txs", "fg b", 13))
    body.append(text(W - PAD, 20, f"height #{height_no} · since {fmt_day(weeks[0], True)}", "mu", 12, "end"))

    opac = [0, 0.22, 0.45, 0.7, 1]
    for i, (w, c) in enumerate(zip(weeks, counts)):
        at = 0.2 + i * 0.035
        x, y = cell(i)
        parts = []
        if i:  # link back to the previous block
            px, py = cell(i - 1)
            if py == y:
                x1, x2 = sorted((px, x))
                parts.append(f'<line x1="{x1 + bw:g}" y1="{y + bh / 2:g}" x2="{x2:g}" y2="{y + bh / 2:g}" class="s-mu" stroke-width="1"/>')
            else:
                cx = x + bw / 2
                parts.append(f'<line x1="{cx:g}" y1="{py + bh:g}" x2="{cx:g}" y2="{y:g}" class="s-mu" stroke-width="1"/>')
        lv = level(c)
        pending = i == len(weeks) - 1
        if lv:
            parts.append(f'<rect x="{x:g}" y="{y}" width="{bw}" height="{bh}" rx="3" class="ac" fill-opacity="{opac[lv]}"/>')
        if not lv:
            parts.append(
                f'<rect x="{x + 0.5:g}" y="{y + 0.5}" width="{bw - 1}" height="{bh - 1}" rx="3" '
                f'fill="none" class="s-fa" stroke-width="1"/>'
            )
        if pending:  # a dashed halo that keeps breathing until the week closes
            parts.append(
                f'<rect x="{x - 3.5:g}" y="{y - 3.5}" width="{bw + 7}" height="{bh + 7}" rx="5" fill="none" '
                f'class="s-ac" stroke-width="1" stroke-dasharray="3 2">'
                f'<animate attributeName="stroke-opacity" values="1;0.2;1" dur="1.8s" repeatCount="indefinite"/></rect>'
            )
        label_cls = "bg b" if lv >= 3 else ("fg b" if lv else "mu")
        parts.append(text(x + bw / 2, y + bh / 2 + 4, str(c), label_cls, 11, "middle"))
        body.append(f'<g opacity="0">{appear(at)}{"".join(parts)}</g>')

    last_x, last_y = cell(len(weeks) - 1)
    foot = last_y + bh + 22
    body.append(text(PAD, foot, "↑ this week, still being mined", "ac", 11))
    body.append(text(W - PAD, foot, "1 block = 1 week · 1 tx = 1 contribution", "mu", 11, "end"))
    return svg(foot + 10, "".join(body), f"The last 52 weeks as a chain of blocks: {total:,} contributions")


# -- streaks


def streaks(days, today):
    current_end = today if days.get(today) else today - dt.timedelta(days=1)
    d, cur_len = current_end, 0
    while days.get(d):
        cur_len += 1
        d -= dt.timedelta(days=1)
    current = (cur_len, d + dt.timedelta(days=1), current_end)

    best, run, run_start = (0, None, None), 0, None
    for day in sorted(days):
        if days[day]:
            run_start = day if run == 0 else run_start
            run += 1
            if run > best[0]:
                best = (run, run_start, day)
        else:
            run = 0
    busiest = max(sorted(days), key=lambda k: days[k]) if days else today
    return current, best, (days.get(busiest, 0), busiest)


def draw_streak(days, today):
    (cl, cs, ce), (bl, bs, be), (top, top_day) = streaks(days, today)

    def span(n, a, b):
        if not n:
            return "nothing yet"
        return fmt_day(a) if a == b else f"{fmt_day(a)} → {fmt_day(b)}"

    cards = [
        ("current streak", f"{cl}", "day" if cl == 1 else "days", span(cl, cs, ce)),
        ("longest streak", f"{bl}", "day" if bl == 1 else "days", span(bl, bs, be) + (f" {be.year}" if bl else "")),
        ("busiest day", f"{top}", "tx" if top == 1 else "txs", fmt_day(top_day, True)),
    ]
    col = (W - 2 * PAD) / 3
    body = []
    for i, (label, num, unit, sub) in enumerate(cards):
        x = PAD + i * col
        num_w = len(num) * 30 * 0.6
        g = (
            text(x, 18, label, "mu", 12)
            + text(x, 56, num, "fg b", 30)
            + text(x + num_w + 6, 56, unit, "mu", 13)
            + text(x, 80, sub, "ac", 12)
        )
        if i:
            g = f'<line x1="{x - 14:g}" y1="6" x2="{x - 14:g}" y2="84" class="s-fa" stroke-width="1"/>' + g
        body.append(f'<g opacity="0">{appear(0.2 + i * 0.15)}{g}</g>')
    return svg(92, "".join(body), f"Current streak {cl} days, longest streak {bl} days")


# -- languages


def draw_langs(by_bytes, by_repos, n=6):
    col = (W - 2 * PAD - 28) / 2
    name_w, pct_w = 118, 44
    bar_w = col - name_w - pct_w
    body = []

    def column(x0, title, data, fmt):
        out = [text(x0, 18, title, "mu", 12)]
        rows = sorted(data.items(), key=lambda kv: (-kv[1], kv[0]))[:n]
        total = sum(data.values()) or 1
        peak = rows[0][1] if rows else 1
        for i, (name, v) in enumerate(rows):
            y = 46 + i * 24
            w = max(2.0, bar_w * v / peak)
            at = 0.2 + i * 0.08
            out.append(text(x0, y, name.lower(), "fg", 12))
            out.append(f'<rect x="{x0 + name_w:g}" y="{y - 9}" width="{bar_w:g}" height="10" rx="2" fill="none" class="s-fa" stroke-width="1"/>')
            out.append(
                f'<rect x="{x0 + name_w:g}" y="{y - 9}" width="0" height="10" rx="2" class="ac">'
                f'<animate attributeName="width" from="0" to="{w:.1f}" dur="0.6s" begin="{at:.2f}s" fill="freeze"/></rect>'
            )
            out.append(text(x0 + col, y, fmt(v, total), "mu", 12, "end"))
        return out

    body += column(PAD, "by bytes", by_bytes, lambda v, t: f"{100 * v / t:.1f}%")
    body += column(PAD + col + 28, "by repos", by_repos, lambda v, t: str(v))
    return svg(46 + n * 24 - 6, "".join(body), "Top languages by bytes and by repository count")


# -- section headings


HEADINGS = ["about", "stack", "projects", "chain", "about this page"]


def draw_heading(i, name):
    x = PAD
    tag = f"0x{i:02x}"
    body = text(x, 26, tag, "ac", 13) + text(x + (len(tag) + 1) * 13 * 0.6, 26, name, "fg b", 15)
    line_x = x + (len(tag) + 1) * 13 * 0.6 + len(name) * 15 * 0.6 + 14
    body += f'<line x1="{line_x:g}" y1="21.5" x2="{W - PAD}" y2="21.5" class="s-fa" stroke-width="1"/>'
    return svg(36, body, name)


# ---------------------------------------------------------------- main


def write(name, content):
    path = OUT / name
    if path.exists() and path.read_text() == content:
        return False
    path.write_text(content)
    return True


def main():
    if not TOKEN:
        sys.exit("set GITHUB_TOKEN")
    today = dt.datetime.now(dt.timezone.utc).date()
    created, days, by_bytes, by_repos = fetch(today)

    files = {
        "header.svg": draw_header(),
        "chain.svg": draw_chain(created, days, today),
        "streak.svg": draw_streak(days, today),
        "langs.svg": draw_langs(by_bytes, by_repos),
    }
    for i, name in enumerate(HEADINGS, 1):
        files[f"hd-{name.replace(' ', '-')}.svg"] = draw_heading(i, name)

    changed = [name for name, content in files.items() if write(name, content)]
    print("changed:", ", ".join(changed) if changed else "nothing")


if __name__ == "__main__":
    main()
