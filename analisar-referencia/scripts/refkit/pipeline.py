"""Orquestra a análise: pasta da referência, etapas com cache, evidências e resumo."""
import re
import shutil
import sys
import traceback
import unicodedata
from datetime import datetime
from pathlib import Path

from PIL import Image

from . import audio, cuts, mapping, ocr, transcribe, visual
from .grids import every_frame_cells, load_words, sample_cells, save_pages
from .media import VIDEO_EXTS, cut_clip, decode, extract_audio, probe
from .util import Timer, fmt_t, log, r, read_json, run, write_json

STAGES = ["fala", "cortes", "textos", "audio", "visual", "evidencias"]


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()[:60] or "referencia"


def find_source(folder: Path) -> Path:
    for p in sorted(folder.glob("source.*")):
        if p.suffix.lower() in VIDEO_EXTS:
            return p
    raise FileNotFoundError(f"nenhum source.* de vídeo em {folder}")


def prepare(source: str, name: str | None, root: Path, replace=False) -> Path:
    is_url = re.match(r"^https?://", source) is not None
    if not name:
        name = "referencia-" + datetime.now().strftime("%Y%m%d-%H%M") if is_url else Path(source).stem
    folder = root / slugify(name)
    if folder.exists() and any(folder.iterdir()):
        if not replace:
            raise FileExistsError(f"{folder} já existe; use outro --nome ou --substituir (apaga a análise anterior)")
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)
    meta = {"origem": source, "preparado_em": datetime.now().isoformat(timespec="seconds")}
    if is_url:
        log(f"baixando {source}")
        run([sys.executable, "-m", "yt_dlp", "--no-playlist", "-f",
             "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b", "--merge-output-format", "mp4",
             "--write-info-json", "-o", str(folder / "source.%(ext)s"), source])
        info_json = folder / "source.info.json"
        if info_json.exists():
            info = read_json(info_json)
            meta.update(titulo=info.get("title"), autor=info.get("uploader"), plataforma=info.get("extractor_key"))
            info_json.unlink()
    else:
        src = Path(source)
        if not src.exists():
            raise FileNotFoundError(source)
        shutil.copy2(src, folder / f"source{src.suffix.lower()}")
    src = find_source(folder)
    meta.update(arquivo=src.name, **probe(src))
    write_json(folder / "dados" / "fonte.json", meta)
    return folder


def _stage(folder: Path, name: str, redo: set, fn):
    path = folder / "dados" / f"{name}.json"
    if path.exists() and name not in redo and "tudo" not in redo:
        return read_json(path)
    with Timer(name):
        data = fn()
    write_json(path, data)
    return data


def analyze(folder: Path, language=None, model=None, device="auto", skip=(), redo=(), ocr_fps=4.0,
            shazam=True) -> dict:
    folder = Path(folder)
    skip, redo = set(skip), set(redo)
    src = find_source(folder)
    fonte_path = folder / "dados" / "fonte.json"
    fonte = read_json(fonte_path) if fonte_path.exists() else {"arquivo": src.name}
    info = probe(src)
    fonte.update(info)
    write_json(fonte_path, fonte)
    errors, result = {}, {"versao": 1, "fonte": fonte}
    audio_dir = folder / "audio"
    duration = info["duracao"]

    def guarded(name, fn):
        if name in skip:
            return None
        try:
            return fn()
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"
            log(f"ERRO em {name}: {exc}")
            traceback.print_exc(file=sys.stderr)
            return None

    transcript_path = folder / "transcript.json"

    def do_fala():
        if not info["tem_audio"]:
            return {"tem_fala": False, "motivo": "vídeo sem áudio"}
        wav16 = audio_dir / "audio_16k.wav"
        if not wav16.exists():
            extract_audio(src, wav16, 16000, 1)
        if not transcript_path.exists() or "fala" in redo or "tudo" in redo:
            transcribe.transcribe(wav16, transcript_path, language, model, device)
        return transcribe.speech_stats(read_json(transcript_path), duration)

    result["fala"] = guarded("fala", lambda: _stage(folder, "fala", redo, do_fala))
    words = load_words(transcript_path) if transcript_path.exists() else []

    def do_cortes():
        det = cuts.detect(src, info)
        # tela dividida precisa dos cortes parciais; um corte "parcial" fora de tela dividida é corte comum
        det["tela_dividida"] = visual.split_screen(src, info, det["transicoes"])
        for t in det["transicoes"]:
            if t["tipo"].startswith("troca de insert") and not any(
                    sp["inicio"] - 0.05 <= t["tempo"] < sp["fim"] - 0.05 for sp in det["tela_dividida"]):
                t["tipo"] = "corte seco"
                for k in ("so_muda", "linha_divisoria", "eixo"):
                    t["detalhes"].pop(k, None)
        return det

    result["cortes"] = guarded("cortes", lambda: _stage(folder, "cortes", redo, do_cortes))
    transitions = (result["cortes"] or {}).get("transicoes", [])
    shots = (result["cortes"] or {}).get("planos") or [{"n": 1, "inicio": 0.0, "fim": duration, "duracao": duration}]

    def do_textos():
        data = ocr.read_text(src, info, words, fps=ocr_fps)
        data["sugestao_openchatcut"] = mapping.suggest_caption(data.get("legendas", {}))
        return data

    result["textos"] = guarded("textos", lambda: _stage(folder, "textos", redo, do_textos))

    def do_audio():
        if not info["tem_audio"]:
            return {"musica": {"presente": False}, "motivo": "vídeo sem áudio"}
        wav44 = audio_dir / "audio_44k.wav"
        if not wav44.exists():
            extract_audio(src, wav44, 44100, 2)
        with Timer("separando voz e música (Demucs)"):
            stems = audio.separate(wav44, audio_dir / "stems")
        return audio.analyze(stems["voz"], stems["resto"], transitions, duration, audio_dir, use_shazam=shazam)

    result["audio"] = guarded("audio", lambda: _stage(folder, "audio", redo, do_audio))

    def do_visual():
        return {"cor": visual.look(src, info), "rostos": visual.faces(src, info),
                "movimento_por_plano": visual.movement(src, info, shots)}

    result["visual"] = guarded("visual", lambda: _stage(folder, "visual", redo, do_visual))

    if "evidencias" not in skip:
        with Timer("evidências"):
            result["evidencias"] = guarded("evidencias", lambda: make_evidence(folder, src, info, words, result))

    result["erros"] = errors
    result["gerado_em"] = datetime.now().isoformat(timespec="seconds")
    write_json(folder / "analise.json", result)
    summary = render_summary(result)
    (folder / "resumo.md").write_text(summary, encoding="utf-8")
    return result


# ---------------------------------------------------------------- evidências

def _rel(folder: Path, paths) -> list:
    return [str(Path(p).relative_to(folder)).replace("\\", "/") for p in paths]


def _expand(box, sx=0.15, sy=1.2):
    x, y, w, h = box
    x0, y0 = max(0.0, x - sx * w - 0.02), max(0.0, y - sy * h)
    x1, y1 = min(1.0, x + w + sx * w + 0.02), min(1.0, y + h + sy * h)
    return [round(x0, 4), round(y0, 4), round(x1 - x0, 4), round(y1 - y0, 4)]


def make_evidence(folder: Path, src: Path, info: dict, words: list, result: dict) -> dict:
    ev_dir = folder / "evidencias"
    if ev_dir.exists():
        shutil.rmtree(ev_dir)
    duration, fps = info["duracao"], info.get("fps") or 30.0
    out = {}
    every = 1.0 if duration <= 90 else 2.0
    times = [round(t * every, 2) for t in range(int(duration / every) + 1) if t * every < duration - 0.05]
    out["visao_geral"] = _rel(folder, save_pages(sample_cells(src, info, times, words, cell_w=300),
                                                ev_dir / "00_visao_geral.jpg", columns=6, rows=4,
                                                cell_w=300, title=f"Visão geral — 1 frame a cada {every:g}s"))

    cortes = result.get("cortes") or {}
    shots = cortes.get("planos") or []
    if shots:
        mids = [round((s["inicio"] + s["fim"]) / 2, 2) for s in shots]
        labels = [f"plano {s['n']} ({s['duracao']:.2f}s)" for s in shots]
        out["planos"] = _rel(folder, save_pages(sample_cells(src, info, mids, words, cell_w=300, labels=labels),
                                               ev_dir / "01_planos.jpg", columns=6, rows=4, cell_w=300,
                                               title="Um frame do meio de cada plano"))

    transitions = cortes.get("transicoes") or []
    rows = []
    for n, tr in enumerate(transitions[:48], 1):
        start = max(0.0, tr["inicio"] - 2 / fps)
        end = min(duration, tr["fim"] + 4 / fps)
        frames, ftimes = decode(src, info, width=240, start=start, duration=max(end - start, 2 / fps))
        if not len(frames):
            continue
        pick = [round(i * (len(frames) - 1) / 5) for i in range(6)] if len(frames) > 6 else list(range(len(frames)))
        for j, i in enumerate(pick):
            label = f"T{n} {tr['tipo']}" if j == 0 else ""
            rows.append({"img": Image.fromarray(frames[i]), "t": ftimes[i], "label": label,
                         "words_active": [], "words_context": []})
        rows.extend({"img": Image.new("RGB", (240, 2)), "t": ftimes[-1], "label": "", "words_active": [],
                     "words_context": []} for _ in range(6 - len(pick)))
    if rows:
        out["transicoes"] = _rel(folder, save_pages(rows, ev_dir / "02_transicoes.jpg", columns=6, rows=4,
                                                   cell_w=240, title="Transições (cada linha = uma transição)"))

    textos = result.get("textos") or {}
    leg = textos.get("legendas") or {}
    out["legendas"] = []
    for n, cfg in enumerate(leg.get("configuracoes", [])[:4], 1):
        t = cfg["exemplo_tempo"]
        region = _expand(cfg["caixa_exemplo"])
        still = sample_cells(src, info, [min(duration - 0.05, t + 0.2)], words, cell_w=900, crop=region)
        paths = save_pages(still, ev_dir / "legendas" / f"estilo_{n}.jpg", columns=1, rows=1, cell_w=900,
                           title=f"Estilo de legenda {n}: {cfg['ocorrencias']} ocorrências")
        entry = every_frame_cells(src, info, max(0.0, t - 0.15), min(duration, t + 0.5), words, cell_w=360,
                                  crop=region)
        paths += save_pages(entry, ev_dir / "legendas" / f"entrada_{n}.jpg", columns=4, rows=5, cell_w=360,
                            title=f"Entrada da legenda (estilo {n}), todos os frames")
        out["legendas"] += _rel(folder, paths)

    on_screen = [e for e in textos.get("eventos", []) if e["tipo"] == "texto_na_tela"][:16]
    if on_screen:
        mids = [round((e["inicio"] + e["fim"]) / 2, 2) for e in on_screen]
        labels = [e["texto"][:40] for e in on_screen]
        out["textos_na_tela"] = _rel(folder, save_pages(sample_cells(src, info, mids, None, cell_w=300, labels=labels),
                                                       ev_dir / "03_textos_na_tela.jpg", columns=4, rows=4,
                                                       cell_w=300, title="Textos na tela (não são legenda da fala)"))
    return out


# ---------------------------------------------------------------- resumo

def render_summary(a: dict) -> str:
    f = a.get("fonte", {})
    L = [f"# Resumo automático — {f.get('titulo') or f.get('arquivo')}", ""]
    L.append(f"- **Formato:** {f.get('largura')}×{f.get('altura')} ({f.get('proporcao')}), {f.get('fps')} fps, "
             f"{f.get('duracao')}s")
    fala = a.get("fala") or {}
    if fala.get("tem_fala"):
        L += ["", "## Fala",
              f"- {fala['palavras']} palavras, {fala['palavras_por_segundo']} palavras/s; fala começa em "
              f"{fala['inicio_fala']}s; {fala['pausas_acima_350ms']} pausas > 350ms (maior {fala['maior_pausa']}s)",
              f"- **Gancho (0–3s):** “{fala.get('gancho_3s', '')}”"]
    c = a.get("cortes") or {}
    st = c.get("estatisticas") or {}
    if st:
        L += ["", "## Cortes e ritmo",
              f"- {st['planos']} planos, {st['cortes_por_minuto']} cortes/min, plano médio {st['plano_medio']}s "
              f"(mediana {st['plano_mediano']}s, de {st['plano_mais_curto']}s a {st['plano_mais_longo']}s)",
              f"- Cortes nos 3s iniciais: {st['cortes_nos_3s_iniciais']}",
              "- Por tipo: " + ", ".join(f"{k}: {v}" for k, v in st.get("por_tipo", {}).items()),
              "- Ritmo por quarto: " + " | ".join(f"{q['trecho']}: {q['cortes']} cortes" for q in st.get("ritmo_por_quarto", []))]
        not_edit = ("emenda na fonte (morph)", "troca de insert (tela dividida)")
        special = [t for t in c.get("transicoes", []) if t["tipo"] not in ("corte seco", "jump cut") + not_edit]
        if special:
            L.append("- Transições não-secas: " + "; ".join(
                f"{fmt_t(t['tempo'])} {t['tipo']}"
                + (f" ({t['detalhes'].get('escala')}x)" if t['detalhes'].get('escala') else "")
                + (f" {round(t['duracao'] * (f.get('fps') or 30))}f" if t.get("duracao") else "")
                + (f" → `{t['tipo_openchatcut']}`" if t.get("tipo_openchatcut") else "")
                for t in special[:20]))
        morphs = [t for t in c.get("transicoes", []) if t["tipo"] == "emenda na fonte (morph)"]
        if morphs:
            L.append(f"- Emendas do próprio material (morph, não recriar): {len(morphs)} — "
                     + ", ".join(fmt_t(t["tempo"]) for t in morphs[:10]))
    tx = a.get("textos") or {}
    leg = tx.get("legendas") or {}
    if leg.get("tem_legenda"):
        L += ["", "## Legendas",
              f"- Modo: **{leg['modo']}** (mediana {leg['palavras_por_bloco_mediana']} palavras/bloco, "
              f"{leg['duracao_bloco_mediana']}s por bloco, {leg['linhas_por_bloco']} linha(s))"
              + (" — revelação progressiva" if leg.get("revelacao_progressiva") else "")]
        for i, cfg in enumerate(leg.get("configuracoes", [])[:3], 1):
            L.append(f"- Estilo {i} ({cfg['ocorrencias']}x): posição {cfg['posicao']} (y={cfg['centro_y']}), "
                     f"texto {cfg.get('cor_texto')}, contorno {cfg.get('cor_contorno') or '—'}, "
                     f"fundo {cfg.get('fundo') or '—'}, destaque {cfg.get('cor_destaque') or '—'}, "
                     f"{'CAIXA ALTA' if cfg.get('maiusculas') else 'caixa normal'}, altura da linha {cfg['altura_linha']}")
        sug = tx.get("sugestao_openchatcut") or {}
        if sug:
            L.append("- OpenChatCut: templates mais próximos " + ", ".join(
                f"`{t['template']}`" for t in sug["templates_mais_proximos"]) + f"; pacing `{sug['pacing']}`")
    elif tx:
        L += ["", "## Legendas", "- Nenhuma legenda sincronizada com a fala detectada."]
    if tx.get("resumo_textos_na_tela"):
        L.append("- Textos de tela: " + "; ".join(f"{fmt_t(e['inicio'])} “{e['texto']}”"
                                                 for e in tx["resumo_textos_na_tela"][:12]))
    au = a.get("audio") or {}
    mus = au.get("musica") or {}
    if au:
        L += ["", "## Áudio"]
        if mus.get("presente"):
            L.append(f"- Música em {int(mus['cobertura'] * 100)}% do vídeo, ~{mus.get('bpm')} BPM"
                     + (f"; cortes na batida: {int(mus['cortes_na_batida'] * 100)}% (acaso ≈ {int(mus['acaso_esperado'] * 100)}%)"
                        + (" → **editado na batida**" if mus.get("sincronizado") else "")
                        if "cortes_na_batida" in mus else ""))
            ids = mus.get("identificacao") or []
            L.append("- Música identificada: " + ("; ".join(f"{m['titulo']} — {m['artista']}" for m in ids)
                                                  if ids else "não identificada"))
        else:
            L.append("- Sem música de fundo relevante.")
        if au.get("mixagem"):
            mx = au["mixagem"]
            L.append(f"- Mixagem: música ~{mx.get('musica_abaixo_da_voz_db')} dB abaixo da voz"
                     + (f"; ducking ~{mx['ducking_db']} dB" if "ducking_db" in mx else ""))
        if au.get("som_nas_transicoes"):
            L.append("- Som nas transições: " + "; ".join(f"{fmt_t(s['tempo'])} {s['som']}"
                                                         for s in au["som_nas_transicoes"][:12]))
        sfx = au.get("sfx_candidatos") or []
        if sfx:
            near = [s for s in sfx if s["perto_de_corte"]]
            L.append(f"- SFX candidatos: {len(sfx)} ({len(near)} colados em cortes), ex.: " +
                     "; ".join(f"{fmt_t(s['tempo'])} {s['tipo']}" for s in (near or sfx)[:6]))
    vi = a.get("visual") or {}
    if vi:
        L += ["", "## Visual"]
        for sp in (a.get("cortes") or {}).get("tela_dividida") or []:
            L.append(f"- **Tela dividida** {fmt_t(sp['inicio'])}–{fmt_t(sp['fim'])}: {sp['eixo']}, divisória em "
                     f"{sp['linha_divisoria']}, insert {sp['lado_do_insert']}; trocas de insert em "
                     + (", ".join(fmt_t(t) for t in sp["trocas_de_insert"]) or "—"))
        if vi.get("cor"):
            L.append(f"- Look: {vi['cor']['descricao']}; paleta " + " ".join(p["cor"] for p in vi["cor"]["paleta"][:5]))
        if vi.get("rostos"):
            ro = vi["rostos"]
            L.append(f"- {ro.get('formato_provavel')}; rosto em {int(ro['tempo_com_rosto'] * 100)}% do tempo"
                     + (f", {ro['enquadramento']}" if ro.get("enquadramento") else ""))
        moves = [m for m in vi.get("movimento_por_plano", []) if m["movimento"] not in ("estático", "curto demais")]
        if moves:
            L.append("- Movimento: " + "; ".join(f"plano {m['plano']}: {m['movimento']}" for m in moves[:12]))
    ev = a.get("evidencias") or {}
    if ev:
        L += ["", "## Evidências para olhar"]
        for key, paths in ev.items():
            if paths:
                L.append(f"- {key}: " + ", ".join(paths))
    if a.get("erros"):
        L += ["", "## Etapas com erro"] + [f"- {k}: {v}" for k, v in a["erros"].items()]
    L += ["", "_Rótulos automáticos são candidatos: confirme nas evidências antes de escrever o perfil._"]
    return "\n".join(L) + "\n"
