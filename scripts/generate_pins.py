#!/usr/bin/env python3
"""Bake GitHub pin SVGs from pins.json into pins/ + README.md.

  python3 scripts/generate_pins.py
  GITHUB_TOKEN=…  # optional, higher rate limit
"""

from __future__ import annotations

import json
import os
import re
import textwrap
import urllib.error
import urllib.request
from html import escape
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "pins.json"
PINS = ROOT / "pins"
README = ROOT / "README.md"

MARK_START = "<!-- pins:start -->"
MARK_END = "<!-- pins:end -->"

FONT = "-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif"
CARD = (400, 120)
DESC_WIDTH, DESC_LINES = 52, 2

LANG_COLOR = {
    "C": "#555555",
    "C++": "#f34b7d",
    "CSS": "#563d7c",
    "Go": "#00ADD8",
    "HTML": "#e34c26",
    "Java": "#b07219",
    "JavaScript": "#f1e05a",
    "Python": "#3572A5",
    "Rust": "#dea584",
    "Shell": "#89e051",
    "TypeScript": "#3178c6",
    "Yacc": "#4B6C4B",
}

THEME = {
    "light": dict(bg="#ffffff", border="#d0d7de", title="#0969da", text="#656d76", icon="#656d76"),
    "dark": dict(bg="#0d1117", border="#30363d", title="#2f81f7", text="#8b949e", icon="#8b949e"),
}

REPO_ICON = (
    "M4 2a2 2 0 0 0-2 2v12.5a.5.5 0 0 0 .8.4L6 14l3.2 2.9a.5.5 0 0 0 .8-.4V4a2 2 0 0 0-2-2H4zm0 "
    "1h4a1 1 0 0 1 1 1v10.1l-2.4-2.2a.75.75 0 0 0-1.1 0L3 14.1V4a1 1 0 0 1 1-1z"
)
STAR_ICON = (
    "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 "
    "2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 "
    "6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25z"
)


def die(msg: str) -> NoReturn:
    raise SystemExit(msg)


def load_config() -> tuple[str, list[str]]:
    cfg = json.loads(CONFIG.read_text())
    user, repos = cfg.get("username"), cfg.get("repos")
    if not isinstance(user, str) or not user:
        die("pins.json: missing username")
    if not isinstance(repos, list) or not repos:
        die("pins.json: repos must be a non-empty list")
    return user, repos


def fetch_repo(user: str, repo: str, token: str | None) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{user}/{repo}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "alyshmahell-pins",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        die(f"{user}/{repo}: {e.code} {e.read().decode(errors='replace')}")


def wrap_desc(text: str | None) -> list[str]:
    if not text:
        return []
    cleaned = " ".join(text.split())
    lines = textwrap.wrap(cleaned, width=DESC_WIDTH)
    if len(lines) <= DESC_LINES:
        return lines
    last = lines[DESC_LINES - 1].rstrip(".,;: ")
    if len(last) > DESC_WIDTH - 1:
        last = last[: DESC_WIDTH - 1].rstrip()
    return lines[: DESC_LINES - 1] + [last + "…"]


def text(x: float, y: float, body: str, *, size: int, fill: str, weight: str | None = None) -> str:
    w = f' font-weight="{weight}"' if weight else ""
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}"{w} fill="{fill}">'
        f"{escape(body)}</text>"
    )


def path(d: str, fill: str) -> str:
    return f'<path fill="{fill}" fill-rule="evenodd" d="{d}"/>'


def svg_card(repo: dict, theme_name: str) -> str:
    t = THEME[theme_name]
    w, h = CARD
    name = repo["name"]
    lang = repo.get("language") or ""
    stars = int(repo.get("stargazers_count") or 0)
    lang_c = LANG_COLOR.get(lang, "#858585")

    parts = [
        f'<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{escape(name)}">',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="6" '
        f'fill="{t["bg"]}" stroke="{t["border"]}"/>',
        f'<g transform="translate(20,18) scale(1.1)">{path(REPO_ICON, t["icon"])}</g>',
        text(42, 32, name, size=14, fill=t["title"], weight="600"),
    ]

    y = 52
    for line in wrap_desc(repo.get("description")):
        parts.append(text(20, y, line, size=12, fill=t["text"]))
        y += 16

    meta_y, x = 100, 20
    if lang:
        parts.append(f'<circle cx="{x + 5}" cy="{meta_y - 3}" r="5" fill="{lang_c}"/>')
        parts.append(text(x + 16, meta_y, lang, size=12, fill=t["icon"]))
        x += 16 + len(lang) * 7 + 20
    parts.append(f'<g transform="translate({x},{meta_y - 11}) scale(0.85)">{path(STAR_ICON, t["icon"])}</g>')
    parts.append(text(x + 16, meta_y, str(stars), size=12, fill=t["icon"]))
    parts.append("</svg>\n")
    return "\n".join(parts)


def slug(name: str) -> str:
    return re.sub(r"[^\w.-]+", "_", name)


def write_svgs(repos: list[dict]) -> None:
    PINS.mkdir(parents=True, exist_ok=True)
    for old in (*PINS.glob("*-light.svg"), *PINS.glob("*-dark.svg")):
        old.unlink()
    for repo in repos:
        base = slug(repo["name"])
        for theme in THEME:
            (PINS / f"{base}-{theme}.svg").write_text(svg_card(repo, theme))


def readme_cell(user: str, repo: dict) -> str:
    name = repo["name"]
    base = slug(name)
    return "\n".join(
        [
            "<td>",
            f'  <a href="https://github.com/{user}/{name}">',
            f'    <img src="pins/{base}-light.svg#gh-light-mode-only" alt="{escape(name)}" width="400" height="120" />',
            f'    <img src="pins/{base}-dark.svg#gh-dark-mode-only" alt="{escape(name)}" width="400" height="120" />',
            "  </a>",
            "</td>",
        ]
    )


def readme_section(user: str, repos: list[dict]) -> str:
    rows = []
    for i in range(0, len(repos), 2):
        pair = repos[i : i + 2]
        cells = "\n".join(readme_cell(user, r) for r in pair)
        if len(pair) == 1:
            cells += "\n<td></td>"
        rows.append(f"<tr>\n{cells}\n</tr>")
    table = "<table>\n" + "\n".join(rows) + "\n</table>"
    return f"{MARK_START}\n{table}\n{MARK_END}\n"


def update_readme(user: str, repos: list[dict]) -> None:
    section = readme_section(user, repos)
    text = README.read_text() if README.exists() else ""
    if MARK_START in text and MARK_END in text:
        text = re.sub(
            re.escape(MARK_START) + r".*?" + re.escape(MARK_END) + r"\n?",
            section,
            text,
            count=1,
            flags=re.DOTALL,
        )
    else:
        text = section + ("\n" + text.lstrip("\n") if text.strip() else "")
    README.write_text(text)


def main() -> None:
    user, names = load_config()
    token = os.environ.get("GITHUB_TOKEN")
    repos = [fetch_repo(user, name, token) for name in names]
    write_svgs(repos)
    update_readme(user, repos)
    print(f"ok — {len(repos)} pins")


if __name__ == "__main__":
    main()
