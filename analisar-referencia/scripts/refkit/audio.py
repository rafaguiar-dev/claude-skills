"""Áudio: separação voz/música (Demucs), música (Shazam, BPM, batidas), SFX e mixagem."""
import asyncio
from pathlib import Path

import numpy as np
import soundfile as sf

from .util import log, r


def separate(wav44: Path, out_dir: Path) -> dict:
    """Demucs htdemucs em dois stems: voz e o resto (música + efeitos)."""
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    out_dir.mkdir(parents=True, exist_ok=True)
    voice, rest = out_dir / "voz.wav", out_dir / "musica_e_efeitos.wav"
    if voice.exists() and rest.exists():
        return {"voz": voice, "resto": rest}
    model = get_model("htdemucs")
    model.eval()
    audio, sr = sf.read(str(wav44), always_2d=True, dtype="float32")
    x = torch.from_numpy(audio.T.copy())
    if x.shape[0] == 1:
        x = x.repeat(2, 1)
    ref = x.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    with torch.no_grad():
        sources = apply_model(model, ((x - mean) / std)[None], device="cpu", split=True, overlap=0.25,
                              progress=False)[0]
    sources = sources * std + mean
    vi = model.sources.index("vocals")
    vocals = sources[vi]
    others = sources.sum(0) - vocals
    sf.write(str(voice), vocals.numpy().T, sr)
    sf.write(str(rest), others.numpy().T, sr)
    return {"voz": voice, "resto": rest}


def _db(x):
    return 20 * np.log10(np.maximum(x, 1e-6))


def _rms(y, sr, hop_s=0.1):
    import librosa
    hop = int(sr * hop_s)
    return librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0], hop_s


async def _shazam(path: str):
    from shazamio import Shazam
    shazam = Shazam()
    fn = getattr(shazam, "recognize", None) or shazam.recognize_song
    return await fn(path)


def identify(rest_wav: Path, active_ranges: list, tmp_dir: Path) -> dict:
    """Tenta reconhecer a música em até 3 janelas de ~12s onde há música."""
    import librosa
    y, sr = librosa.load(str(rest_wav), sr=44100, mono=True)
    windows = []
    for a, b in active_ranges:
        t = a
        while t + 6 <= b and len(windows) < 3:
            windows.append((t, min(b, t + 12)))
            t += 12
    if not windows and len(y) / sr >= 6:
        windows = [(0, min(len(y) / sr, 12))]
    found, tried = {}, []
    for a, b in windows:
        clip = tmp_dir / f"shazam_{int(a)}.wav"
        sf.write(str(clip), y[int(a * sr):int(b * sr)], sr)
        try:
            res = asyncio.run(_shazam(str(clip)))
            track = res.get("track") if isinstance(res, dict) else None
            tried.append({"janela": [r(a, 1), r(b, 1)], "encontrou": bool(track)})
            if track:
                key = track.get("key")
                found.setdefault(key, {"titulo": track.get("title"), "artista": track.get("subtitle"),
                                       "link": track.get("url"), "janelas": 0})
                found[key]["janelas"] += 1
        except Exception as exc:  # rede fora, limite do serviço etc.
            tried.append({"janela": [r(a, 1), r(b, 1)], "erro": str(exc)[:160]})
        finally:
            clip.unlink(missing_ok=True)
    return {"identificacao": sorted(found.values(), key=lambda f: -f["janelas"]), "tentativas": tried}


def _transition_sounds(y, sr, transitions: list) -> list:
    """Energia de agudos (>2 kHz) em volta de cada transição comparada ao entorno: whoosh/riser/impacto."""
    import librosa
    hop = 512
    spec = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    high = spec[freqs > 2000].sum(0)
    low = spec[freqs < 200].sum(0)
    tt = librosa.frames_to_time(np.arange(len(high)), sr=sr, hop_length=hop)
    def baseline(sig, a, b):
        """Mediana dos picos de janelas do mesmo tamanho no entorno — batidas regulares não contam como SFX."""
        span = max(3, int((b - a) * sr / hop))
        idx = np.where(((tt >= a - 2.0) & (tt < a)) | ((tt > b) & (tt <= b + 2.0)))[0]
        if idx.size < span:
            return None
        peaks = [sig[j:j + span].max() for j in range(idx[0], idx[-1] - span + 1, max(1, span // 2))
                 if np.all(np.isin(np.arange(j, j + span), idx))]
        return float(np.median(peaks)) if peaks else None

    out = []
    for tr in transitions:
        a, b = tr["inicio"] - 0.35, tr["fim"] + 0.25
        near = (tt >= a) & (tt <= b)
        base_hi, base_lo = baseline(high, a, b), baseline(low, a, b)
        if near.sum() < 3 or base_hi is None or base_lo is None:
            continue
        hi_ratio = float(high[near].max() / max(1e-6, base_hi))
        lo_ratio = float(low[near].max() / max(1e-6, base_lo))
        kinds = []
        if hi_ratio > 2.5:
            peak_t = float(tt[near][np.argmax(high[near])])
            kinds.append("whoosh/riser" if peak_t >= tr["inicio"] - 0.05 else "swoosh antecipado")
        if lo_ratio > 2.5:
            kinds.append("impacto/boom")
        if kinds:
            out.append({"tempo": tr["tempo"], "som": " + ".join(kinds), "agudos_x": r(hi_ratio, 1),
                        "graves_x": r(lo_ratio, 1)})
    return out


def analyze(voice_wav: Path, rest_wav: Path, transitions: list, duration: float, tmp_dir: Path,
            use_shazam=True) -> dict:
    import librosa

    cut_times = [t["tempo"] for t in transitions]
    y, sr = librosa.load(str(rest_wav), sr=22050, mono=True)
    yv, _ = librosa.load(str(voice_wav), sr=22050, mono=True)
    n = min(len(y), len(yv))
    y, yv = y[:n], yv[:n]
    rms_m, hop_s = _rms(y, sr)
    rms_v, _ = _rms(yv, sr)
    db_m, db_v = _db(rms_m), _db(rms_v)
    peak = float(np.percentile(db_m, 99)) if len(db_m) else -80
    music_on = db_m > max(-45.0, peak - 30)
    voice_on = db_v > max(-40.0, float(np.percentile(db_v, 99)) - 25)

    ranges, start = [], None
    for i, on in enumerate(music_on):
        t = i * hop_s
        if on and start is None:
            start = t
        elif not on and start is not None:
            if t - start >= 1.0:
                ranges.append((start, t))
            start = None
    if start is not None and len(music_on) * hop_s - start >= 1.0:
        ranges.append((start, len(music_on) * hop_s))
    presence = float(music_on.mean()) if len(music_on) else 0.0
    out = {"musica": {"presente": presence > 0.25, "cobertura": r(presence, 2),
                      "trechos": [[r(a, 1), r(b, 1)] for a, b in ranges]}}

    both = music_on & voice_on
    if both.sum() > 10:
        out["mixagem"] = {"musica_abaixo_da_voz_db": r(np.median(db_v[both] - db_m[both]), 1)}
        alone = music_on & ~voice_on
        if alone.sum() > 10:
            out["mixagem"]["ducking_db"] = r(np.median(db_m[alone]) - np.median(db_m[both]), 1)

    if out["musica"]["presente"]:
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
        tempo = float(np.atleast_1d(tempo)[0])
        beats = np.asarray(beats, dtype=float)
        mus = out["musica"]
        mus["bpm"] = r(tempo, 1)
        mus["batidas"] = [r(b, 2) for b in beats]
        if len(beats) > 1 and transitions:
            tol = 0.08
            # transição gradual conta como "na batida" se começa, centra ou termina na batida
            dist = [min(float(np.min(np.abs(beats - c))) for c in {t["inicio"] if t["duracao"] else t["tempo"],
                                                                     t["tempo"], t["fim"]})
                    for t in transitions]
            on_beat = sum(1 for d in dist if d <= tol) / len(dist)
            period = 60.0 / max(tempo, 1)
            chance = min(1.0, 2 * tol / period)
            mus["cortes_na_batida"] = r(on_beat, 2)
            mus["acaso_esperado"] = r(chance, 2)
            mus["sincronizado"] = on_beat >= max(0.5, 1.8 * chance)
        energy = [r(v, 1) for v in [np.median(db_m[int(i / hop_s):int((i + 1) / hop_s)])
                                    for i in range(int(duration))] if np.isfinite(v)]
        mus["energia_db_por_segundo"] = energy
        rises = [i for i in range(1, len(energy)) if energy[i] - energy[i - 1] >= 6]
        mus["subidas_de_energia"] = rises
        if use_shazam:
            log("identificando a música (Shazam)")
            mus.update(identify(rest_wav, ranges, tmp_dir))

    # efeitos sonoros: ataques fortes fora da grade da batida ou colados em cortes
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units="frames")
    beats_arr = np.asarray(out["musica"].get("batidas", []), dtype=float)
    sfx = []
    if len(onsets):
        strength = onset_env[onsets]
        thr = np.percentile(strength, 85)
        cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        rms_full = librosa.feature.rms(y=y)[0]
        for f, s in zip(onsets, strength):
            if s < thr:
                continue
            t = float(librosa.frames_to_time(f, sr=sr))
            near_cut = any(abs(t - c) <= 0.15 for c in cut_times)
            off_beat = len(beats_arr) == 0 or float(np.min(np.abs(beats_arr - t))) > 0.07
            if not (near_cut or off_beat):
                continue
            c = float(np.median(cent[max(0, f - 2):f + 8]))
            pre = rms_full[max(0, f - 9):f]
            rising = len(pre) > 3 and pre[-1] > 2.5 * max(1e-6, pre[0])
            if rising and c > 2500:
                kind = "whoosh/swoosh (provável)"
            elif c > 4000:
                kind = "agudo: pop/click/brilho (provável)"
            elif c < 1200:
                kind = "grave: impacto/boom (provável)"
            else:
                kind = "médio: hit/transição (provável)"
            sfx.append({"tempo": r(t, 2), "tipo": kind, "perto_de_corte": near_cut, "forca": r(s, 1)})
    out["sfx_candidatos"] = sfx[:60]
    out["som_nas_transicoes"] = _transition_sounds(y, sr, transitions)
    return out
