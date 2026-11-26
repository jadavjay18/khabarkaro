"""Branded headline cards (1200x630 PNG) for posts.

Used as the share image (og:image) for every post, and as the post's
picture when no stock photo was found.
"""
import hashlib
import textwrap
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
CACHE = Path(__file__).resolve().parent.parent / ".font-cache"
FONT_URLS = {
    "serif": "https://github.com/google/fonts/raw/main/ofl/newsreader/Newsreader%5Bopsz,wght%5D.ttf",
    "sans": "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz,wght%5D.ttf",
}
FALLBACK = {
    "serif": ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "sans": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
}
_paths = {}


def _font_path(kind):
    if kind in _paths:
        return _paths[kind]
    CACHE.mkdir(exist_ok=True)
    dest = CACHE / f"{kind}.ttf"
    if not dest.exists():
        try:
            urllib.request.urlretrieve(FONT_URLS[kind], dest)
        except Exception:
            dest = None
    if dest and dest.exists() and dest.stat().st_size > 10000:
        _paths[kind] = str(dest)
    else:
        _paths[kind] = next((p for p in FALLBACK[kind] if Path(p).exists()), None)
    return _paths[kind]


def _font(kind, size, bold=True):
    path = _font_path(kind)
    if not path:
        return ImageFont.load_default(size=size)
    f = ImageFont.truetype(path, size)
    try:  # variable fonts: pick a heavy weight when available
        axes = f.get_variation_axes()
        vals = []
        for a in axes:
            name = a.get("name", b"")
            name = name.decode() if isinstance(name, bytes) else str(name)
            if name.lower().startswith("weight"):
                vals.append(700 if bold else 500)
            else:
                vals.append(a.get("default", a.get("minimum")))
        f.set_variation_by_axes(vals)
    except Exception:
        pass
    return f


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_card(title, category, color, site_first, site_second, out_path):
    out_path = Path(out_path)
    key = hashlib.md5(f"v1|{title}|{category}|{color}".encode()).hexdigest()[:10]
    stamp = out_path.with_suffix(".key")
    if out_path.exists() and stamp.exists() and stamp.read_text() == key:
        return out_path
    img = Image.new("RGB", (W, H), _hex(color))
    d = ImageDraw.Draw(img)
    # soft bottom band
    d.rectangle([0, H - 110, W, H], fill=(17, 24, 39))
    pad = 72
    # category chip
    chip_font = _font("sans", 26)
    chip = category.upper()
    cw = d.textlength(chip, font=chip_font)
    d.rounded_rectangle([pad, 64, pad + cw + 36, 112], radius=8, fill=(255, 255, 255))
    d.text((pad + 18, 88), chip, font=chip_font, fill=(17, 24, 39), anchor="lm")
    # headline: shrink until it fits in 4 lines
    for size in (68, 60, 54, 48, 42):
        hf = _font("serif", size)
        lines = _wrap(d, title, hf, W - 2 * pad)
        if len(lines) <= 4:
            break
    lines = lines[:4]
    if len(lines) == 4 and len(textwrap.shorten(title, 999)) > len(" ".join(lines)):
        lines[-1] = lines[-1].rstrip(".,") + "…"
    y = 150
    lh = int(size * 1.22)
    for ln in lines:
        d.text((pad, y), ln, font=hf, fill=(255, 255, 255))
        y += lh
    # wordmark
    wf = _font("serif", 44)
    d.text((pad, H - 55), site_first, font=wf, fill=(255, 255, 255), anchor="lm")
    d.text((pad + d.textlength(site_first, font=wf), H - 55), site_second, font=wf, fill=(251, 146, 60), anchor="lm")
    tf = _font("sans", 24, bold=False)
    tag = "Trending khabar, seedhi bhasha mein"
    d.text((W - pad, H - 55), tag, font=tf, fill=(209, 213, 219), anchor="rm")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    stamp.write_text(key)
    return out_path
