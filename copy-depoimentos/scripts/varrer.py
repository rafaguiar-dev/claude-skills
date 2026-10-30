"""Folha de prints de um trecho do vídeo, com o tempo (em segundos) escrito em cada print.

Uso: python -I varrer.py "<pasta>" <início_s> <fim_s> [--nome dep3] [--passo 3]

Usa o vídeo do frases.json (rode o preparar.py antes). Até 40 prints por folha; o passo
cresce sozinho em trechos longos. Grava <pasta>/_copy-depoimentos/varre-<nome>.jpg
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("pasta")
ap.add_argument("ini", type=float)
ap.add_argument("fim", type=float)
ap.add_argument("--nome")
ap.add_argument("--passo", type=float, default=2)
a = ap.parse_args()

trab = Path(a.pasta) / "_copy-depoimentos"
video = json.loads((trab / "frases.json").read_text(encoding="utf-8"))["video"]
nome = a.nome or f"{a.ini:.0f}-{a.fim:.0f}"
passo = max(a.passo, (a.fim - a.ini) / 40)
tmp = trab / "tmp"
tmp.mkdir(exist_ok=True)
t, k = a.ini, 0
while t < a.fim and k < 40:
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                    "-vf", f"scale=135:-1,drawtext=text='{t:.0f}':x=3:y=3:fontsize=18:fontcolor=yellow"
                    ":box=1:boxcolor=black", str(tmp / f"{k:02d}.jpg")], stderr=subprocess.DEVNULL)
    t += passo
    k += 1
saida = trab / f"varre-{nome}.jpg"
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(tmp / "%02d.jpg"), "-vf", "tile=10x4",
                "-frames:v", "1", str(saida)], stderr=subprocess.DEVNULL)
for p in tmp.iterdir():
    p.unlink()
tmp.rmdir()
print(f"{k} prints de {a.ini:.0f}s a {a.fim:.0f}s (passo {passo:.1f}s) -> {saida}")
