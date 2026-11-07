"""MatchBase logo family: one geometry per size class, every variant. Writes SVGs into apps/web/public/brand.

The mark (after the Gemini mockup): the bracket of a tournament runs from both sides into the base in the middle, a
diamond drawn as an outline with a gold core. The full mark has two rounds per side (from about 128 px), the small one
a single round with a larger diamond for small logos; the favicon has it solid (an outline closes up at 16 px).
`pnpm brand` writes the SVGs here and, with scripts/brand/export.mjs, the PNG sizes and the icons of app/.
"""
import os
from pathlib import Path

# run from anywhere: `pnpm brand` in apps/web
OUT = Path(__file__).resolve().parents[2] / "public" / "brand"
os.makedirs(OUT, exist_ok=True)
for old in os.listdir(OUT):
    os.remove(os.path.join(OUT, old))

NAME = "MatchBase"
VIOLET = "#7C3AED"
GOLD = "#F59E0B"
WHITE = "#FFFFFF"
INK = "#1A1A1E"
PAPER_DARK = "#F0F0F5"
FONT = "'Plus Jakarta Sans', 'Inter', 'Segoe UI', system-ui, sans-serif"

# --- the two marks in a 512 box ------------------------------------------------------------------------------------
FULL = {
    "lines": (
        "M72 100 H112 V204 H72 M72 308 H112 V412 H72 M112 152 H164 V360 H112 M164 256 H195 "
        "M440 100 H400 V204 H440 M440 308 H400 V412 H440 M400 152 H348 V360 H400 M348 256 H317"
    ),
    "stroke": 18,
    "base": (220, 72, 14),   # x/y, size, corner radius of the diamond (before turning it 45 degrees)
    "core": (242, 28, 7),
}
# the 32 px draft (scaled by 16) with a larger diamond, so its outline stays open at 16 px
SMALL = {
    "lines": "M64 160 H144 V352 H64 M144 256 H152 M448 160 H368 V352 H448 M368 256 H360",
    "stroke": 32,
    "base": (192, 128, 24),
    "core": (232, 48, 10),
}


def diamond(spec: tuple[int, int, int], fill: str, extra: str = "") -> str:
    pos, size, radius = spec
    return (
        f'<rect x="{pos}" y="{pos}" width="{size}" height="{size}" rx="{radius}" transform="rotate(45 256 256)" '
        f'fill="{fill}"{extra}/>'
    )


def mark(m: dict, lines: str = WHITE, base: str = WHITE, core: str | None = GOLD, filled: bool = False) -> str:
    """The mark: bracket lines, the diamond as an outline in the line color, the core gold (or in the line color).

    `filled`: the diamond as a solid shape (the favicon: an outline closes up at 16 px).
    """
    outline = f' stroke="{base}" stroke-width="{m["stroke"]}"'
    return (
        f'<path d="{m["lines"]}" fill="none" stroke="{lines}" stroke-width="{m["stroke"]}" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
        + diamond(m["base"], base, outline)
        if filled
        else f'<path d="{m["lines"]}" fill="none" stroke="{lines}" stroke-width="{m["stroke"]}" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
        + diamond(m["base"], "none", outline)
    ) + diamond(m["core"], core or base)


def tile(rx: int = 112) -> str:
    return f'<rect width="512" height="512" rx="{rx}" fill="{VIOLET}"/>'


def svg(content: str, w: float, h: float) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
        f'aria-label="{NAME}"><title>{NAME}</title>{content}</svg>\n'
    )


def write(name: str, text: str) -> None:
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(name)


# icons: the full mark on the tile; maskable full bleed with the mark inside the safe circle; the favicon small
write("icon.svg", svg(tile() + mark(FULL), 512, 512))
write("icon-maskable.svg", svg(f'<rect width="512" height="512" fill="{VIOLET}"/><g transform="translate(25.6 25.6) scale(0.9)">{mark(FULL)}</g>', 512, 512))
write("favicon.svg", svg(tile() + mark(SMALL, filled=True), 512, 512))

# the mark without the tile: in color for light ground, and in one color (violet / white, core cut out)
write("mark.svg", svg(mark(FULL, VIOLET, VIOLET, GOLD), 512, 512))
write("mark-violet.svg", svg(mark(FULL, VIOLET, VIOLET, None), 512, 512))
write("mark-white.svg", svg(mark(FULL, WHITE, WHITE, None), 512, 512))
write("mark-small.svg", svg(mark(SMALL, VIOLET, VIOLET, GOLD), 512, 512))


def wordmark(x: float, y: float, size: int, base_color: str, anchor: str = "start") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-weight="800" font-size="{size}" letter-spacing="-0.02em" '
        f'text-anchor="{anchor}"><tspan fill="{VIOLET}">Match</tspan><tspan fill="{base_color}">Base</tspan></text>'
    )


def icon_at(x: float, y: float, size: float, m: dict) -> str:
    return f'<g transform="translate({x} {y}) scale({size / 512})">{tile()}{mark(m)}</g>'


# horizontal (header, small on screen): the small mark; stacked (login, start page, large): the full one. The -dark
# variants only swap the ink for dark ground and stay transparent, so they sit on any dark background (app, GitHub)
for suffix, ink in (("", INK), ("-dark", PAPER_DARK)):
    write(f"logo-horizontal{suffix}.svg", svg(icon_at(0, 4, 120, SMALL) + wordmark(144, 92, 80, ink), 600, 128))
    write(f"logo-stacked{suffix}.svg", svg(icon_at(130, 0, 200, FULL) + wordmark(230, 306, 72, ink, "middle"), 460, 340))
write("wordmark.svg", svg(wordmark(0, 70, 80, INK), 440, 92))
write("wordmark-dark.svg", svg(wordmark(0, 70, 80, PAPER_DARK), 440, 92))
