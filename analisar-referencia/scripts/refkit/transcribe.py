"""Transcrição local com faster-whisper (tempo por palavra).

A GPU é tentada num subprocesso: se faltar cuDNN/cuBLAS o processo pode abortar sem exceção,
então o processo principal só lê o resultado e cai para CPU quando necessário."""
import os
import subprocess
import sys
from pathlib import Path

from .util import log, read_json, write_json

GPU_MODEL = "large-v3-turbo"
CPU_MODEL = "large-v3-turbo"


def _add_cuda_dlls():
    try:
        import nvidia  # pacotes nvidia-cublas-cu12 / nvidia-cudnn-cu12 (extra "gpu")
    except ImportError:
        return
    for base in list(nvidia.__path__):
        for bin_dir in Path(base).glob("*/bin"):
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(str(bin_dir))


def worker(audio: str, out: str, device: str, model_name: str, language: str | None) -> None:
    """Executado em subprocesso: `ref.py _transcrever ...`."""
    if device == "cuda":
        _add_cuda_dlls()
    from faster_whisper import WhisperModel

    compute = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_name, device=device, compute_type=compute)
    segments, info = model.transcribe(audio, language=language or None, word_timestamps=True, vad_filter=True,
                                      vad_parameters={"min_silence_duration_ms": 300}, beam_size=5)
    result = []
    for seg in segments:
        words = [{"texto": w.word.strip(), "inicio": round(w.start, 3), "fim": round(w.end, 3),
                  "prob": round(w.probability, 3)} for w in (seg.words or []) if w.word.strip()]
        result.append({"inicio": round(seg.start, 3), "fim": round(seg.end, 3), "texto": seg.text.strip(),
                       "palavras": words})
    write_json(Path(out), {"format": "ref.transcript@1", "idioma": info.language,
                           "prob_idioma": round(info.language_probability, 3), "modelo": model_name,
                           "dispositivo": device, "segmentos": result})


def transcribe(audio: Path, out: Path, language=None, model=None, device="auto") -> dict:
    script = Path(__file__).resolve().parents[1] / "ref.py"
    attempts = []
    if device in ("auto", "cuda"):
        attempts.append(("cuda", model or GPU_MODEL))
    if device in ("auto", "cpu"):
        attempts.append(("cpu", model or CPU_MODEL))
    last_err = ""
    for dev, name in attempts:
        log(f"transcrevendo com {name} em {dev.upper()}")
        cmd = [sys.executable, str(script), "_transcrever", str(audio), str(out), dev, name, language or ""]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode == 0 and out.exists():
            return read_json(out)
        last_err = proc.stderr.decode("utf-8", errors="replace")[-600:]
        log(f"falhou em {dev.upper()}: {last_err.strip().splitlines()[-1] if last_err.strip() else proc.returncode}")
    raise RuntimeError(f"transcrição falhou: {last_err}")


def speech_stats(transcript: dict, duration: float) -> dict:
    words = [w for s in transcript.get("segmentos", []) for w in s.get("palavras", [])]
    if not words:
        return {"tem_fala": False}
    gaps = [b["inicio"] - a["fim"] for a, b in zip(words, words[1:])]
    pauses = [g for g in gaps if g >= 0.35]
    speaking = sum(w["fim"] - w["inicio"] for w in words)
    first3 = [w["texto"] for w in words if w["inicio"] < 3.0]
    return {
        "tem_fala": True,
        "idioma": transcript.get("idioma"),
        "palavras": len(words),
        "inicio_fala": words[0]["inicio"],
        "fim_fala": words[-1]["fim"],
        "palavras_por_segundo": round(len(words) / max(0.1, words[-1]["fim"] - words[0]["inicio"]), 2),
        "pausas_acima_350ms": len(pauses),
        "pausa_media": round(sum(pauses) / len(pauses), 2) if pauses else 0,
        "maior_pausa": round(max(gaps), 2) if gaps else 0,
        "cobertura_fala": round(speaking / max(0.1, duration), 2),
        "gancho_3s": " ".join(first3),
        "texto": " ".join(s["texto"] for s in transcript["segmentos"]),
    }
