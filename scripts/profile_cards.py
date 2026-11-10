"""Generate self-contained profile cards from public GitHub data."""
import json
import os
from collections import Counter
from html import escape
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree

OWNER = os.environ["PROFILE_OWNER"]
TOKEN = os.environ["GH_TOKEN"]
API = "https://api.github.com"


def get(path):
    request = Request(API + path, headers={
        "Authorization": "Bearer " + TOKEN,
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-cards-workflow",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def repos():
    result = []
    page = 1
    while True:
        batch = get(f"/users/{quote(OWNER)}/repos?type=owner&per_page=100&page={page}")
        result.extend(repo for repo in batch if not repo["private"])
        if len(batch) < 100:
            return result
        page += 1


def text(x, y, value, color, size=14, weight=400):
    return (f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
            f'font-weight="{weight}">{escape(str(value))}</text>')


def card(title, content, theme):
    bg, fg, muted, border, accent = theme
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="420" height="204" '
            f'viewBox="0 0 420 204" role="img" aria-label="{escape(title, quote=True)}">'
            f'<title>{escape(title)}</title>'
            f'<rect x="0.5" y="0.5" width="419" height="203" rx="12" fill="{bg}" stroke="{border}"/>'
            '<g font-family="Arial, Helvetica, sans-serif">'
            + text(20, 29, title, accent, 18, 700)
            + content + '</g></svg>\n')


def stats_card(profile, repositories, theme):
    bg, fg, muted, border, accent = theme
    stats = [
        ("Public repositories", len(repositories)),
        ("Stars received", sum(r["stargazers_count"] for r in repositories)),
        ("Forks received", sum(r["forks_count"] for r in repositories)),
        ("Followers", profile["followers"]),
    ]
    body = ""
    for i, (name, value) in enumerate(stats):
        y = 60 + i * 31
        body += text(20, y, name, fg, 14, 500)
        body += f'<text x="400" y="{y}" fill="{fg}" font-size="15" font-weight="700" text-anchor="end">{value:,}</text>'
    body += text(20, 190, "Public repositories • GitHub API", muted, 11)
    return card("GitHub Stats", body, theme)


COLORS = ["#2f81f7", "#f1e05a", "#3572a5", "#f34b7d", "#89e051", "#a371f7"]


def languages_card(languages, theme):
    bg, fg, muted, border, accent = theme
    total = sum(languages.values())
    body = ""
    if total:
        top = languages.most_common(5)
        rest = total - sum(n for _, n in top)
        if rest:
            top.append(("Other", rest))
        x = 20
        for i, (name, n) in enumerate(top):
            width = 380 * n / total
            body += f'<rect x="{x:.3f}" y="45" width="{width:.3f}" height="10" fill="{COLORS[i]}"/>'
            x += width
            col, row = i % 2, i // 2
            lx, ly = 20 + col * 195, 81 + row * 33
            body += f'<circle cx="{lx+5}" cy="{ly-4}" r="5" fill="{COLORS[i]}"/>'
            body += text(lx+16, ly, f"{name} {100*n/total:.1f}%", fg, 12, 500)
    else:
        body += text(20, 80, "No language data available", muted)
    body += text(20, 190, "Code bytes in public, non-fork repositories", muted, 11)
    return card("Top Languages", body, theme)


def main():
    profile = get(f"/users/{quote(OWNER)}")
    repositories = repos()
    languages = Counter()
    for repo in repositories:
        if not repo["fork"]:
            languages.update(get(f"/repos/{repo['full_name']}/languages"))
    themes = {
        "light": ("#ffffff", "#24292f", "#57606a", "#d0d7de", "#0969da"),
        "dark": ("#0d1117", "#e6edf3", "#8b949e", "#30363d", "#58a6ff"),
    }
    out = Path("assets")
    out.mkdir(exist_ok=True)
    for name, theme in themes.items():
        for prefix, svg in [
            ("profile-stats", stats_card(profile, repositories, theme)),
            ("top-languages", languages_card(languages, theme)),
        ]:
            ElementTree.fromstring(svg)
            (out / f"{prefix}-{name}.svg").write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()
