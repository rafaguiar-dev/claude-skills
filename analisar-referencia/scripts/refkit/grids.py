"""Grades de frames com tempo e palavras faladas — a forma de o Claude "assistir" um trecho."""
import math
import re
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .media import decode, frame_at
from .util import fmt_t, read_json

_FONTS = {}


def font(size: int, bold=False):
    key = (size, bold)
    if key not in _FONTS:
        names = ["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]
        for name in names:
            path = Path("C:/Windows/Fonts") / name
            if path.exists():
                _FONTS[key] = ImageFont.truetype(str(path), size)
                break
        else:
            _FONTS[key] = ImageFont.load_default(size)
    return _FONTS[key]


# ---------------------------------------------------------------- transcrição

def load_words(path) -> list:
    """Lê transcript.json (formato ref.transcript@1) como lista plana de palavras."""
    if not path:
        return []
    data = read_json(path)
    return [w for seg in data.get("segmentos", []) for w in seg.get("palavras", [])
            if w.get("inicio") is not None and w.get("fim") is not None]


def words_at(words: list, t: float, context=3) -> tuple:
    """(palavras ativas, contexto) no instante t."""
    if not words:
        return [], []
    active = [i for i, w in enumerate(words) if w["inicio"] <= t < w["fim"]]
    if active:
        first, last = active[0], active[-1]
    else:
        first = last = min(range(len(words)), key=lambda i: abs(words[i]["inicio"] - t))
    lo, hi = max(0, first - context), min(len(words), last + context + 1)
    return [words[i] for i in active], words[lo:hi]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"[^\w]", "", "".join(c for c in text if not unicodedata.combining(c)))


def phrase_ranges(words: list, phrase: str) -> list:
    """Intervalos (inicio, fim) em que a frase é falada; ignora pontuação, caixa e acentos."""
    query = _norm(phrase)
    matches = []
    for first in range(len(words)):
        if not _norm(words[first]["texto"]):
            continue
        joined = ""
        for last in range(first, len(words)):
            joined += _norm(words[last]["texto"])
            if joined == query:
                matches.append((words[first]["inicio"], words[last]["fim"]))
                break
            if len(joined) >= len(query) or not query.startswith(joined):
                break
    return matches


# ---------------------------------------------------------------- composição

def _wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def compose(cells: list, columns: int, cell_w: int, title: str = None) -> Image.Image:
    """cells: [{img, t, words_active, words_context, label}] -> uma página."""
    pad, fs = 6, max(13, cell_w // 26)
    f_time, f_word, f_title = font(fs, bold=True), font(fs), font(fs + 4, bold=True)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    blocks = []
    for c in cells:
        img = c["img"]
        if img.width != cell_w:
            img = img.resize((cell_w, int(img.height * cell_w / img.width)), Image.LANCZOS)
        header = fmt_t(c["t"]) + (f"  {c['label']}" if c.get("label") else "")
        ctx = c.get("words_context") or []
        active_ids = {id(w) for w in c.get("words_active") or []}
        text = " ".join(f"[{w['texto'].strip()}]" if id(w) in active_ids else w["texto"].strip() for w in ctx)
        lines = _wrap(probe, text, f_word, cell_w - 2 * pad)[:3] if text else []
        label_h = pad + fs + 4 + len(lines) * (fs + 3) + pad
        blocks.append((img, header, lines, label_h))
    rows = math.ceil(len(blocks) / columns)
    row_h = [max(b[0].height + b[3] for b in blocks[r * columns:(r + 1) * columns]) for r in range(rows)]
    top = (fs + 16) if title else 0
    sheet = Image.new("RGB", (columns * (cell_w + pad) + pad, top + sum(row_h) + (rows + 1) * pad), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    if title:
        draw.text((pad, 6), title, font=f_title, fill=(255, 255, 255))
    y = top + pad
    for r in range(rows):
        for ci, (img, header, lines, _) in enumerate(blocks[r * columns:(r + 1) * columns]):
            x = pad + ci * (cell_w + pad)
            sheet.paste(img, (x, y))
            ty = y + img.height + pad
            draw.text((x + pad, ty), header, font=f_time, fill=(255, 214, 74))
            ty += fs + 4
            for line in lines:
                draw.text((x + pad, ty), line, font=f_word, fill=(230, 230, 230))
                ty += fs + 3
        y += row_h[r] + pad
    return sheet


def save_pages(cells: list, to, columns=4, rows=3, cell_w=360, title=None) -> list:
    """Salva em uma ou várias páginas. `to` .jpg -> nome base; pasta -> pagina_NN.jpg."""
    to = Path(to)
    per_page = columns * rows if rows else len(cells)
    pages = [cells[i:i + per_page] for i in range(0, len(cells), per_page)] or [[]]
    out = []
    for n, page in enumerate(pages, 1):
        if to.suffix.lower() in (".jpg", ".jpeg", ".png"):
            path = to if len(pages) == 1 else to.with_name(f"{to.stem}_{n:02d}{to.suffix}")
        else:
            path = to / f"pagina_{n:02d}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        t_title = title if len(pages) == 1 or not title else f"{title} ({n}/{len(pages)})"
        compose(page, min(columns, max(1, len(page))), cell_w, t_title).save(path, quality=88)
        out.append(path)
    return out


# ---------------------------------------------------------------- amostragem

def sample_cells(src, info, times, words=None, cell_w=360, crop=None, labels=None) -> list:
    cells = []
    for i, t in enumerate(times):
        active, ctx = words_at(words, t) if words else ([], [])
        cells.append({"img": frame_at(src, t, info, width=cell_w, crop=crop), "t": t,
                      "words_active": active, "words_context": ctx,
                      "label": labels[i] if labels else None})
    return cells


def every_frame_cells(src, info, start, end, words=None, cell_w=360, crop=None) -> list:
    frames, times = decode(src, info, width=cell_w, start=start, duration=end - start, crop=crop)
    cells = []
    for frame, t in zip(frames, times):
        active, ctx = words_at(words, t) if words else ([], [])
        cells.append({"img": Image.fromarray(frame), "t": t, "words_active": active, "words_context": ctx})
    return cells
