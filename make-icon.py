import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional, TypeVar

T = TypeVar("T")

SIZE = 512
"""Size of the icon image in pixels"""


def contents(filepath: str) -> str:
    with open(filepath) as f:
        return f.read()


def write(filepath: str, data: str):
    with open(filepath, "w") as f:
        f.write(data)


def next_num():
    try:
        next_num.current += 1
    except:
        next_num.current = 0
    return next_num.current


@dataclass
class Icon:
    symbol: str = ""
    """The icon symbol (e.g. "􀈕")"""

    size: float = 50
    """Percentage: symbol size / image size"""

    color: str = "#fff"
    """Color of the icon symbol: #rgb or #rrggbb or color name"""

    background: list[str] = field(default_factory=lambda: ["#000"])
    """Colors of the icon background gradiant: #rgb or #rrggbb or color name.
    If only one color is provided, the background is a solid color.
    The colors are applied from left to right.
    """

    radius: float = 50
    """Relative radius of icon corners: 0 = square, 100 = circle"""

    angle: float = 45
    """Angle of the gradient in degrees: 0 = horizontal, 90 = vertical"""

    def svg(self, scale: float = 1.0) -> str:
        size = SIZE * scale

        def px(percentage: float) -> float:
            return size * percentage / 100

        def gradiant_stops() -> Iterable[str]:
            colors = self.background
            for i, color in enumerate(colors):
                offset = 0 if len(colors) == 1 else float(i) / (len(colors) - 1)
                yield f'<stop stop-color="{color}" offset="{offset}"/>'

        id = next_num()
        return f"""
            <svg width="{size}" height="{size}"
                 viewBox="0 0 {size} {size}"
                 fill="none" xmlns="http://www.w3.org/2000/svg"
                 xmlns:xlink="http://www.w3.org/1999/xlink">
              <rect width="{size}" height="{size}" x="0" y="0"
                    rx="{px(self.radius)/2}" fill="url(#{id})" stroke="#FFFFFF"
                    stroke-width="0" stroke-opacity="100%" paint-order="stroke">
              </rect>
              <defs>
                <linearGradient id="{id}" gradientUnits="userSpaceOnUse"
                                gradientTransform="rotate({self.angle})"
                                style="transform-origin: center center;">
                  {'\n'.join(gradiant_stops())}
                </linearGradient>
              </defs>
              <text x="{size/2}" y="{size/2}"
                    font-size="{px(self.size)}" style="fill:{self.color}"
                    font-family="'SF Pro'" class="symbol"
                    text-anchor="middle" dominant-baseline="central">
                {self.symbol}
              </text>
            </svg>
            """

    @property
    def html(self) -> str:
        return f"""<!DOCTYPE html>
          <html lang="en">
            <head>
              <meta charset="UTF-8">
              <meta name="viewport"
                    content="width=device-width, initial-scale=1.0">
            </head>
            <body>
              {self.svg(scale=0.25)}
            </body>
          </html>
          """


def try_parse[T](val: str, parser: Callable[[str], T]) -> Optional[T]:
    try:
        return parser(val)
    except:
        return None


def parse_alfred_query(query: str) -> dict[str, Any]:
    try:
        return _parse_alfred_query(query)
    except:
        return {}


def _parse_alfred_query(query: str) -> dict[str, Any]:
    # trim whitespace around = and , so that when we split at
    # whitespace, we get strings of the form var_name=var_value
    query = re.sub(r"\s+=\s+", "=", query)
    query = re.sub(r"\s+,\s+", ",", query)

    parsed = {}
    for param_and_value in [pv for pv in query.split() if pv]:
        param, value = param_and_value.split("=", 1)
        if param in ["size", "s"]:
            if (size := try_parse(value, float)) is not None:
                parsed["size"] = size
        elif param in ["radius", "r"]:
            if (radius := try_parse(value, float)) is not None:
                parsed["radius"] = radius
        elif param in ["angle", "a"]:
            if (angle := try_parse(value, float)) is not None:
                parsed["angle"] = angle
        elif param in ["background", "b"]:
            bg = [color.strip() for color in value.split(",") if color.strip()]
            if bg:
                parsed["background"] = bg
        elif param in ["color", "c"]:
            parsed["color"] = value
    return parsed


def style_to_icon(style: dict) -> Icon:
    return Icon(**{k: v for k, v in style.items() if k != "name"})


def list_all():
    svgs = "\n".join(
        [
            f"""<div class='svg-item'>
                  {style_to_icon(style).svg(scale=0.125)}
                </div>"""
            for style in json.loads(contents("styles.json"))
        ]
    )
    write(
        "/tmp/showcase.html",
        f"""<!DOCTYPE html>
      <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <style>
            .svg-grid {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
            }}
            .svg-item {{
                display: flex;
                justify-content: center;
                align-items: center;
            }}
          </style>
        </head>
        <body class='svg-grid'>
          {svgs}
          <script>
            const params = new URLSearchParams(window.location.search);
            const symbol = params.get('symbol');
            document
              .querySelectorAll('.symbol')
              .forEach(el => el.textContent = symbol);
          </script>
        </body>
      </html>
      """,
    )

    json.dump(
        {
            "items": [
                {
                    "title": symbol,
                    "arg": symbol,
                    "subtitle": name,
                    "match": name,
                    "icon": {"path": "empty.png"},
                    "quicklookurl": f"file:///tmp/showcase.html?symbol={symbol}",
                }
                for name, symbol in json.loads(contents("symbols.json")).items()
            ]
        },
        sys.stdout,
    )


def svg2png(svgpath: str) -> str:
    """Convert SVG file to PNG, returning path to the PNG."""
    in_hash = hashlib.md5(open(svgpath, "rb").read()).hexdigest()
    outpath = os.path.join(os.path.dirname(svgpath), in_hash + ".png")
    if not os.path.exists(outpath):
        print(f"Converting {svgpath} to {outpath}", file=sys.stderr)
        # Use Popen, and not run or call, to avoid blocking
        subprocess.Popen(
            [
                "inkscape",
                "--export-type=png",
                svgpath,
                "--export-filename=" + outpath,
            ]
        )
    else:
        print(f"Skipping {svgpath} to {outpath}", file=sys.stderr)
    return outpath


def style_html(style: dict) -> str:
    path = f"/tmp/{style['name']}.html"
    svgs = "\n".join(
        [
            f"""<div class='svg-item'>
                  {style_to_icon(style).svg(scale=width/float(SIZE))}
                </div>"""
            for width in [128, 64, 32]
        ]
    )
    write(
        path,
        f"""<!DOCTYPE html>
      <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <style>
            .svg-grid {{
                display: grid;
                grid-template-columns: repeat(1, 1fr);
                gap: 10px;
            }}
            .svg-item {{
                display: flex;
                justify-content: center;
                align-items: center;
            }}
            .footer {{
                position: absolute;
                color: var(--result-text-color);
                bottom: 0;
            }}
          </style>
        </head>
        <body class='svg-grid'>
          {svgs}
          <script>
            const params = new URLSearchParams(window.location.search);
            const symbol = params.get('symbol');
            document
              .querySelectorAll('.symbol')
              .forEach(el => el.textContent = symbol);
          </script>
          <pre class="footer">{json.dumps(style, indent=2)}</pre>
        </body>
      </html>
      """,
    )
    return path


def edit_style():
    symbol = contents(sys.argv[2])
    name = sys.argv[3]
    mods = sys.argv[4] if len(sys.argv) > 4 else ""
    styles = json.loads(contents("styles.json"))
    style = {
        **[s for s in styles if s["name"] == name][0],
        **parse_alfred_query(mods),
    }
    svg_file_path = f"/tmp/{name}.svg"
    icon = style_to_icon(style)
    icon.symbol = symbol
    write(svg_file_path, icon.svg())
    png_file_path = svg2png(svg_file_path)
    item = {
        "title": f"Editing {name.title()}",
        "subtitle": "↩: icon file, ⌘↩: save as new style, ⌥↩: overwrite style",
        "arg": png_file_path,
        "type": "file:skipcheck",
        "icon": {"path": png_file_path},
        "quicklookurl": f"file://{style_html(style)}?symbol={symbol}",
        "text": {"copy": f"{uuid.uuid4()}"},
        "mods": {
            "cmd": {
                "arg": name,
                "subtitle": "Save as new style",
                "variables": {
                    "style": json.dumps(style),
                },
            },
            "alt": {
                "arg": name,
                "subtitle": f"Overwrite {name.title()}",
                "variables": {
                    "style": json.dumps(style),
                },
            },
        },
    }
    json.dump({"items": [item]}, sys.stdout, indent=2)
    sys.stdout.flush()


def save_style():
    name, style = sys.argv[2], json.loads(sys.argv[3])
    style["name"] = name
    styles = json.loads(contents("styles.json"))
    styles = [s if s["name"] != name else style for s in styles]
    names = [s["name"] for s in styles]
    if name not in names:
        styles.append(style)
    write("styles.json", json.dumps(styles, indent=2))


def gen_icons_for_symbol():
    symbol = contents(sys.argv[2])
    subtitle = "drag-and-drop the icon or press ↩ for icon file"
    subtitle += " (⌘↩ to edit style)"
    alfred_items = []
    for style in json.loads(contents("styles.json")):
        name = style["name"]
        svg_file_path = f"/tmp/{name}.svg"
        icon = style_to_icon(style)
        icon.symbol = symbol
        write(svg_file_path, icon.svg())
        png_file_path = svg2png(svg_file_path)
        alfred_items.append(
            {
                "title": name.title(),
                "subtitle": subtitle,
                "arg": png_file_path,
                "type": "file:skipcheck",
                "icon": {"path": png_file_path},
                "quicklookurl": f"file://{style_html(style)}?symbol={symbol}",
                "text": {"copy": f"{uuid.uuid4()}"},
                "mods": {
                    "cmd": {
                        "arg": name,
                        "subtitle": "edit style",
                    }
                },
            }
        )
    json.dump({"items": alfred_items}, sys.stdout)
    sys.stdout.flush()


if __name__ == "__main__":
    globals()[sys.argv[1]]()
