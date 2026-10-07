"""Look (cor), movimento por plano e enquadramento de rosto."""
import cv2
import numpy as np

from .media import decode
from .util import hexcolor, r


def look(src, info: dict, fps=2.0) -> dict:
    frames, _ = decode(src, info, width=160, fps=fps)
    if not len(frames):
        return {}
    f = frames.astype(np.float32) / 255
    luma = 0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]
    hsv = np.stack([cv2.cvtColor(fr, cv2.COLOR_RGB2HSV) for fr in frames]).astype(np.float32)
    sat = hsv[..., 1] / 255
    warmth = float((f[..., 0] - f[..., 2]).mean())
    px = frames[:, ::4, ::4].reshape(-1, 3).astype(np.float32)
    _, labels, centers = cv2.kmeans(px, 6, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 2,
                                    cv2.KMEANS_PP_CENTERS)
    share = np.bincount(labels.ravel(), minlength=6) / len(labels)
    palette = [{"cor": hexcolor(centers[i]), "proporcao": r(share[i], 2)} for i in np.argsort(-share)]
    brightness, contrast, saturation = float(luma.mean()), float(luma.std()), float(sat.mean())
    desc = []
    desc.append("claro" if brightness > 0.55 else ("escuro" if brightness < 0.3 else "exposição média"))
    desc.append("alto contraste" if contrast > 0.27 else ("contraste baixo/lavado" if contrast < 0.15 else "contraste médio"))
    desc.append("saturado" if saturation > 0.45 else ("dessaturado" if saturation < 0.2 else "saturação natural"))
    desc.append("quente" if warmth > 0.06 else ("frio" if warmth < -0.03 else "neutro"))
    return {"brilho": r(brightness, 2), "contraste": r(contrast, 2), "saturacao": r(saturation, 2),
            "temperatura": r(warmth, 3), "descricao": ", ".join(desc), "paleta": palette}


def movement(src, info: dict, shots: list, fps=6.0) -> list:
    """Movimento dominante de cada plano pelo fluxo óptico (zoom digital, pan, tremor)."""
    frames, times = decode(src, info, width=128, fps=fps)
    times = np.array(times)
    out = []
    for shot in shots:
        idx = np.where((times >= shot["inicio"] + 0.05) & (times < shot["fim"] - 0.05))[0]
        if len(idx) < 3:
            out.append({"plano": shot["n"], "movimento": "curto demais"})
            continue
        divs, us, vs = [], [], []
        for a, b in zip(idx, idx[1:]):
            ga = cv2.cvtColor(frames[a], cv2.COLOR_RGB2GRAY)
            gb = cv2.cvtColor(frames[b], cv2.COLOR_RGB2GRAY)
            flow = cv2.calcOpticalFlowFarneback(ga, gb, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            h, w = flow.shape[:2]
            ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
            xs -= w / 2
            ys -= h / 2
            u, v = flow[..., 0], flow[..., 1]
            divs.append(float((u * xs + v * ys).sum() / (xs ** 2 + ys ** 2).sum()))
            us.append(float(u.mean()))
            vs.append(float(v.mean()))
        zoom_per_s = float(np.mean(divs)) * fps
        pan_x, pan_y = float(np.mean(us)) * fps / 128, float(np.mean(vs)) * fps / 128
        jitter = float(np.std(us) + np.std(vs))
        consistent = np.mean(np.sign(divs) == np.sign(np.mean(divs))) > 0.75
        labels = []
        if consistent and abs(zoom_per_s) > 0.02:
            labels.append(f"{'push-in' if zoom_per_s > 0 else 'pull-out'} ~{abs(zoom_per_s) * 100:.0f}%/s")
        if abs(pan_x) > 0.05 or abs(pan_y) > 0.05:
            labels.append("pan " + ("horizontal" if abs(pan_x) >= abs(pan_y) else "vertical"))
        if jitter > 0.6:
            labels.append("câmera na mão/tremida")
        out.append({"plano": shot["n"], "movimento": ", ".join(labels) or "estático",
                    "zoom_por_s": r(zoom_per_s, 3), "tremor": r(jitter, 2)})
    return out


def faces(src, info: dict, fps=2.0) -> dict:
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    frames, times = decode(src, info, width=360, fps=fps)
    if not len(frames):
        return {}
    areas, centers = [], []
    for fr in frames:
        g = cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY)
        found = cascade.detectMultiScale(g, 1.1, 5, minSize=(24, 24))
        if len(found):
            x, y, w, h = max(found, key=lambda b: b[2] * b[3])
            areas.append(w * h / (g.shape[0] * g.shape[1]))
            centers.append(((x + w / 2) / g.shape[1], (y + h / 2) / g.shape[0]))
        else:
            areas.append(0.0)
    present = [a for a in areas if a > 0]
    cover = len(present) / len(areas)
    result = {"tempo_com_rosto": r(cover, 2)}
    if present:
        med = float(np.median(present))
        result["tamanho_rosto_mediano"] = r(med, 3)
        result["enquadramento"] = ("close (rosto grande)" if med > 0.1 else
                                   "plano médio" if med > 0.025 else "plano aberto")
        result["rosto_centro_mediano"] = [r(np.median([c[0] for c in centers]), 2),
                                          r(np.median([c[1] for c in centers]), 2)]
    result["formato_provavel"] = ("talking head / UGC com apresentador" if cover > 0.5 else
                                  "misto (apresentador + B-roll)" if cover > 0.15 else "sem apresentador (B-roll/produto/motion)")
    return result



def split_screen(src, info: dict, transitions: list, fps=6.0) -> list:
    """Trechos em tela dividida. Semente: cortes que trocaram só um lado do quadro
    (cuts.py → "troca de insert"). A partir de cada semente, segue a costura: a linha reta na
    posição da divisória continua existindo (borda forte em boa parte da largura) antes e depois."""
    seeds = [t for t in transitions if t.get("detalhes", {}).get("linha_divisoria") is not None]
    if not seeds:
        return []
    frames, times = decode(src, info, width=180, fps=fps)
    times = np.array(times)
    out = []
    for seed in seeds:
        det = seed["detalhes"]
        if any(o["inicio"] <= seed["tempo"] <= o["fim"] for o in out):
            continue
        horiz = det["eixo"].startswith("horizontal")
        strength = []
        for f in frames:
            g = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY).astype(np.float32)
            d = np.abs(np.diff(g, axis=0 if horiz else 1))
            if not horiz:
                d = d.T
            y = int(round(det["linha_divisoria"] * (d.shape[0] + 1))) - 1
            band = d[max(0, y - 1):y + 2]
            strength.append(float((band.max(0) > 12).mean()))
        strength = np.array(strength)
        # mediana móvel de ~1 s: legenda cruzando a costura ou um quadro escuro não quebram o trecho
        k = max(3, int(fps))
        smooth = np.array([np.median(strength[max(0, i - k // 2):i + k // 2 + 1]) for i in range(len(strength))])
        # dois vídeos diferentes: o movimento de um lado não acompanha o do outro. Numa cena única
        # (ex.: peitoril de janela na mesma altura da costura) as duas faixas se mexem juntas.
        grays = np.stack([cv2.cvtColor(f, cv2.COLOR_RGB2GRAY).astype(np.float32) for f in frames])
        act = np.abs(np.diff(grays, axis=0))
        if not horiz:
            act = act.transpose(0, 2, 1)
        H = act.shape[1]
        yy = int(det["linha_divisoria"] * H)
        up = act[:, max(0, yy - int(.12 * H)):max(1, yy - int(.02 * H))].mean((1, 2))
        dn = act[:, yy + int(.02 * H):yy + int(.12 * H)].mean((1, 2))
        w = max(8, int(fps * 2))

        def together(i0, i1):
            """As duas faixas se mexem juntas entre os quadros i0 e i1 (= mesma cena, não tela dividida)?"""
            i0, i1 = max(0, i0), min(len(up), i1)
            a_, b_ = up[i0:i1], dn[i0:i1]
            if len(a_) < 6 or a_.std() < 1e-3 or b_.std() < 1e-3:
                return False
            return float(np.corrcoef(a_, b_)[0, 1]) >= 0.45
        i0 = int(np.argmin(np.abs(times - seed["tempo"])))
        if smooth[i0] < 0.3:
            continue
        if together(i0 + 1, i0 + 1 + w):
            continue  # depois do "corte parcial" as metades se mexem juntas: era corte comum (mesmo enquadramento em cima)
        a, b = i0, i0
        while a > 0 and smooth[a - 1] >= 0.3:
            a -= 1
        while b < len(smooth) - 1 and smooth[b + 1] >= 0.3:
            b += 1
        # fronteiras exatas: se houver transição logo na borda, ela marca o fim da tela dividida
        start, end = float(times[a]), float(times[b]) + 1 / fps
        # a costura pode coincidir com uma borda real do cenário depois da tela dividida acabar:
        # o trecho termina no primeiro corte depois do qual as duas metades se mexem juntas
        for t in sorted(transitions, key=lambda t: t["tempo"]):
            if seed["tempo"] < t["tempo"] < end:
                i = int(np.searchsorted(times, t["tempo"]))
                if together(i, i + w):
                    end = t["tempo"]
                    break
        for t in sorted(transitions, key=lambda t: -t["tempo"]):
            if start < t["tempo"] < seed["tempo"]:
                i = int(np.searchsorted(times, t["tempo"]))
                if together(i - w, i):
                    start = t["tempo"]
                    break
        for t in transitions:
            if t is not seed and abs(t["inicio"] - end) < 0.5:
                end = t["inicio"]
            if t is not seed and abs(t["fim"] - start) < 0.5:
                start = t["fim"]
        out.append({"inicio": r(start), "fim": r(end), "eixo": det["eixo"],
                    "linha_divisoria": det["linha_divisoria"],
                    "lado_do_insert": det["so_muda"],
                    "trocas_de_insert": [t["tempo"] for t in transitions
                                         if t.get("tipo", "").startswith("troca de insert") and start <= t["tempo"] <= end]})
    return out
