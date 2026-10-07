"""ffmpeg/ffprobe: metadados, áudio e decodificação de frames."""
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .util import run

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


def _aspect(w: int, h: int) -> str:
    ratio = w / h
    options = {"9:16": 9 / 16, "4:5": 4 / 5, "1:1": 1.0, "4:3": 4 / 3, "16:9": 16 / 9, "3:4": 3 / 4, "2:3": 2 / 3}
    return min(options, key=lambda k: abs(options[k] - ratio))


def probe(path) -> dict:
    data = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path]))
    video = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    audio = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    duration = float(data["format"].get("duration") or (video or {}).get("duration") or 0)
    info = {"duracao": round(duration, 3), "tem_audio": audio is not None, "tem_video": video is not None}
    if video:
        num, den = (video.get("avg_frame_rate") or "0/1").split("/")
        fps = float(num) / float(den) if float(den) else 0.0
        if not 1 <= fps <= 240:
            num, den = (video.get("r_frame_rate") or "30/1").split("/")
            fps = float(num) / float(den) if float(den) else 30.0
        w, h = int(video["width"]), int(video["height"])
        rotation = 0
        for side in video.get("side_data_list", []) or []:
            if "rotation" in side:
                rotation = int(side["rotation"])
        rotation = rotation or int((video.get("tags") or {}).get("rotate", 0) or 0)
        if abs(rotation) % 180 == 90:
            w, h = h, w
        info.update(largura=w, altura=h, fps=round(fps, 3), proporcao=_aspect(w, h))
    return info


def extract_audio(src, dst, sr=16000, channels=1) -> Path:
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-vn", "-ac", channels, "-ar", sr,
         "-c:a", "pcm_s16le", dst])
    return dst


def _size_for(info: dict, width: int, crop=None) -> tuple:
    w, h = info["largura"], info["altura"]
    if crop:
        w, h = w * crop[2], h * crop[3]
    height = int(round(width * h / w / 2) * 2)
    return width, max(2, height)


def _crop_filter(crop) -> str:
    if not crop:
        return ""
    x, y, w, h = crop
    return f"crop=iw*{w}:ih*{h}:iw*{x}:ih*{y},"


def decode(src, info: dict, width=96, fps=None, start=None, duration=None, crop=None):
    """Decodifica um trecho como RGB uint8 (N, H, W, 3). Retorna (frames, tempos)."""
    w, h = _size_for(info, width, crop)
    vf = _crop_filter(crop) + (f"fps={fps}," if fps else "") + f"scale={w}:{h}:flags=area,format=rgb24"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", f"{max(0.0, start):.3f}"]
    cmd += ["-i", src]
    if duration is not None:
        cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-vf", vf, "-f", "rawvideo", "-"]
    raw = run(cmd)
    stride = w * h * 3
    n = len(raw) // stride
    frames = np.frombuffer(raw[: n * stride], dtype=np.uint8).reshape(n, h, w, 3)
    rate = fps or info.get("fps") or 30.0
    t0 = start or 0.0
    times = [round(t0 + i / rate, 3) for i in range(n)]
    return frames, times


def frame_at(src, t: float, info: dict, width=480, crop=None) -> Image.Image:
    t = max(0.0, min(float(t), info["duracao"] - 0.04))
    vf = _crop_filter(crop) + f"scale={width}:-2:flags=lanczos"
    raw = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1",
               "-vf", vf, "-f", "image2pipe", "-vcodec", "png", "-"])
    if not raw:
        raise RuntimeError(f"nenhum frame em {t:.2f}s")
    return Image.open(io.BytesIO(raw)).convert("RGB")


def frame_full(src, t: float, info: dict) -> np.ndarray:
    """Frame em resolução original como array RGB."""
    return np.asarray(frame_at(src, t, info, width=info["largura"]))


def cut_clip(src, dst, start: float, end: float, label_time=False) -> Path:
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", src,
           "-t", f"{end - start:.3f}"]
    if label_time:
        font = "'C\\:/Windows/Fonts/consola.ttf'" if Path("C:/Windows/Fonts/consola.ttf").exists() else None
        draw = (f"drawtext={'fontfile=' + font + ':' if font else ''}text='%{{pts\\:hms\\:{start:.3f}}}'"
                ":x=10:y=10:fontsize=h/28:fontcolor=white:box=1:boxcolor=black@0.6")
        cmd += ["-vf", draw]
    if dst.suffix.lower() == ".wav":
        cmd += ["-vn", "-c:a", "pcm_s16le", dst]
    else:
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", dst]
    run(cmd)
    return dst
