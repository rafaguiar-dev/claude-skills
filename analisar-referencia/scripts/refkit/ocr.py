"""Texto na tela: OCR (RapidOCR/PP-OCR em ONNX, local), rastreamento no tempo, cores e ritmo das legendas.

Limitação: o modelo padrão lê bem letras latinas, mas pode perder acentos (ã, ç, é). O texto serve para
localizar e cronometrar; a leitura exata vem dos recortes em evidencias/legendas."""
import difflib
import re
import unicodedata

import cv2
import numpy as np

from .media import decode
from .util import hexcolor, log, r

_ENGINE = None


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR()
    return _ENGINE


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"[^\w]", "", "".join(c for c in text if not unicodedata.combining(c)))


def _lum(rgb) -> float:
    return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255


def _sat(rgb) -> float:
    mx, mn = max(rgb), min(rgb)
    return 0 if mx == 0 else (mx - mn) / mx


def _colors(img, box) -> dict:
    h_img, w_img = img.shape[:2]
    x0, y0 = box[:, 0].min(), box[:, 1].min()
    x1, y1 = box[:, 0].max(), box[:, 1].max()
    pad = max(2, int((y1 - y0) * 0.18))
    x0, y0 = int(max(0, x0 - pad)), int(max(0, y0 - pad))
    x1, y1 = int(min(w_img, x1 + pad)), int(min(h_img, y1 + pad))
    crop = img[y0:y1, x0:x1]
    if crop.size < 48:
        return {}
    px = crop.reshape(-1, 3).astype(np.float32)
    k = 4 if len(px) > 200 else 2
    _, labels, centers = cv2.kmeans(px, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0),
                                    2, cv2.KMEANS_PP_CENTERS)
    labels = labels.reshape(crop.shape[:2])
    ring = max(1, pad // 2)
    ring_mask = np.zeros(labels.shape, bool)
    ring_mask[:ring], ring_mask[-ring:], ring_mask[:, :ring], ring_mask[:, -ring:] = True, True, True, True
    counts = np.bincount(labels.ravel(), minlength=k) / labels.size
    ring_share = np.bincount(labels[ring_mask], minlength=k) / ring_mask.sum()
    # fundo = grupos que dominam a borda do recorte (vídeo atrás ou caixa sólida)
    bg = {i for i in range(k) if ring_share[i] > 0.15}
    bg.add(int(ring_share.argmax()))
    ring_px = crop[ring_mask].astype(np.float32)
    out = {}
    if float(ring_px.std(axis=0).mean()) < 16:
        # caixa de verdade: a borda uniforme difere do vídeo logo fora dela
        ex = pad * 3
        X0, Y0, X1, Y1 = max(0, x0 - ex), max(0, y0 - ex), min(w_img, x1 + ex), min(h_img, y1 + ex)
        outer = np.ones((Y1 - Y0, X1 - X0), bool)
        outer[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0] = False
        outer_px = img[Y0:Y1, X0:X1][outer].astype(np.float32)
        if outer_px.size and np.abs(outer_px.mean(0) - ring_px.mean(0)).sum() > 60:
            out["fundo"] = hexcolor(centers[int(ring_share.argmax())])
    others = [i for i in np.argsort(-counts) if i not in bg and counts[i] > 0.04]
    if not others:
        return out
    # contorno encosta no fundo; preenchimento fica no miolo das letras
    bg_mask = np.isin(labels, list(bg)).astype(np.uint8)
    near_bg = cv2.dilate(bg_mask, np.ones((3, 3), np.uint8), iterations=2).astype(bool)
    touch = {i: float(near_bg[labels == i].mean()) for i in others}
    fill = min(others, key=lambda i: (touch[i], -counts[i]))
    out["cor_texto"] = hexcolor(centers[fill])
    for i in others:
        if i == fill:
            continue
        c, f = centers[i], centers[fill]
        if touch[i] > touch[fill] + 0.15 and abs(_lum(c) - _lum(f)) > 0.3:
            out["cor_contorno"] = hexcolor(c)
            out["contorno_proporcao"] = r(counts[i] / max(1e-3, counts[fill]), 2)
            break
    for i in others:
        if i == fill or hexcolor(centers[i]) == out.get("cor_contorno"):
            continue
        c, f = centers[i], centers[fill]
        if counts[i] > 0.06 and touch[i] < 0.8 and _sat(c) > 0.35 and np.abs(c - f).sum() > 120 and _lum(c) > 0.25:
            out["cor_destaque"] = hexcolor(c)
            break
    return out


def _anchor(cx: float, cy: float) -> str:
    v = "top" if cy < 0.33 else ("bottom" if cy > 0.66 else "middle")
    h = "left" if cx < 0.33 else ("right" if cx > 0.66 else "center")
    return "center" if (v, h) == ("middle", "center") else f"{v}-{h}"


def _speech_match(text, t0, t1, words):
    if not words:
        return None
    window = [w for w in words if w["fim"] >= t0 - 1.0 and w["inicio"] <= t1 + 1.0]
    if not window:
        return 0.0
    spoken = [norm(w["texto"]) for w in window]
    toks = [norm(t) for t in text.split() if norm(t)]
    by_token = sum(1 for tk in toks if any(difflib.SequenceMatcher(None, tk, sp).ratio() >= 0.75 for sp in spoken))
    by_token = by_token / len(toks) if toks else 0
    joined, spoken_joined = norm(text), "".join(spoken)
    if not joined:
        return 0.0
    blocks = difflib.SequenceMatcher(None, joined, spoken_joined, autojunk=False).get_matching_blocks()
    by_chars = sum(b.size for b in blocks if b.size >= 3) / len(joined)
    return round(max(by_token, by_chars), 2)


def _word_count(text, t0, t1, words):
    toks = [t for t in text.split() if norm(t)]
    if len(toks) == 1 and len(norm(text)) > 10 and words:
        joined = norm(text)
        found = [w for w in words if w["fim"] >= t0 - 0.5 and w["inicio"] <= t1 + 0.5
                 and len(norm(w["texto"])) >= 2 and norm(w["texto"]) in joined]
        return max(1, len(found))
    return max(1, len(toks))


def read_text(src, info: dict, words: list, fps=4.0, width=720) -> dict:
    width = min(width, info["largura"])
    duration = info["duracao"]
    step = 1.0 / fps
    detections = []  # (t, box_norm, text, score, colors, h_rel)
    chunk = 8.0
    t = 0.0
    engine = _engine()
    while t < duration:
        frames, times = decode(src, info, width=width, fps=fps, start=t, duration=min(chunk, duration - t))
        for frame, ft in zip(frames, times):
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            result, _ = engine(bgr, use_cls=False)
            for box, text, score in result or []:
                score = float(score)
                if score < 0.6 or not norm(text):
                    continue
                box = np.array(box, dtype=np.float32)
                h, w = frame.shape[:2]
                bn = [box[:, 0].min() / w, box[:, 1].min() / h,
                      (box[:, 0].max() - box[:, 0].min()) / w, (box[:, 1].max() - box[:, 1].min()) / h]
                detections.append((ft, bn, text.strip(), score, _colors(frame, box)))
        t += chunk
        log(f"OCR {min(t, duration):.0f}/{duration:.0f}s")

    # rastreia a mesma linha de texto ao longo das amostras
    events, open_ev = [], []
    for ft, bn, text, score, colors in sorted(detections, key=lambda d: d[0]):
        cx, cy = bn[0] + bn[2] / 2, bn[1] + bn[3] / 2
        match = None
        for ev in open_ev:
            if ft - ev["_last"] > step * 2.5:
                continue
            same_place = abs(ev["_cx"] - cx) < 0.08 and abs(ev["_cy"] - cy) < 0.05
            similar = difflib.SequenceMatcher(None, norm(ev["texto"]), norm(text)).ratio() > 0.8
            if same_place and similar:
                match = ev
                break
        if match:
            match["_last"] = ft
            match["_n"] += 1
            if score > match["_best"]:
                match.update(texto=text, _best=score, _colors=colors, _bn=bn)
        else:
            ev = {"texto": text, "_first": ft, "_last": ft, "_n": 1, "_best": score, "_colors": colors, "_bn": bn,
                  "_cx": cx, "_cy": cy}
            open_ev.append(ev)
            events.append(ev)
        open_ev = [e for e in open_ev if ft - e["_last"] <= step * 2.5]

    out_events = []
    for ev in events:
        start, end = r(ev["_first"]), r(min(duration, ev["_last"] + step))
        bn = ev["_bn"]
        match = _speech_match(ev["texto"], start, end, words)
        letters = [c for c in ev["texto"] if c.isalpha()]
        if end - start > 0.8 * duration and bn[3] < 0.035:
            kind = "interface/marca"
        elif match is not None and match >= 0.5:
            kind = "legenda"
        else:
            kind = "texto_na_tela"
        out_events.append({
            "texto": ev["texto"], "inicio": start, "fim": end, "duracao": r(end - start),
            "tipo": kind, "correspondencia_fala": match,
            "caixa": [r(v) for v in bn], "centro_y": r(ev["_cy"]), "altura_linha": r(bn[3]),
            "posicao": _anchor(ev["_cx"], ev["_cy"]),
            "maiusculas": bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.8,
            "palavras": _word_count(ev["texto"], start, end, words),
            "confianca_ocr": r(ev["_best"], 2), "amostras": ev["_n"], **ev["_colors"],
        })
    out_events.sort(key=lambda e: (e["inicio"], e["centro_y"]))
    return {"amostragem_fps": fps, "eventos": out_events, **_caption_system(out_events, words, step)}


def _blocks(events, step):
    """Agrupa linhas que aparecem juntas (mesmo instante, verticalmente próximas) num bloco."""
    blocks = []
    for ev in events:
        for b in blocks:
            if abs(b["inicio"] - ev["inicio"]) <= step * 1.5 and \
                    abs(b["_cy"] - ev["centro_y"]) < 2.8 * max(b["_h"], ev["altura_linha"]):
                b["linhas"].append(ev)
                b["fim"] = max(b["fim"], ev["fim"])
                b["_cy"] = max(b["_cy"], ev["centro_y"])
                break
        else:
            blocks.append({"inicio": ev["inicio"], "fim": ev["fim"], "linhas": [ev], "_cy": ev["centro_y"],
                           "_h": ev["altura_linha"]})
    out = []
    for b in blocks:
        lines = sorted(b["linhas"], key=lambda e: e["centro_y"])
        out.append({"inicio": b["inicio"], "fim": b["fim"], "duracao": r(b["fim"] - b["inicio"]),
                    "texto": " / ".join(l["texto"] for l in lines), "linhas": len(lines),
                    "palavras": sum(l["palavras"] for l in lines), "posicao": lines[-1]["posicao"],
                    # OCR costuma perder espaços: caracteres = letras + (palavras - 1)
                    "caracteres_por_linha": [len(l["texto"].replace(" ", "")) + max(0, l["palavras"] - 1)
                                             for l in lines],
                    "largura": r(max(l["caixa"][2] for l in lines), 3)})
    return out


def _config_key(ev):
    def q(hexc):
        if not hexc:
            return None
        rgb = [int(hexc[i:i + 2], 16) for i in (1, 3, 5)]
        return tuple(v // 64 for v in rgb)
    band = "top" if ev["centro_y"] < 0.33 else ("bottom" if ev["centro_y"] > 0.66 else "middle")
    return band, q(ev.get("cor_texto"))


def _stroke_majority(evs):
    """Contorno some sobre fundo da mesma cor, então vota só entre eventos em que ele apareceu."""
    vals = [e.get("cor_contorno") or e.get("_voto_contorno") for e in evs]
    vals = [v for v in vals if v]
    if len(vals) < 2:
        return None
    return _majority([{"c": v} for v in vals], "c", min_frac=0.5)


def _majority(evs, key, min_frac=0.4):
    """Valor mais comum de `key` (cores parecidas contam juntas) se cobrir `min_frac` dos eventos."""
    vals = [e.get(key) for e in evs if e.get(key)]
    buckets = {}
    for v in vals:
        rgb = tuple(int(v[i:i + 2], 16) for i in (1, 3, 5))
        buckets.setdefault(tuple(c // 40 for c in rgb), []).append(rgb)
    if not buckets:
        return None
    top = max(buckets.values(), key=len)
    if len(top) < max(1, min_frac * len(evs)):
        return None
    return hexcolor(np.mean(top, axis=0))


def _caption_system(events, words, step):
    caps = [e for e in events if e["tipo"] == "legenda"]
    texts = [e for e in events if e["tipo"] == "texto_na_tela"]
    result = {"resumo_textos_na_tela": [{k: e[k] for k in ("texto", "inicio", "fim", "posicao")} for e in texts]}
    if not caps:
        result["legendas"] = {"tem_legenda": False}
        return result
    blocks = _blocks(caps, step)
    wpb = np.array([b["palavras"] for b in blocks])
    med = float(np.median(wpb))
    growing = sum(1 for a, b in zip(blocks, blocks[1:])
                  if norm(b["texto"]).startswith(norm(a["texto"])) and len(norm(b["texto"])) > len(norm(a["texto"])))
    configs = {}
    for e in caps:
        configs.setdefault(_config_key(e), []).append(e)
    # sobre fundo claro o preenchimento some no vídeo e o contorno vira "cor do texto":
    # funde esse grupo minoritário no estilo cujo contorno tem essa cor
    groups = sorted(configs.values(), key=len, reverse=True)
    kept = []
    for evs in groups:
        fill = _majority(evs, "cor_texto")
        host = None
        for big in kept:
            stroke = _stroke_majority(big)
            same_band = _config_key(big[0])[0] == _config_key(evs[0])[0]
            if same_band and fill and stroke and len(evs) < len(big) and \
                    sum(abs(int(fill[i:i + 2], 16) - int(stroke[i:i + 2], 16)) for i in (1, 3, 5)) < 90:
                host = big
                break
        if host is not None:
            for e in evs:
                e["_voto_contorno"] = e.get("cor_texto")
            host.extend(evs)
        else:
            kept.append(list(evs))
    configs = {i: evs for i, evs in enumerate(kept)}
    cfg_out = []
    for evs in sorted(configs.values(), key=len, reverse=True):
        stroke = _stroke_majority(evs)
        with_stroke = [e for e in evs if e.get("cor_contorno")]
        native = [e for e in evs if not e.get("_voto_contorno")] or evs
        rep = max(with_stroke if stroke and with_stroke else native, key=lambda e: e["confianca_ocr"])
        cfg = {
            "ocorrencias": len(evs), "exemplo": rep["texto"], "exemplo_tempo": rep["inicio"],
            "posicao": rep["posicao"], "centro_y": r(np.median([e["centro_y"] for e in evs])),
            "altura_linha": r(np.median([e["altura_linha"] for e in evs])),
            "maiusculas": sum(e["maiusculas"] for e in evs) / len(evs) > 0.6,
            "cor_texto": _majority(native, "cor_texto") or rep.get("cor_texto"),
            "caixa_exemplo": rep["caixa"],
        }
        if stroke:
            cfg["cor_contorno"] = stroke
            cfg["contorno_proporcao"] = r(np.median([e.get("contorno_proporcao") or 0 for e in with_stroke]), 2) \
                if with_stroke else None
        for key in ("fundo", "cor_destaque"):
            if _majority(evs, key):
                cfg[key] = _majority(evs, key)
        cfg_out.append(cfg)
    # como a página quebra: por número de palavras ou pelo comprimento da linha?
    n = len(blocks)
    dist = {k: r(sum(1 for b in blocks if (b["palavras"] if b["palavras"] < 4 else 4) == v) / n, 2)
            for k, v in (("1", 1), ("2", 2), ("3", 3), ("4+", 4))}
    one_line = sum(1 for b in blocks if b["linhas"] == 1) / n
    chars = [c for b in blocks for c in b["caracteres_por_linha"]]
    chars_1l = [b["caracteres_por_linha"][0] for b in blocks if b["linhas"] == 1]
    widths = [b["largura"] for b in blocks if b["linhas"] == 1] or [b["largura"] for b in blocks]
    paging = {
        "distribuicao_palavras_por_pagina": dist,
        "fracao_uma_linha": r(one_line, 2),
        "caracteres_por_linha_mediana": r(np.median(chars), 1),
        "caracteres_por_linha_p90": r(np.percentile(chars, 90), 1),
        "largura_linha_mediana": r(np.median(widths), 3),
        "largura_linha_p90": r(np.percentile(widths, 90), 3),
    }
    if one_line >= 0.7 and dist["1"] >= 0.1 and chars_1l:
        paging["quebra"] = "por comprimento (a página cabe numa linha; palavras longas ficam sozinhas)"
        paging["limite_caracteres_por_linha"] = int(np.ceil(np.percentile(chars_1l, 90)))
    else:
        paging["quebra"] = "por número de palavras"
    result["legendas"] = {
        "tem_legenda": True,
        "paginacao": paging,
        "blocos": blocks,
        "palavras_por_bloco_mediana": med,
        "duracao_bloco_mediana": r(np.median([b["duracao"] for b in blocks]), 2),
        "linhas_por_bloco": r(np.median([b["linhas"] for b in blocks]), 1),
        "modo": "palavra a palavra" if med <= 1.5 else ("blocos curtos (2-3 palavras)" if med <= 3.5
                                                        else "frase (4+ palavras)"),
        "revelacao_progressiva": growing >= max(2, 0.3 * (len(blocks) - 1)),
        "configuracoes": cfg_out[:6],
    }
    return result
