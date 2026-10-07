"""Linha de comando da skill /analisar-referencia.

  ref preparar <link|arquivo> [--nome N] [--raiz referencias] [--substituir]
  ref analisar <pasta> [--idioma pt] [--modelo M] [--dispositivo auto|cuda|cpu]
               [--pular etapa,...] [--refazer etapa,...|tudo] [--ocr-fps 4] [--sem-shazam]
  ref resumo   <pasta>
  ref grade    <pasta|vídeo> (--inicio S --fim S | --em T,T,... | --perto "frase" [--ocorrencia N] [--margem S])
               [--cada S | --quadros N | --todos-frames] [--recorte x,y,w,h] [--celula PX] [--colunas N]
               [--linhas N] [--transcricao arquivo] --para arquivo.jpg|pasta
  ref frames   <pasta|vídeo> (--em T,T,... | --inicio S --fim S --cada S) [--celula PX] --para pasta
  ref recorte  <pasta|vídeo> --inicio S --fim S [--rotular-tempo] --para clipe.mp4|audio.wav
  ref sondar   <vídeo>

Etapas: fala, cortes, textos, audio, visual, evidencias."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _video_and_transcript(target: str, transcript: str | None):
    from refkit.pipeline import find_source
    p = Path(target)
    if p.is_dir():
        src = find_source(p)
        tr = Path(transcript) if transcript else (p / "transcript.json")
        return src, (tr if tr.exists() else None), p
    return p, (Path(transcript) if transcript else None), p.parent


def _floats(text):
    return [float(x) for x in text.split(",") if x.strip()]


def cmd_grade(a):
    from refkit.grids import every_frame_cells, load_words, phrase_ranges, sample_cells, save_pages
    from refkit.media import probe
    src, tr, _ = _video_and_transcript(a.alvo, a.transcricao)
    info = probe(src)
    words = load_words(tr) if tr else []
    crop = _floats(a.recorte) if a.recorte else None
    if a.perto:
        if not words:
            sys.exit("--perto precisa de transcript.json")
        matches = phrase_ranges(words, a.perto)
        if not matches:
            sys.exit(f"frase não encontrada: {a.perto!r}")
        if len(matches) > 1 and not a.ocorrencia:
            listing = ", ".join(f"{i + 1}: {s:.2f}-{e:.2f}s" for i, (s, e) in enumerate(matches))
            sys.exit(f"a frase aparece {len(matches)} vezes ({listing}); use --ocorrencia N")
        s, e = matches[(a.ocorrencia or 1) - 1]
        start, end = max(0.0, s - a.margem), min(info["duracao"], e + a.margem)
    else:
        start, end = a.inicio, a.fim
    if a.em:
        cells = sample_cells(src, info, _floats(a.em), words, a.celula, crop)
    elif a.todos_frames:
        if start is None or end is None:
            sys.exit("--todos-frames precisa de --inicio/--fim ou --perto")
        cells = every_frame_cells(src, info, start, end, words, a.celula, crop)
    else:
        start = 0.0 if start is None else start
        end = info["duracao"] if end is None else end
        if a.quadros:
            step = (end - start) / a.quadros
            times = [round(start + step * (i + 0.5), 3) for i in range(a.quadros)]
        else:
            every = a.cada or 1.0
            n = int((end - start) / every + 1e-9)
            times = [round(start + i * every, 3) for i in range(n + 1) if start + i * every < end]
        cells = sample_cells(src, info, times, words, a.celula, crop)
    paths = save_pages(cells, a.para, a.colunas, a.linhas, a.celula)
    print("\n".join(str(p) for p in paths))


def cmd_frames(a):
    from refkit.media import frame_at, probe
    src, _, _ = _video_and_transcript(a.alvo, None)
    info = probe(src)
    if a.em:
        times = _floats(a.em)
    else:
        times, t = [], a.inicio or 0.0
        while t < (a.fim or info["duracao"]):
            times.append(round(t, 3))
            t += a.cada or 1.0
    out = Path(a.para)
    out.mkdir(parents=True, exist_ok=True)
    for t in times:
        path = out / f"t{t:08.3f}s.jpg"
        frame_at(src, t, info, width=a.celula or info["largura"]).save(path, quality=92)
        print(path)


def main():
    ap = argparse.ArgumentParser(prog="ref", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("preparar")
    p.add_argument("fonte")
    p.add_argument("--nome")
    p.add_argument("--raiz", default="referencias")
    p.add_argument("--substituir", action="store_true")

    p = sub.add_parser("analisar")
    p.add_argument("pasta")
    p.add_argument("--idioma")
    p.add_argument("--modelo")
    p.add_argument("--dispositivo", default="auto", choices=["auto", "cuda", "cpu"])
    p.add_argument("--pular", default="")
    p.add_argument("--refazer", default="")
    p.add_argument("--ocr-fps", type=float, default=4.0)
    p.add_argument("--sem-shazam", action="store_true")

    p = sub.add_parser("resumo")
    p.add_argument("pasta")

    p = sub.add_parser("grade")
    p.add_argument("alvo")
    p.add_argument("--inicio", type=float)
    p.add_argument("--fim", type=float)
    p.add_argument("--em")
    p.add_argument("--perto")
    p.add_argument("--ocorrencia", type=int)
    p.add_argument("--margem", type=float, default=0.3)
    p.add_argument("--cada", type=float)
    p.add_argument("--quadros", type=int)
    p.add_argument("--todos-frames", action="store_true")
    p.add_argument("--recorte")
    p.add_argument("--celula", type=int, default=360)
    p.add_argument("--colunas", type=int, default=4)
    p.add_argument("--linhas", type=int, default=3)
    p.add_argument("--transcricao")
    p.add_argument("--para", required=True)

    p = sub.add_parser("frames")
    p.add_argument("alvo")
    p.add_argument("--em")
    p.add_argument("--inicio", type=float)
    p.add_argument("--fim", type=float)
    p.add_argument("--cada", type=float)
    p.add_argument("--celula", type=int)
    p.add_argument("--para", required=True)

    p = sub.add_parser("recorte")
    p.add_argument("alvo")
    p.add_argument("--inicio", type=float, required=True)
    p.add_argument("--fim", type=float, required=True)
    p.add_argument("--rotular-tempo", action="store_true")
    p.add_argument("--para", required=True)

    p = sub.add_parser("comparar")
    p.add_argument("referencia")
    p.add_argument("edicao")
    p.add_argument("--legenda-size", type=float, help="sizePx usado na legenda da edição (para sugerir o novo)")

    p = sub.add_parser("sondar")
    p.add_argument("video")

    p = sub.add_parser("_transcrever")  # interno (subprocesso da transcrição)
    p.add_argument("audio")
    p.add_argument("saida")
    p.add_argument("dispositivo")
    p.add_argument("modelo")
    p.add_argument("idioma", nargs="?", default="")

    a = ap.parse_args()
    if a.cmd == "_transcrever":
        from refkit.transcribe import worker
        worker(a.audio, a.saida, a.dispositivo, a.modelo, a.idioma or None)
    elif a.cmd == "preparar":
        from refkit.pipeline import prepare
        folder = prepare(a.fonte, a.nome, Path(a.raiz), a.substituir)
        print(folder.resolve())
    elif a.cmd == "analisar":
        from refkit.pipeline import analyze
        split = lambda s: [x.strip() for x in s.split(",") if x.strip()]
        analyze(Path(a.pasta), a.idioma, a.modelo, a.dispositivo, split(a.pular), split(a.refazer), a.ocr_fps,
                not a.sem_shazam)
        print((Path(a.pasta) / "resumo.md").read_text(encoding="utf-8"))
    elif a.cmd == "resumo":
        from refkit.pipeline import render_summary
        from refkit.util import read_json
        print(render_summary(read_json(Path(a.pasta) / "analise.json")))
    elif a.cmd == "comparar":
        from refkit.compare import compare
        text = compare(Path(a.referencia), Path(a.edicao), a.legenda_size)
        (Path(a.edicao) / "comparacao.md").write_text(text, encoding="utf-8")
        print(text)
    elif a.cmd == "grade":
        cmd_grade(a)
    elif a.cmd == "frames":
        cmd_frames(a)
    elif a.cmd == "recorte":
        from refkit.media import cut_clip
        src, _, _ = _video_and_transcript(a.alvo, None)
        print(cut_clip(src, a.para, a.inicio, a.fim, a.rotular_tempo))
    elif a.cmd == "sondar":
        import json
        from refkit.media import probe
        print(json.dumps(probe(a.video), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
