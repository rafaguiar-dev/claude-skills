"""Prepara a pasta: frases marcadas da copy + transcrição do vídeo + tempo de cada parágrafo + folha de prints.

Uso: python -I preparar.py "<pasta>" [--docx X] [--video Y] [--nome-antigo SlimJara --nome-novo "Melt Peak"]

Grava tudo em <pasta>/_copy-depoimentos/:
  transc.json      transcrição do Whisper (cache: não refaz se já existir)
  copia.tsv        cada parágrafo da copy com tempo no vídeo e as frases marcadas que ele tem
  frases.json      as frases marcadas com tempo (lido pelo montar.py)
  frases-N.jpg     um print no meio de cada frase marcada, numerado
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "copy-expert" / "scripts"))
from extrair import analisar, limpar  # noqa: E402

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def achar_arquivos(pasta, docx, video):
    pasta = Path(pasta).resolve()
    arqs = [p for p in pasta.iterdir() if p.is_file() and not p.name.startswith("~$")]
    docs = [pasta / docx] if docx else [p for p in arqs if p.suffix.lower() == ".docx" and "[depoimentos]" not in p.name]
    vids = [pasta / video] if video else [p for p in arqs if p.suffix.lower() in VIDEO_EXT]
    if len(docs) != 1 or len(vids) != 1:
        print("PRECISA ESCOLHER: passe --docx e/ou --video")
        print("  docx:", *[d.name for d in docs], sep="\n    ")
        print("  vídeos:", *[v.name for v in vids], sep="\n    ")
        sys.exit(2)
    return docs[0], vids[0]


def transcrever(video, saida):
    if saida.exists():
        print(f"Transcrição em cache: {saida}")
        return json.loads(saida.read_text(encoding="utf-8"))
    try:  # DLLs da CUDA instaladas pelo pip (nvidia-cublas-cu12, nvidia-cudnn-cu12)
        import nvidia.cublas, nvidia.cudnn
        for m in (nvidia.cublas, nvidia.cudnn):
            d = os.path.join(list(m.__path__)[0], "bin")
            os.add_dll_directory(d)
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
    except ImportError:
        pass
    from faster_whisper import WhisperModel, decode_audio
    modelo = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
    try:
        m = WhisperModel(modelo, device="cuda", compute_type="float16")
    except Exception as e:
        print(f"GPU indisponível ({e}); usando CPU (bem mais lento)")
        m = WhisperModel(modelo, device="cpu", compute_type="int8")
    wav = decode_audio(str(video), sampling_rate=16000)
    SR, CH = 16000, 600  # pedaços de 10 min: o áudio inteiro de uma vez estoura a RAM
    res, lang = [], None
    for off in range(0, len(wav), CH * SR):
        t0 = off / SR
        segs, info = m.transcribe(wav[off:off + CH * SR], language=lang, word_timestamps=True, vad_filter=True)
        lang = lang or info.language  # idioma detectado no 1º pedaço vale pro resto
        for s in segs:
            res.append({"start": s.start + t0, "end": s.end + t0, "text": s.text,
                        "words": [[w.start + t0, w.end + t0, w.word] for w in s.words]})
        print(f"  transcrito até {min(len(wav), off + CH * SR) / SR / 60:.0f} min", flush=True)
    saida.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return res


def norm(t):
    return re.sub(r"[^\wäöüßàáâãçéêíóôõú ]|_", " ", t.lower()).split()


def nomes_produto(paras, antigo, novo):
    if not (antigo and novo):
        for txt, _ in paras:
            m = re.search(r"produto\s*:\s*(.+?)\s*(?:→|->|=>)\s*(.+)", txt, re.I)
            if m:
                antigo, novo = antigo or m.group(1), novo or m.group(2)
                break
    return antigo, novo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta")
    ap.add_argument("--docx")
    ap.add_argument("--video")
    ap.add_argument("--nome-antigo")
    ap.add_argument("--nome-novo")
    a = ap.parse_args()
    docx, video = achar_arquivos(a.pasta, a.docx, a.video)
    trab = Path(a.pasta) / "_copy-depoimentos"
    trab.mkdir(exist_ok=True)
    print(f"Copy:  {docx.name}\nVídeo: {video.name}\n")

    paras, legenda, cores_troca, cores_marcador, inicio, frases, pistas = analisar(docx)
    antigo, novo = nomes_produto(paras, a.nome_antigo, a.nome_novo)
    print(f"{len(frases)} frases marcadas. Produto: {antigo} -> {novo} (ignorado na comparação)")
    if pistas:
        print("Pistas de troca escritas/marcadas na copy:")
        for n, i, t in pistas:
            print(f"  antes da frase {n + 1} (parágrafo {i}): {t[:100]}")

    segs = transcrever(video, trab / "transc.json")

    # o nome do produto é diferente na copy e no vídeo: tira os dois da comparação.
    # No vídeo o Whisper escreve o nome de vários jeitos ("Slim Jara", "Slimjarders"), então
    # corta toda palavra que começa como uma parte do nome antigo.
    # "SlimJara" vira "slim" + "jara", porque a copy/o Whisper escrevem separado
    partes = {p for n in (antigo, novo) if n for p in norm(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", n)) if len(p) >= 3}
    def eh_produto(t):
        return any(t == p or (len(p) >= 4 and t.startswith(p[:3])) for p in partes)

    W = [w for s in segs for w in s["words"]]
    toks, idx = [], []
    for i, w in enumerate(W):
        for t in norm(w[2]):
            if not eh_produto(t):
                toks.append(t)
                idx.append(i)

    marcadas = {}
    for n, (i, f) in enumerate(frases, 1):
        marcadas.setdefault(i, []).append(n)
    copia = [(i, limpar(t)) for i, (t, _) in enumerate(paras)
             if i >= inicio and t.strip() and "cor que sinaliza" not in t.lower()]

    def casar(texto, pos, janela):
        pt = [t for t in norm(texto) if not eh_produto(t)]
        n = len(pt)
        if not n:
            return 0, None, 0
        best = (0, None)
        fim = len(toks) - n + 1 if janela is None else min(len(toks) - n + 1, pos + janela)
        for st in range(pos, max(pos, fim)):
            sm = difflib.SequenceMatcher(None, pt, toks[st:st + n])
            if sm.real_quick_ratio() <= best[0] or sm.quick_ratio() <= best[0]:
                continue
            r = sm.ratio()
            if r > best[0]:
                best = (r, st)
            if best[0] > 0.9 and st > best[1] + 30:
                break
        return best[0], best[1], n

    # parágrafo por parágrafo, em ordem; a copy pode começar no meio do vídeo
    linhas, pos, achou = [], 0, False
    for i, t in copia:
        r, st, n = casar(t, pos, None if not achou else 2500)
        ok = st is not None and r >= 0.6
        ini = W[idx[st]][0] if ok else None
        fim = W[idx[min(st + n - 1, len(idx) - 1)]][1] if ok else None
        if ok:
            pos, achou = st + n, True
        linhas.append((i, ini, fim, r, t))

    # frases marcadas: casa de novo só a frase, dentro do trecho do parágrafo
    tempo_par = {i: (ini, fim) for i, ini, fim, _, _ in linhas}
    saida_frases = []
    for n, (i, f) in enumerate(frases, 1):
        ini_p, _ = tempo_par.get(i, (None, None))
        p0 = 0
        if ini_p is not None:
            p0 = next((k for k, j in enumerate(idx) if W[j][0] >= ini_p - 1), 0)
        r, st, m = casar(f, p0, 400 if ini_p is not None else None)
        ok = st is not None and r >= 0.6
        saida_frases.append({"n": n, "paragrafo": i, "texto": f, "ratio": round(r, 2),
                             "ini": W[idx[st]][0] if ok else None,
                             "fim": W[idx[min(st + m - 1, len(idx) - 1)]][1] if ok else None})

    (trab / "frases.json").write_text(json.dumps(
        {"docx": str(docx), "video": str(video), "frases": saida_frases}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    with open(trab / "copia.tsv", "w", encoding="utf-8") as f:
        f.write("paragrafo\tini\tfim\tsemelhanca\tfrases_marcadas\ttexto\n")
        for i, ini, fim, r, t in linhas:
            mm = ",".join(map(str, marcadas.get(i, [])))
            f.write(f"{i}\t{'' if ini is None else f'{ini:.1f}'}\t{'' if fim is None else f'{fim:.1f}'}"
                    f"\t{r:.2f}\t{mm}\t{t}\n")

    # folha de prints: um no meio de cada frase marcada
    achadas = [x for x in saida_frases if x["ini"] is not None]
    for k in range(0, len(achadas), 40):
        lote = achadas[k:k + 40]
        tmp = trab / "tmp"
        tmp.mkdir(exist_ok=True)
        for j, x in enumerate(lote):
            t = (x["ini"] + x["fim"]) / 2
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video),
                            "-frames:v", "1", "-vf",
                            f"scale=180:-1,drawtext=text='{x['n']:02d}':x=5:y=5:fontsize=28:fontcolor=yellow"
                            ":box=1:boxcolor=black", str(tmp / f"{j:02d}.jpg")], stderr=subprocess.DEVNULL)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(tmp / "%02d.jpg"),
                        "-vf", "tile=10x4", "-frames:v", "1", str(trab / f"frases-{k // 40 + 1}.jpg")],
                       stderr=subprocess.DEVNULL)
        for p in tmp.iterdir():
            p.unlink()
        tmp.rmdir()

    total, ach = len(saida_frases), len(achadas)
    par_ach = sum(1 for _, ini, _, _, _ in linhas if ini is not None)
    print(f"\nFrases marcadas achadas no vídeo: {ach}/{total}. Parágrafos da copy achados: {par_ach}/{len(linhas)}")
    if total and ach / total < 0.7:
        print("ATENÇÃO: o vídeo não bate com a copy (menos de 70% das frases). Confira se é o vídeo certo.")
    print("\nFRASES (n | parágrafo | tempo | semelhança | texto):")
    for x in saida_frases:
        tt = "  --  " if x["ini"] is None else f"{int(x['ini'] // 60):02d}:{x['ini'] % 60:04.1f}"
        print(f"  {x['n']:3} | {x['paragrafo']:4} | {tt} | {x['ratio']:.2f} | {x['texto'][:90]}")
    print(f"\nArquivos em {trab}")


if __name__ == "__main__":
    main()
