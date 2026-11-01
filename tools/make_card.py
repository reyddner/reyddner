"""Gera dark_mode.svg e light_mode.svg: foto em ASCII + dados no estilo neofetch.

Uso: python tools/make_card.py   (token em GH_TOKEN ou do `gh auth token`)
"""
import datetime as dt
import json
import os
import subprocess
import time
import urllib.request
from html import escape
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PHOTO = ROOT / "_fonte" / "busto_sem_fundo.png"  # fica fora do git (.gitignore)
LOGIN = "reyddner"
START = dt.date(2011, 7, 1)  # primeiro emprego no setor (Engefort)
COLS = 46
RAMP = " .:-=+*#%@"
WIDTH = 54  # largura da coluna de dados, em caracteres

FIELDS = [
    ("header", f"{LOGIN}@github"),
    ("OS", "Windows"),
    ("Uptime", None),  # calculado
    ("Host", "Mont Cruz Engenharia"),
    ("Kernel", "Civil Engineer · Full Stack Dev"),
    ("IDE", "Claude Code, Codex, VS Code"),
    ("blank", ""),
    ("Languages.Programming", "TypeScript, Python, C#"),
    ("Languages.Real", "Portuguese, English"),
    ("blank", ""),
    ("section", "Contact"),
    ("Website", "montcruz.com.br"),
    ("LinkedIn", "in/reyddnerandrei"),
    ("blank", ""),
    ("section", "GitHub Stats"),
]

THEMES = {
    "dark_mode": dict(bg="#161b22", border="#30363d", art="#c9d1d9", key="#ffa657",
                      value="#a5d6ff", dots="#616e7f", head="#58a6ff", add="#3fb950", rem="#f85149"),
    "light_mode": dict(bg="#f6f8fa", border="#d0d7de", art="#24292f", key="#953800",
                       value="#0a3069", dots="#c2cfde", head="#0550ae", add="#1a7f37", rem="#cf222e"),
}


def token():
    return os.environ.get("GH_TOKEN") or subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def api(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"bearer {token()}"})
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read() or "null")


def gql(query):
    return api("https://api.github.com/graphql", {"query": query})[1]["data"]


def stats():
    v = gql("""{ viewer { followers{totalCount}
        repositories(ownerAffiliations:OWNER, first:100){ totalCount nodes{ nameWithOwner stargazerCount } }
        repositoriesContributedTo(contributionTypes:[COMMIT]){ totalCount }
        contributionsCollection{ contributionYears } } }""")["viewer"]
    commits = 0
    for y in v["contributionsCollection"]["contributionYears"]:
        c = gql(f'{{ viewer {{ contributionsCollection(from:"{y}-01-01T00:00:00Z", to:"{y}-12-31T23:59:59Z")'
                f'{{ totalCommitContributions }} }} }}')
        commits += c["viewer"]["contributionsCollection"]["totalCommitContributions"]
    add = rem = 0
    for repo in v["repositories"]["nodes"]:
        for _ in range(6):  # a API responde 202 enquanto calcula
            status, data = api(f"https://api.github.com/repos/{repo['nameWithOwner']}/stats/contributors")
            if status == 200:
                break
            time.sleep(3)
        for c in data or []:
            if c.get("author") and c["author"]["login"].lower() == LOGIN:
                add += sum(w["a"] for w in c["weeks"])
                rem += sum(w["d"] for w in c["weeks"])
    return dict(repos=v["repositories"]["totalCount"], contrib=v["repositoriesContributedTo"]["totalCount"],
                stars=sum(r["stargazerCount"] for r in v["repositories"]["nodes"]),
                followers=v["followers"]["totalCount"], commits=commits, add=add, rem=rem)


def uptime(today):
    y, m = today.year - START.year, today.month - START.month
    d = today.day - START.day
    if d < 0:
        m -= 1
        d += (today.replace(day=1) - dt.timedelta(days=1)).day
    if m < 0:
        y -= 1
        m += 12
    return f"{y} years, {m} months, {d} days"


def ascii_art():
    im = Image.open(PHOTO).convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())
    rows = round(COLS * im.height / im.width * 0.5)
    small = im.resize((COLS, rows), Image.LANCZOS)
    # recorte oval: os ombros vão sumindo nas laterais, como no modelo
    oval = Image.new("L", (COLS, rows), 0)
    ImageDraw.Draw(oval).ellipse((0, -rows * 0.25, COLS - 1, rows * 1.02), fill=255)
    alpha = ImageChops.multiply(small.getchannel("A"), oval)
    gray = ImageOps.autocontrast(small.convert("L"), cutoff=2, mask=alpha.point(lambda a: 255 if a > 128 else 0))
    lines = []
    for yy in range(rows):
        row = ""
        for xx in range(COLS):
            if alpha.getpixel((xx, yy)) < 100:
                row += " "
            else:
                # dentro da pessoa nunca vira espaço, senão o terno escuro some
                row += RAMP[1 + min(len(RAMP) - 2, gray.getpixel((xx, yy)) * (len(RAMP) - 1) // 256)]
        lines.append(row.rstrip())
    return lines


def tspan(text, color):
    return f'<tspan fill="{color}">{escape(text)}</tspan>'


def kv(key, value, t, width=WIDTH):
    dots = " " + "." * max(1, width - len(key) - len(value) - 4) + " "
    return tspan(key + ":", t["key"]) + tspan(dots, t["dots"]) + tspan(value, t["value"])


def pair(k1, v1, k2, v2, t):
    left = WIDTH // 2 + 4
    return (kv(k1, v1, t, left) + tspan(" | ", t["dots"]) + kv(k2, v2, t, WIDTH - left - 3))


def info_lines(s, t, today):
    out = []
    for key, value in FIELDS:
        if key == "header":
            out.append(tspan(value, t["head"]) + tspan(" " + "─" * (WIDTH - len(value) - 1), t["dots"]))
        elif key == "section":
            out.append(tspan("─ " + value, t["head"]) + tspan(" " + "─" * (WIDTH - len(value) - 3), t["dots"]))
        elif key == "blank":
            out.append(" ")  # tspan vazio não avança a linha
        else:
            out.append(kv(key, uptime(today) if key == "Uptime" else value, t))
    out.append(pair("Repos", f"{s['repos']} {{Contributed: {s['contrib']}}}", "Stars", f"{s['stars']:,}", t))
    out.append(pair("Commits", f"{s['commits']:,}", "Followers", f"{s['followers']:,}", t))
    out.append(tspan("Lines of Code: ", t["key"]) + tspan(f"{s['add'] - s['rem']:,} ", t["value"])
               + tspan("( ", t["dots"]) + tspan(f"{s['add']:,}++", t["add"]) + tspan(", ", t["dots"])
               + tspan(f"{s['rem']:,}--", t["rem"]) + tspan(" )", t["dots"]))
    return out


def svg(art, info, t):
    lh, top = 20, 30
    n = max(len(art), len(info) + 2)
    h = top + n * lh + 10
    art_top = top + (n - len(art)) * lh // 2
    info_top = top + (n - len(info)) * lh // 2
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="985" height="{h}" font-family="ConsolasFallback,Consolas,monospace" font-size="16px">',
             '<style>@font-face{font-family:ConsolasFallback;src:local("Consolas");size-adjust:109%}text{white-space:pre}</style>',
             f'<rect width="985" height="{h}" rx="15" fill="{t["bg"]}" stroke="{t["border"]}"/>',
             f'<text x="20" y="{art_top}" fill="{t["art"]}">']
    parts += [f'<tspan x="20" dy="{lh if i else 0}">{escape(l)}</tspan>' for i, l in enumerate(art)]
    parts.append(f'</text><text x="460" y="{info_top}">')
    parts += [f'<tspan x="460" dy="{lh if i else 0}">{l}</tspan>' for i, l in enumerate(info)]
    parts.append("</text></svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    today = dt.date.today()
    s, art = stats(), ascii_art()
    print(s)
    for name, t in THEMES.items():
        (ROOT / f"{name}.svg").write_text(svg(art, info_lines(s, t, today), t), encoding="utf-8")
    print("\n".join(art))
