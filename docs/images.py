#!/usr/bin/env python3
"""Draws the README images in Canarito's colors: python3 docs/images.py"""
import base64
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGE, SURFACE, LINE = "#0E1517", "#172226", "#26353A"
TEXT, SUB, TEAL, TILE = "#E4ECEC", "#9DB0B2", "#56C2B6", "#123A3A"
CANARY, CORAL = "#F5C842", "#F08A6E"
BIRD = "M8 64 C27 72 33 40 57 33 C70 29 79 34 84 41 L95 44 L84 49 C80 65 63 75 40 73"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
# Fonts linked from an SVG shown as <img> never load, so the wordmark's face goes inline.
DISPLAY_FONT = base64.b64encode((HERE / "fonts/bricolage-grotesque.woff2").read_bytes()).decode()
DISPLAY = "'Bricolage Grotesque', " + SANS


def svg(width, height, body, label, with_font=False, shift_up=0):
    font = (f"<style>@font-face{{font-family:'Bricolage Grotesque';font-weight:200 800;"
            f"src:url(data:font/woff2;base64,{DISPLAY_FONT}) format('woff2')}}</style>") if with_font else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
            f'height="{height}" role="img" aria-label="{label}">{font}'
            f'<rect width="{width}" height="{height}" rx="28" fill="{PAGE}"/>'
            f'<g transform="translate(0 {-shift_up})">{body}</g></svg>\n')


def text(x, y, content, size=22, color=TEXT, weight=400, anchor="start", family=SANS):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{color}" text-anchor="{anchor}">{content}</text>')


def bird(x, y, size, stroke=10):
    scale = size / 100
    return (f'<g transform="translate({x} {y}) scale({scale})"><path d="{BIRD}" fill="none" stroke="{CANARY}" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round"/></g>')


def box(x, y, w, h, fill=SURFACE, stroke=LINE, radius=18):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'


def line(points, color=CANARY, width=3, dashed=False):
    dash = ' stroke-dasharray="2 9"' if dashed else ""
    path = " ".join(f"{x},{y}" for x, y in points)
    return (f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linecap="round" stroke-linejoin="round"{dash}/>')


def arrow_head(x, y, color=CANARY):
    return f'<path d="M{x - 11} {y - 7} L{x} {y} L{x - 11} {y + 7}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'


def icon(kind, x, y, color=TEXT, scale=1):
    """Line icons on a 40 px grid, the same stroke weight as the bird's small drawing."""
    common = f'fill="none" stroke="{color}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"'
    shapes = {
        "phone": '<rect x="11" y="3" width="18" height="34" rx="4"/><path d="M17 32h6"/>',
        "laptop": '<rect x="7" y="8" width="26" height="18" rx="2"/><path d="M3 32h34"/>',
        "desktop": '<rect x="4" y="6" width="32" height="22" rx="2"/><path d="M15 35h10M20 28v7"/>',
        "home": '<path d="M5 19 L20 6 L35 19"/><path d="M9 16v18h22V16"/><circle cx="20" cy="24" r="3.5"/>',
        "script": '<rect x="4" y="7" width="32" height="26" rx="3"/><path d="M11 16l5 4-5 4M19 26h9"/>',
        "watch": '<rect x="11" y="10" width="18" height="20" rx="5"/><path d="M15 10l1-6h8l1 6M15 30l1 6h8l1-6"/>',
        "pin": '<path d="M20 36s-11-10-11-18a11 11 0 0 1 22 0c0 8-11 18-11 18z"/><circle cx="20" cy="18" r="4"/>',
        "bell": '<path d="M10 27V19a10 10 0 0 1 20 0v8l2.5 3.5h-25zM16.5 34.5a3.5 3.5 0 0 0 7 0"/>',
        "chip": '<rect x="9" y="9" width="22" height="22" rx="3"/><path d="M15 3v6M25 3v6M15 31v6M25 31v6M3 15h6M3 25h6M31 15h6M31 25h6"/>',
    }
    return f'<g transform="translate({x} {y}) scale({scale})" {common}>{shapes[kind]}</g>'


def quake(cx, cy):
    rings = "".join(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{CORAL}" stroke-width="2.5" '
                    f'opacity="{o}"/>' for r, o in ((14, 1), (28, .6), (42, .3)))
    return rings + f'<circle cx="{cx}" cy="{cy}" r="5" fill="{CORAL}"/>'


def banner():
    seismogram = [(70, 290), (430, 290), (450, 282), (466, 300), (482, 262), (498, 318), (514, 248),
                  (530, 330), (546, 270), (562, 306), (578, 280), (600, 294), (630, 288), (1130, 290)]
    # The canarito.app icon as it is: page-colored tile, bird at the small-size stroke.
    app_icon = (f'<rect x="70" y="56" width="148" height="148" rx="34" fill="{PAGE}" stroke="{LINE}" stroke-width="2"/>'
                + bird(82.4, 68, 124, stroke=14))
    body = (app_icon
            + text(250, 150, "Canarito", 96, TEXT, 800, family=DISPLAY)
            + text(254, 205, "Earthquake early warnings on any device you own.", 30, SUB)
            + line(seismogram, TEAL, 2.5) + text(1130, 330, "Avisos de sismo · open source", 20, SUB, anchor="end"))
    return svg(1200, 360, body, "Canarito: earthquake early warnings on any device you own", with_font=True)


STRINGS = {
    "en": {
        "quake": "Quake", "detects": "detects it with", "phones": "real Android phones",
        "computer": "Your computer", "receptors": (("home", "Bogotá"), ("parents", "Cali")),
        "receptor": "Receptor “{}”", "thinks": "thinks it is in {}", "private": "your private", "link": "link",
        "devices": ("iPhone", "Android", "Laptop browser", "Desktop app", "Home Assistant", "Your script"),
        "mesh_1": "One receptor per place you care about. Everyone who subscribes to the link gets the alert.",
        "mesh_2": "Nothing in the middle is ours: your computer, a free ntfy server, your devices.",
        "mesh_alt": "Quake, Google, receptors on your computer, ntfy, and any device that subscribes",
        "panels": (("Install ntfy", "Free on iPhone, Android and the web."),
                   ("Subscribe to your link", "canarito.py setup prints it."),
                   ("Leave it be", "The next alert rings it.")),
        "same_1": "Same link on every device,", "same_2": "and share it with family.", "now": "now",
        "connect_alt": "Install ntfy, subscribe to your link, and the next alert arrives on that device",
        "warn_top": "The shaking travels about 3.5 km/s. The alert reached a test phone 18.8 s after the quake began.",
        "early": "{} s to take cover", "late": "none, shaking came {} s before", "alert": "alert",
        "warn_bottom": "Useful from about 80 km. For the quake right under you, no system can help.",
        "warn_alt": "Warning time by distance: none at 20 and 50 km, about 10 s at 100 km, 38 s at 200 km, 67 s at 300 km",
    },
    "es": {
        "quake": "Sismo", "detects": "lo detecta con", "phones": "celulares Android reales",
        "computer": "Tu computador", "receptors": (("casa", "Bogotá"), ("papás", "Cali")),
        "receptor": "Receptor “{}”", "thinks": "cree que está en {}", "private": "tu enlace", "link": "privado",
        "devices": ("iPhone", "Android", "Navegador", "App de escritorio", "Home Assistant", "Tu script"),
        "mesh_1": "Un receptor por cada lugar que te importa. Quien se suscriba al enlace recibe el aviso.",
        "mesh_2": "En el medio no hay nada nuestro: tu computador, un servidor gratis de ntfy y tus aparatos.",
        "mesh_alt": "Sismo, Google, receptores en tu computador, ntfy y cualquier aparato suscrito",
        "panels": (("Instala ntfy", "Gratis en iPhone, Android y la web."),
                   ("Suscríbete a tu enlace", "canarito.py setup te lo da."),
                   ("Y listo", "El próximo aviso suena ahí.")),
        "same_1": "El mismo enlace en cada aparato,", "same_2": "y compártelo con tu familia.", "now": "ahora",
        "connect_alt": "Instala ntfy, suscríbete a tu enlace y el próximo aviso llega a ese aparato",
        "warn_top": "El temblor viaja a unos 3,5 km/s. El aviso llegó a un celular de prueba 18,8 s después de empezar el sismo.",
        "early": "{} s para protegerte", "late": "nada, el temblor llegó {} s antes", "alert": "aviso",
        "warn_bottom": "Sirve desde unos 80 km. Para el sismo justo debajo de ti, ningún sistema alcanza.",
        "warn_alt": "Tiempo de aviso por distancia: nada a 20 y 50 km, unos 10 s a 100 km, 38 s a 200 km, 67 s a 300 km",
    },
}


def link_preview(line_text):
    """1200x630 card shown when someone shares canarito.app. Rendered to PNG for the site."""
    app_icon = (f'<rect x="96" y="150" width="168" height="168" rx="38" fill="{PAGE}" stroke="{LINE}" stroke-width="2"/>'
                + bird(110, 164, 140, stroke=14))
    body = (app_icon + text(300, 262, "Canarito", 112, TEXT, 800, family=DISPLAY)
            + text(100, 420, line_text, 40, SUB)
            + text(100, 540, "canarito.app", 28, TEAL, 700))
    return svg(1200, 630, body, line_text, with_font=True).replace('rx="28" fill', 'rx="0" fill', 1)


def mesh(t):
    out = []
    # Google side
    out.append(quake(84, 230))
    out.append(text(84, 300, t["quake"], 20, SUB, anchor="middle"))
    out.append(box(150, 180, 196, 100))
    out.append(text(248, 222, "Google", 24, TEXT, 700, anchor="middle"))
    out.append(text(248, 252, t["detects"], 17, SUB, anchor="middle"))
    out.append(text(248, 272, t["phones"], 17, SUB, anchor="middle"))
    out.append(line([(132, 230), (144, 230)], CORAL) + arrow_head(146, 230, CORAL))
    # Your computer with two receptors
    out.append(box(396, 110, 330, 360, fill="none", stroke=TEAL, radius=22))
    out.append(icon("laptop", 414, 124, TEAL))
    out.append(text(462, 152, t["computer"], 22, TEAL, 700))
    for (name, city), top in zip(t["receptors"], (196, 326)):
        out.append(box(420, top, 282, 108, fill=TILE, stroke=TILE))
        out.append(bird(434, top + 16, 44, stroke=12))
        out.append(text(490, top + 44, t["receptor"].format(name), 19, TEXT, 700))
        out.append(icon("pin", 488, top + 62, SUB, scale=.6))
        out.append(text(514, top + 82, t["thinks"].format(city), 17, SUB))
        out.append(line([(346, 230), (372, 230), (372, top + 54), (412, top + 54)]) + arrow_head(414, top + 54))
        out.append(line([(702, top + 54), (748, top + 54), (748, 290), (770, 290)]) + arrow_head(772, 290))
    # ntfy
    out.append(box(778, 232, 140, 116, fill=SURFACE, stroke=CANARY))
    out.append(text(848, 278, "ntfy", 26, TEXT, 700, anchor="middle"))
    out.append(text(848, 306, t["private"], 16, SUB, anchor="middle"))
    out.append(text(848, 326, t["link"], 16, SUB, anchor="middle"))
    # Anything that listens
    kinds = ("phone", "phone", "laptop", "desktop", "home", "script")
    for index, (kind, label) in enumerate(zip(kinds, t["devices"])):
        y = 108 + index * 62
        out.append(line([(918, 290), (956, 290), (956, y + 20), (980, y + 20)], CANARY, 2.5) + arrow_head(982, y + 20))
        out.append(icon(kind, 992, y, TEXT))
        out.append(text(1042, y + 27, label, 18, TEXT))
    out.append(text(48, 560, t["mesh_1"], 19, SUB))
    out.append(text(48, 588, t["mesh_2"], 19, SUB))
    return svg(1200, 556, "".join(out), t["mesh_alt"], shift_up=64)


def connect(t):
    out = []
    for index, (title, sub) in enumerate(t["panels"]):
        x = 48 + index * 380
        out.append(box(x, 100, 344, 300))
        out.append(text(x + 28, 360, title, 23, TEXT, 700))
        out.append(text(x + 28, 386, sub, 17, SUB))
        if index < 2:
            out.append(line([(x + 352, 250), (x + 372, 250)], CANARY) + arrow_head(x + 374, 250))
    # 1: the devices that run ntfy
    for offset, kind in enumerate(("phone", "laptop", "desktop", "watch")):
        out.append(icon(kind, 92 + offset * 66, 190, TEXT))
    # 2: the link field
    out.append(box(456, 176, 296, 64, fill=PAGE, stroke=CANARY, radius=12))
    out.append(text(476, 216, "ntfy.sh/canarito-3f9a…", 21, TEXT))
    out.append(text(476, 282, t["same_1"], 17, SUB))
    out.append(text(476, 304, t["same_2"], 17, SUB))
    # 3: the notification as it arrives. It comes from the ntfy app, so ntfy's bell, not our bird.
    out.append(box(830, 150, 300, 120, fill="#24343A", stroke="#24343A", radius=20))
    out.append('<rect x="846" y="168" width="44" height="44" rx="11" fill="#317F6F"/>' + icon("bell", 848, 170, TEXT))
    out.append(text(904, 186, "Alerta de sismo", 18, TEXT, 700))
    out.append(text(1114, 186, t["now"], 15, SUB, anchor="end"))
    out.append(text(904, 214, "Sismo M4.5 cerca de su zona.", 17, TEXT))
    out.append(text(904, 238, "Protéjase ahora.", 17, TEXT))
    return svg(1200, 388, "".join(out), t["connect_alt"], shift_up=52)


def warning(t):
    alert_s, wave_kms, scale_x, left = 18.8, 3.5, 8.6, 160
    out = [text(48, 56, t["warn_top"], 18, SUB)]
    for second in range(0, 91, 15):
        x = left + second * scale_x
        out.append(f'<line x1="{x}" y1="140" x2="{x}" y2="470" stroke="{LINE}" stroke-width="1"/>')
        out.append(text(x, 496, f"{second} s", 15, SUB, anchor="middle"))
    for row, km in enumerate((20, 50, 100, 200, 300)):
        y = 170 + row * 64
        shaking = km / wave_kms
        early = shaking > alert_s
        end = left + shaking * scale_x
        out.append(text(left - 20, y + 6, f"{km} km", 19, TEXT, 700, anchor="end"))
        out.append(f'<rect x="{left}" y="{y - 7}" width="{end - left}" height="14" rx="4" fill="{LINE}"/>')
        out.append(f'<circle cx="{end}" cy="{y}" r="8" fill="{TEAL if early else CORAL}" stroke="{PAGE}" stroke-width="2"/>')
        gap = f"{abs(shaking - alert_s):.0f}"
        label = t["early"].format(gap) if early else t["late"].format(gap)
        label_x = max(end, left + alert_s * scale_x) + 18
        out.append(text(label_x, y + 6, label, 17, TEAL if early else CORAL, 700))
    x = left + alert_s * scale_x
    out.append(f'<line x1="{x}" y1="128" x2="{x}" y2="470" stroke="{CANARY}" stroke-width="3" stroke-linecap="round"/>')
    out.append(bird(x - 20, 108, 26, stroke=14))
    out.append(text(x + 14, 128, t["alert"], 16, CANARY, 700))
    out.append(text(48, 540, t["warn_bottom"], 18, SUB))
    return svg(1200, 570, "".join(out), t["warn_alt"])


if __name__ == "__main__":
    # The README uses docs/*.svg in English; the site uses both languages.
    site = HERE.parent / "site/public/img"
    site.mkdir(parents=True, exist_ok=True)
    (HERE / "canarito-banner.svg").write_text(banner())
    for name, draw in (("mesh", mesh), ("connect", connect), ("warning", warning)):
        (HERE / f"{name}.svg").write_text(draw(STRINGS["en"]))
        for language, strings in STRINGS.items():
            (site / f"{name}-{language}.svg").write_text(draw(strings))
    # Link previews must be PNG; render these two with a browser at 1200x630 into site/public/og*.png.
    (site / "og-es.svg").write_text(link_preview("Avisos de sismo en cualquier dispositivo."))
    (site / "og-en.svg").write_text(link_preview("Earthquake warnings on any device."))
