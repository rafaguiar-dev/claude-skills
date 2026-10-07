"""Traduz o que foi observado para recursos do OpenChatCut (templates de legenda, âncoras, transições).

Valores dos templates copiados de src/captions/styles.ts do OpenChatCut (v0.2.15)."""
from .util import r

# stroke: 0 sem contorno, 1 fino, 2 grosso | hl = cor da palavra ativa | hlbg = fundo da palavra ativa
TEMPLATES = {
    "plain": dict(fill="#FFFFFF", stroke=0),
    "black-bar": dict(fill="#FFFFFF", box="#000000"),
    "netflix": dict(fill="#FFFFFF", stroke=0),
    "bili": dict(fill="#F8FAFC", hlbg="#6EE7F9", stroke=1),
    "tiktok": dict(fill="#FFFDF7", hlbg="#FF2E63", stroke=1),
    "story": dict(fill="#FFFFFF", hl="#FFD84A", stroke=1),
    "bold-outline": dict(fill="#FFFFFF", stroke=2, wpp=3),
    "studio": dict(fill="#F8F7F2", hlbg="#FFFFFF", stroke=0),
    "white-card": dict(fill="#ABABAB", hl="#040404", stroke=0),
    "the-french-dispatch": dict(fill="#0F0F0F", hlbg="#F6C239", stroke=0, wpp=3),
    "bubble-pop": dict(fill="#FFFFFF", hl="#FFEC1A", stroke=2, upper=True, wpp=2, big=True),
    "submagic": dict(fill="#FFFFFF", hlbg="#00E83C", stroke=0, big=True),
    "off-the-wall": dict(fill="#000000", hlbg="#FFFFFF", stroke=0, big=True),
    "boyz-n-the-hood": dict(fill="#FFFFFF", hl="#FFF200", stroke=2, upper=True, big=True),
    "dogme": dict(fill="#FCFCFA", stroke=0, upper=True),
    "persona": dict(fill="#9C928A", hl="#1F1B17", stroke=0, big=True),
    "luxe": dict(fill="#F8E8C6", hlbg="#F8E8C6", stroke=0),
    "noir": dict(fill="#F5EFE3", hlbg="#8E263B", stroke=0),
    "atelier": dict(fill="#24120A", hlbg="#B64A3B", stroke=0),
    "product": dict(fill="#F7FFF9", hlbg="#A3FF12", stroke=0),
    "signal": dict(fill="#EAFBFF", hlbg="#4DFFDF", stroke=0, upper=True),
}

ANCHORS = {"top-left", "top-center", "top-right", "middle-left", "center", "middle-right",
           "bottom-left", "bottom-center", "bottom-right"}


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _cdist(a, b) -> float:
    if not a or not b:
        return 1.0
    return sum(abs(x - y) for x, y in zip(_rgb(a), _rgb(b))) / (3 * 255)


def suggest_caption(legendas: dict) -> dict:
    if not legendas.get("tem_legenda") or not legendas.get("configuracoes"):
        return {}
    cfgs = legendas["configuracoes"]
    cfg = dict(cfgs[0])
    # karaokê: páginas de 1 palavra (ou só a palavra ativa lida pelo OCR) aparecem inteiras na cor de
    # destaque e viram um "estilo" próprio. Se outro estilo na mesma altura tem texto de outra cor e
    # destaque igual a essa cor, o estilo real é esse outro (texto normal + palavra ativa colorida).
    for other in cfgs[1:]:
        same_band = abs(other["centro_y"] - cfg["centro_y"]) < 0.04
        hl_match = other.get("cor_destaque") and _cdist(other["cor_destaque"], cfg.get("cor_texto")) < 0.1
        # destaque nem sempre é lido pelo OCR: aceita também um 2º estilo frequente de cor bem diferente
        frequent = not other.get("cor_destaque") and other["ocorrencias"] >= 0.15 * cfg["ocorrencias"] and             _cdist(other.get("cor_texto"), cfg.get("cor_texto")) > 0.25
        if same_band and (hl_match or frequent) and _cdist(other.get("cor_texto"), cfg.get("cor_texto")) > 0.15:
            cfg.update(cor_texto=other["cor_texto"], cor_destaque=other.get("cor_destaque") or cfg.get("cor_texto"),
                       cor_contorno=cfg.get("cor_contorno") or other.get("cor_contorno"))
            cfg["karaoke"] = True
            break
    stroke = 0
    if cfg.get("cor_contorno"):
        stroke = 2 if (cfg.get("contorno_proporcao") or 0) > 0.35 else 1
    big = (cfg.get("altura_linha") or 0) > 0.055
    wpp = legendas.get("palavras_por_bloco_mediana")
    scored = []
    for name, t in TEMPLATES.items():
        s = 2.0 * _cdist(cfg.get("cor_texto"), t["fill"])
        hl = t.get("hlbg") or t.get("hl")
        if cfg.get("cor_destaque"):
            s += _cdist(cfg["cor_destaque"], hl) if hl else 1.0
        elif hl and _cdist(hl, t["fill"]) > 0.2:
            s += 0.35
        s += 0.4 * abs(stroke - t.get("stroke", 0))
        s += 0.5 * (bool(cfg.get("maiusculas")) != bool(t.get("upper")))
        s += 0.8 * (bool(cfg.get("fundo")) != bool(t.get("box")))
        s += 0.3 * (big != bool(t.get("big")))
        if wpp and t.get("wpp"):
            s += 0.1 * abs(wpp - t["wpp"])
        scored.append((round(s, 2), name))
    scored.sort()

    override = {}
    if cfg.get("cor_texto"):
        override["color"] = cfg["cor_texto"]
    if cfg.get("cor_destaque"):
        override["highlightColor"] = cfg["cor_destaque"]
    if cfg.get("cor_contorno"):
        override["strokeColor"] = cfg["cor_contorno"]
        override["strokeWidth"] = 8 if stroke == 2 else 2
    else:
        override["strokeWidth"] = 0
    if cfg.get("fundo"):
        override["background"] = cfg["fundo"]
        override["wholeLine"] = True
    override["textTransform"] = "uppercase" if cfg.get("maiusculas") else "none"
    paging = legendas.get("paginacao") or {}
    dist = paging.get("distribuicao_palavras_por_pagina") or {}
    if dist:
        # maior número de palavras que aparece com frequência (≥10%) — o limite real da página
        common = [int(k) for k in ("1", "2", "3") if dist.get(k, 0) >= 0.1] + ([4] if dist.get("4+", 0) >= 0.1 else [])
        override["wordsPerPage"] = max(common or [round(wpp or 3)])
    elif wpp:
        override["wordsPerPage"] = max(1, min(6, round(wpp)))
    if cfg.get("altura_linha"):
        # calibrado no OpenChatCut: Montserrat 900 + contorno 6, sizePx 72 → altura OCR 0,033 (1920 px)
        override["sizePx"] = int(round(cfg["altura_linha"] * 1920 * 1.14))
    anchor = cfg.get("posicao") if cfg.get("posicao") in ANCHORS else "bottom-center"
    if anchor in ("top", "bottom"):
        anchor += "-center"
    extra = {}
    if paging.get("fracao_uma_linha", 0) >= 0.7:
        extra["uma_linha"] = "layout_policy perSource maxLines 1"
    if paging.get("limite_caracteres_por_linha"):
        extra["paginar"] = f"occ paginar --max-chars {paging['limite_caracteres_por_linha']} "                            f"--max-palavras {override.get('wordsPerPage', 3)}"
    return {
        "templates_mais_proximos": [{"template": n, "distancia": s} for s, n in scored[:3]],
        **extra,
        "pacing": "word" if (wpp or 3) <= 1.5 else "phrase",
        "motionPreset": "verificar nas grades de entrada (none | fade-up | pop | word-pop | karaoke-pulse)",
        "styleOverride": override,
        "layout": {"anchor": anchor, "centro_y": cfg.get("centro_y")},
        "observacao": "sizePx calibrado para Montserrat 900 (fontes de CapCut são mais estreitas/altas). "
                      "Confirme fonte e animação nos recortes e valide com `ref comparar`.",
    }
