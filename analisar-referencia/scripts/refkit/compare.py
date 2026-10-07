"""Referência × edição: mede a distância entre as duas análises e sugere o ajuste de cada diferença.

Lê `dados/*.json` das duas pastas (rode `analisar` nas duas antes). As dicas de OpenChatCut assumem
que a edição foi feita com os parâmetros informados em `--legenda-size` (sizePx usado na edição)."""
from pathlib import Path

from .mapping import suggest_caption
from .util import fmt_t, r, read_json

NOT_EDIT = ("emenda na fonte (morph)",)


def _load(folder: Path) -> dict:
    out = {}
    for name in ("fonte", "fala", "cortes", "textos", "audio", "visual"):
        p = Path(folder) / "dados" / f"{name}.json"
        out[name] = read_json(p) if p.exists() else {}
    return out


def _row(label, a, b, ok, hint=""):
    mark = "✅" if ok else "⚠️"
    return f"| {label} | {a} | {b} | {mark} {hint} |"


def _close(a, b, rel=0.15, abs_=0.0):
    if a is None or b is None:
        return a == b
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b), 1e-9))


def _col_dist(a, b):
    if not a or not b:
        return 1.0
    ra = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    rb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return sum(abs(x - y) for x, y in zip(ra, rb)) / 765


def _special(cortes):
    return [t for t in cortes.get("transicoes", [])
            if t["tipo"] not in ("corte seco", "jump cut") + NOT_EDIT]


def compare(ref_folder: Path, edit_folder: Path, caption_size_px: float | None = None) -> str:
    A, B = _load(ref_folder), _load(edit_folder)
    L = [f"# Comparação: referência × edição", "",
         f"- Referência: `{Path(ref_folder).name}` ({A['fonte'].get('duracao')}s)",
         f"- Edição: `{Path(edit_folder).name}` ({B['fonte'].get('duracao')}s)", "",
         "| Item | Referência | Edição | Situação / ajuste |", "|---|---|---|---|"]

    # formato e fala
    fa, fb = A["fonte"], B["fonte"]
    L.append(_row("Formato", f"{fa.get('largura')}×{fa.get('altura')}", f"{fb.get('largura')}×{fb.get('altura')}",
                  fa.get("proporcao") == fb.get("proporcao")))
    sa, sb = A["fala"], B["fala"]
    if sa.get("tem_fala") and sb.get("tem_fala"):
        L.append(_row("Palavras/s", sa["palavras_por_segundo"], sb["palavras_por_segundo"],
                      _close(sa["palavras_por_segundo"], sb["palavras_por_segundo"], 0.12),
                      "" if _close(sa["palavras_por_segundo"], sb["palavras_por_segundo"], 0.12)
                      else "ritmo vem da locução (só muda com velocidade/cortes de pausas)"))
        L.append(_row("Maior pausa", f"{sa['maior_pausa']}s", f"{sb['maior_pausa']}s",
                      sb["maior_pausa"] <= sa["maior_pausa"] + 0.15,
                      "" if sb["maior_pausa"] <= sa["maior_pausa"] + 0.15 else "remover pausas acima da referência"))

    # cortes e transições
    ca, cb = A["cortes"].get("estatisticas", {}), B["cortes"].get("estatisticas", {})
    if ca and cb:
        L.append(_row("Cortes/min", ca["cortes_por_minuto"], cb["cortes_por_minuto"],
                      _close(ca["cortes_por_minuto"], cb["cortes_por_minuto"], 0.25, 1.0)))
        L.append(_row("Plano mediano", f"{ca['plano_mediano']}s", f"{cb['plano_mediano']}s",
                      _close(ca["plano_mediano"], cb["plano_mediano"], 0.3, 0.5)))
    ta, tb = _special(A["cortes"]), _special(B["cortes"])
    kinds_a = sorted({t["tipo"] for t in ta})
    kinds_b = sorted({t["tipo"] for t in tb})
    missing = [k for k in kinds_a if k not in kinds_b]
    L.append(_row("Transições especiais", ", ".join(f"{fmt_t(t['tempo'])} {t['tipo']}" for t in ta[:8]) or "—",
                  ", ".join(f"{fmt_t(t['tempo'])} {t['tipo']}" for t in tb[:8]) or "—", not missing,
                  ("faltando: " + ", ".join(
                      f"{k} → `{next(t['tipo_openchatcut'] for t in ta if t['tipo'] == k)}`" for k in missing))
                  if missing else ""))

    # layout
    va, vb = A["visual"], B["visual"]
    spa, spb = A["cortes"].get("tela_dividida") or [], B["cortes"].get("tela_dividida") or []
    fmt_sp = lambda sp: "; ".join(f"{fmt_t(s['inicio'])}–{fmt_t(s['fim'])} linha {s['linha_divisoria']}" for s in sp) or "—"
    L.append(_row("Tela dividida", fmt_sp(spa), fmt_sp(spb),
                  len(spa) == len(spb) and all(_close(x["linha_divisoria"], y["linha_divisoria"], 0, 0.02)
                                               for x, y in zip(spa, spb))))

    # legendas
    la, lb = A["textos"].get("legendas") or {}, B["textos"].get("legendas") or {}
    hints = []
    if la.get("tem_legenda") and lb.get("tem_legenda"):
        pa, pb = la.get("paginacao") or {}, lb.get("paginacao") or {}
        if pa and pb:
            L.append(_row("Legenda: 1 linha", f"{int(pa['fracao_uma_linha'] * 100)}%", f"{int(pb['fracao_uma_linha'] * 100)}%",
                          _close(pa["fracao_uma_linha"], pb["fracao_uma_linha"], 0, 0.07),
                          "" if _close(pa["fracao_uma_linha"], pb["fracao_uma_linha"], 0, 0.07) else
                          "ajustar maxLines/maxCharsPerLine por fonte (layout_policy perSource)"))
            L.append(_row("Palavras por página (1/2/3/4+)",
                          "/".join(str(int(pa['distribuicao_palavras_por_pagina'][k] * 100)) for k in ("1", "2", "3", "4+")),
                          "/".join(str(int(pb['distribuicao_palavras_por_pagina'][k] * 100)) for k in ("1", "2", "3", "4+")),
                          abs(pa["distribuicao_palavras_por_pagina"]["1"] - pb["distribuicao_palavras_por_pagina"]["1"]) < 0.12))
            L.append(_row("Caracteres/linha (mediana, p90)",
                          f"{pa['caracteres_por_linha_mediana']}, {pa['caracteres_por_linha_p90']}",
                          f"{pb['caracteres_por_linha_mediana']}, {pb['caracteres_por_linha_p90']}",
                          _close(pa["caracteres_por_linha_p90"], pb["caracteres_por_linha_p90"], 0.15),
                          f"limite da referência ≈ {pa.get('limite_caracteres_por_linha')} caracteres"
                          if pa.get("limite_caracteres_por_linha") else ""))
        c0a = (la.get("configuracoes") or [{}])[0]
        c0b = (lb.get("configuracoes") or [{}])[0]
        ha, hb = c0a.get("altura_linha"), c0b.get("altura_linha")
        size_hint = ""
        if ha and hb and not _close(ha, hb, 0.08):
            if caption_size_px:
                size_hint = f"sizePx {caption_size_px:g} → **{round(caption_size_px * ha / hb)}**"
            else:
                size_hint = f"escalar a fonte × {r(ha / hb, 2)}"
        L.append(_row("Altura da letra (fração da tela)", ha, hb, _close(ha, hb, 0.08), size_hint))
        wa = (la.get("paginacao") or {}).get("largura_linha_mediana")
        wb = (lb.get("paginacao") or {}).get("largura_linha_mediana")
        if wa and wb:
            L.append(_row("Largura da linha (mediana)", wa, wb, _close(wa, wb, 0.12)))
        # posições por faixa: compara cada estilo da referência com o da edição na mesma faixa vertical
        for cfg in (la.get("configuracoes") or [])[:3]:
            twin = min(lb.get("configuracoes") or [{}], key=lambda c: abs((c.get("centro_y") or 9) - cfg["centro_y"]))
            y_ok = twin.get("centro_y") is not None and abs(twin["centro_y"] - cfg["centro_y"]) < 0.025
            L.append(_row(f"Posição y ({cfg['posicao']})", cfg["centro_y"], twin.get("centro_y", "—"), y_ok,
                          "" if y_ok or twin.get("centro_y") is None else
                          f"mover {r(cfg['centro_y'] - twin['centro_y'], 3):+} da altura (offsetYRatio)"))
        # cores do estilo principal já com o karaokê resolvido (texto + palavra ativa)
        sa_, sb_ = suggest_caption(la).get("styleOverride", {}), suggest_caption(lb).get("styleOverride", {})
        for key, label in (("color", "Cor do texto"), ("strokeColor", "Contorno"), ("highlightColor", "Destaque")):
            a_, b_ = sa_.get(key), sb_.get(key)
            if a_ or b_:
                L.append(_row(label, a_ or "—", b_ or "—", _col_dist(a_, b_) < 0.12,
                              "" if _col_dist(a_, b_) < 0.12 or a_ else "OCR pode perder contorno fino: confira no recorte"))
        L.append(_row("Caixa alta", c0a.get("maiusculas"), c0b.get("maiusculas"),
                      c0a.get("maiusculas") == c0b.get("maiusculas")))
    elif la.get("tem_legenda") != lb.get("tem_legenda"):
        L.append(_row("Legenda", la.get("tem_legenda"), lb.get("tem_legenda"), False))

    # áudio
    ma, mb = (A["audio"].get("musica") or {}), (B["audio"].get("musica") or {})
    if A["audio"] and B["audio"]:
        L.append(_row("Música", f"{ma.get('presente')} ~{ma.get('bpm')} BPM" if ma.get("presente") else "não",
                      f"{mb.get('presente')} ~{mb.get('bpm')} BPM" if mb.get("presente") else "não",
                      bool(ma.get("presente")) == bool(mb.get("presente"))))
        sa_, sb_ = A["audio"].get("som_nas_transicoes") or [], B["audio"].get("som_nas_transicoes") or []
        L.append(_row("Som nas transições", len(sa_), len(sb_), len(sa_) <= len(sb_),
                      "" if len(sa_) <= len(sb_) else "faltam SFX (whoosh/impacto) nas transições"))

    # cor
    ka, kb = va.get("cor") or {}, vb.get("cor") or {}
    if ka and kb:
        L.append(_row("Look", ka["descricao"], kb["descricao"], ka["descricao"] == kb["descricao"],
                      "diferença de cor vem do material; ajustar só se o perfil pedir LUT"))
    L += ["", "_Métricas automáticas: confirme as diferenças nas grades (`ref grade`) antes de ajustar._"]
    return "\n".join(L) + "\n"
