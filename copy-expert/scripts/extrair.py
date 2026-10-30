"""Extrai as frases marcadas de uma copy (.docx) e devolve com [expert] entre elas.

Uso: python -I extrair.py "copy.docx" [--saida arquivo.txt]

Lê a legenda de cores do próprio documento ("Cor que sinaliza ..."):
- cor de troca de avatar/personagem -> pista de troca de quem fala (não vira frase);
- cor de pitch / bloco de oferta / minuto -> marcador de edição (ignorado);
- as outras cores -> adaptação da copy (a frase entra).

Escreve o rascunho (tudo como [expert]) no .txt e imprime no terminal um relatório com
as pistas de troca de personagem entre as frases, pra trocar a etiqueta à mão.
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SEM_COR = {None, "auto", "ffffff", "none"}
TROCA = re.compile(r"avatar|personagem|locutor|narrador|quem fala", re.I)
MARCADOR = re.compile(r"pitch|bloco de oferta|minuto|tempo", re.I)
# rótulos de fala escritos na copy: "Dr. Anne Fleck:", "[Depoimento 2]", "AVATAR 2", "Personagem: Helene"
ROTULO = re.compile(
    r"^\s*(\[[^\]]{1,40}\]|\(?\s*(avatar|personagem|depoimento|locutor|narrador|expert|especialista)\b[^.!?]{0,40}\)?"
    r"|[A-ZÄÖÜÀ-Ý][\wÀ-ÿ.\- ]{1,35}:\s*$)",
    re.I,
)


def cor_do_run(r):
    rpr = r.find(W + "rPr")
    if rpr is None:
        return None
    h = rpr.find(W + "highlight")
    if h is not None and h.get(W + "val") not in SEM_COR:
        return "hl:" + h.get(W + "val").lower()
    s = rpr.find(W + "shd")
    if s is not None and (s.get(W + "fill") or "").lower() not in SEM_COR:
        return "shd:" + s.get(W + "fill").lower()
    return None


def ler(docx):
    root = ET.fromstring(zipfile.ZipFile(docx).read("word/document.xml"))
    paras = []
    for p in root.iter(W + "p"):
        txt, runs = "", []
        for r in p.iter(W + "r"):
            t = "".join(x.text or "" for x in r.iter(W + "t"))
            if not t:
                continue
            runs.append((len(txt), len(txt) + len(t), cor_do_run(r), t))
            txt += t
        paras.append((txt, runs))
    return paras


def limpar(s):
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r" ([.,;:?!])", r"\1", s)


def analisar(docx):
    """Lê a copy. Devolve (paras, legenda, cores_troca, cores_marcador, inicio, frases, pistas);
    frases = [(parágrafo, frase)], pistas = [(índice da próxima frase, parágrafo, texto)]."""
    paras = ler(docx)

    # legenda de cores
    # a legenda pode se repetir no meio da copy, então a copy começa no "Segue copy ..." ou,
    # sem ele, logo depois do primeiro bloco de legenda
    legenda, fim_legenda, inicio_copy = {}, None, None
    for i, (txt, runs) in enumerate(paras):
        if "cor que sinaliza" in txt.lower():
            for _, _, cor, _ in runs:
                if cor:
                    legenda.setdefault(cor, limpar(txt))
            if fim_legenda is None or i - fim_legenda <= 3:
                fim_legenda = i
        if inicio_copy is None and re.search(r"segue (a )?copy", txt, re.I):
            inicio_copy = i + 1
    inicio = inicio_copy if inicio_copy is not None else (fim_legenda + 1 if fim_legenda is not None else 0)
    cores_troca = {c for c, d in legenda.items() if TROCA.search(d)}
    cores_marcador = {c for c, d in legenda.items() if MARCADOR.search(d)} - cores_troca

    frases, pistas = [], []  # pistas: (índice da próxima frase, texto)
    for i in range(inicio, len(paras)):
        txt, runs = paras[i]
        if not txt.strip() or "cor que sinaliza" in txt.lower():
            continue
        cores = {c for _, _, c, _ in runs if c}
        if cores & cores_troca or ROTULO.match(txt):
            pistas.append((len(frases), i, limpar(txt)))
        marcas = [
            (x, y) for x, y, c, t in runs
            if c and c not in cores_troca and c not in cores_marcador and not re.match(r"\s*https?://", t)
        ]
        if not marcas:
            continue
        # frase = do começo até o ponto (. ! ?) que vem antes de espaço + maiúscula
        cortes, ini = [], 0
        for m in re.finditer(r"[.!?]\s+(?=[A-ZÄÖÜÀ-Ý\"„“])", txt):
            cortes.append((ini, m.start() + 1))
            ini = m.end()
        cortes.append((ini, len(txt)))
        for x0, x1 in cortes:
            if any(x < x1 and y > x0 for x, y in marcas):
                frases.append((i, limpar(txt[x0:x1])))
    return paras, legenda, cores_troca, cores_marcador, inicio, frases, pistas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("--saida")
    a = ap.parse_args()
    paras, legenda, cores_troca, cores_marcador, inicio, frases, pistas = analisar(a.docx)

    print("LEGENDA:")
    for c, d in legenda.items():
        tipo = "troca de personagem" if c in cores_troca else "ignorada" if c in cores_marcador else "entra"
        print(f"  {c:14} {tipo:20} {d}")
    print(f"Copy começa no parágrafo {inicio}.\n")

    saida = Path(a.saida) if a.saida else Path(a.docx).with_name(Path(a.docx).stem + " - [expert].txt")
    saida.write_text("\n".join(f"[expert]\n{f}" for _, f in frases) + "\n", encoding="utf-8")
    print(f"{len(frases)} frases -> {saida}\n")

    print("PISTAS DE TROCA DE PERSONAGEM (antes da frase n):")
    if not pistas:
        print("  nenhuma marcação nem rótulo de troca na copy")
    for n, i, t in pistas:
        print(f"  antes da frase {n + 1} (parágrafo {i}): {t[:120]}")
    print("\nFRASES (n | parágrafo | texto):")
    for n, (i, f) in enumerate(frases, 1):
        print(f"  {n:3} | {i:4} | {f}")


if __name__ == "__main__":
    main()
