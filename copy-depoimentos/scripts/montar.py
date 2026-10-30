"""Monta o docx final: frases marcadas com [expert] / [depoimento N] e o print do rosto na 1ª fala de cada pessoa.

Uso: python -I montar.py "<pasta>" "<mapa.json>"

mapa.json (feito pelo Claude depois de olhar as folhas):
  {"falas":  {"5": 1, "6": 2, "9": 4},      frase marcada -> número do depoimento (o resto é [expert])
   "prints": {"1": 2448, "2": 2537}}         depoimento -> segundo do vídeo com o rosto bem visível

Grava ao lado da copy: "<copy> - [depoimentos].docx", o mesmo em .txt e a pasta "prints depoimentos".
"""
import json
import subprocess
import sys
from pathlib import Path

import docx
from docx.shared import Cm, Pt

sys.stdout.reconfigure(encoding="utf-8")
pasta, mapa = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
dados = json.loads((pasta / "_copy-depoimentos" / "frases.json").read_text(encoding="utf-8"))
copy, video = Path(dados["docx"]), dados["video"]
falas = {int(k): int(v) for k, v in mapa.get("falas", {}).items()}
prints = {int(k): float(v) for k, v in mapa.get("prints", {}).items()}

fotos = pasta / "prints depoimentos"
fotos.mkdir(exist_ok=True)
img = {}
for n, t in prints.items():
    img[n] = fotos / f"depoimento {n}.jpg"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", video,
                    "-frames:v", "1", "-q:v", "2", str(img[n])], check=True)

d = docx.Document()
d.styles["Normal"].font.name = "Arial"
d.styles["Normal"].font.size = Pt(11)
txt, vistos = [], set()
for x in dados["frases"]:
    n = falas.get(x["n"])
    tag = f"[depoimento {n}]" if n else "[expert]"
    d.add_paragraph().add_run(tag).bold = True
    if n and n not in vistos:
        vistos.add(n)
        if n in img:
            d.add_picture(str(img[n]), width=Cm(5))
        else:
            print(f"AVISO: depoimento {n} sem print no mapa")
    d.add_paragraph(x["texto"])
    txt += [tag, x["texto"]]

base = copy.with_name(copy.stem + " - [depoimentos]")
d.save(base.with_suffix(".docx"))
base.with_suffix(".txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
print(f"{len(dados['frases'])} frases, {len(vistos)} depoimentos -> {base.with_suffix('.docx')}")
print(f"Prints em {fotos}")
