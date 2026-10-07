"""Cortes e transições. Os rótulos são candidatos mecânicos: confirme nas grades de evidência."""
import cv2
import numpy as np

from .media import decode
from .util import r

# tipo detectado -> transição equivalente no OpenChatCut (None = sem transição, é corte)
OPENCHATCUT_TRANSITION = {
    "corte seco": None,
    "jump cut": None,
    "punch-in": None,  # recriar com keyframe de escala no clipe seguinte
    "punch-out": None,
    "dip-to-black": "dip-to-black",
    "dip-to-color": "dip-to-color",
    "flash": "flash",
    "cross-dissolve": "cross-dissolve",
    "whip-pan": "whip-pan",
    # zoom detectado por borrão de movimento: o anticipation-zoom do OpenChatCut não borra, o radial-blur sim
    "zoom-in": "radial-blur",
    "zoom-out": "radial-blur",
    "radial-blur": "radial-blur",
    "glitch": "glitch-cut",
    "gradual (verificar)": "cross-dissolve",
    "emenda na fonte (morph)": None,
    "troca de insert (tela dividida)": None,  # corte só na metade do insert  # não é edição: vem do material (ex.: vídeo gerado por IA)
}


def _diff(a, b) -> float:
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean() / 255.0)


def _hist(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
    h = cv2.calcHist([hsv], [0, 1, 2], None, [16, 4, 4], [0, 180, 0, 256, 0, 256])
    cv2.normalize(h, h)
    return h


def _hdist(h1, h2) -> float:
    return float(cv2.compareHist(h1, h2, cv2.HISTCMP_BHATTACHARYYA))


def _gray(frame):
    return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)


def _zoom_match(a, b):
    """Procura b como recorte ampliado de a (punch-in). Retorna ((escala, correlação), correlação sem zoom).

    Conteúdo liso (gradiente, parede) casa em qualquer escala, então exige textura e confirma
    reconstruindo o recorte: a ampliação precisa reproduzir b em cor e em pixels."""
    ga, gb = _gray(a).astype(np.float32), _gray(b).astype(np.float32)
    h, w = ga.shape
    base = float(cv2.matchTemplate(ga, gb, cv2.TM_CCOEFF_NORMED).max())
    edges = lambda g: float(np.abs(cv2.Laplacian(g, cv2.CV_32F)).mean())
    if edges(ga) < 2.0 or edges(gb) < 2.0:
        return (1.0, base), base
    direct = _diff(a, b)
    best = (1.0, base)
    for scale in (1.12, 1.25, 1.4, 1.6, 1.85, 2.2):
        tw, th = int(w / scale), int(h / scale)
        if tw < 16 or th < 16:
            break
        tmpl = cv2.resize(gb, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(ga, tmpl, cv2.TM_CCOEFF_NORMED)
        _, score, _, (x, y) = cv2.minMaxLoc(res)
        if score <= best[1]:
            continue
        rebuilt = cv2.resize(a[y:y + th, x:x + tw], (w, h), interpolation=cv2.INTER_LINEAR)
        if _diff(rebuilt, b) < 0.6 * direct and _hdist(_hist(rebuilt), _hist(b)) < 0.25:
            best = (scale, float(score))
    return best, base


def _chroma_shift(frame) -> float:
    rch = frame[..., 0].astype(np.float32)
    bch = frame[..., 2].astype(np.float32)
    (dx, dy), resp = cv2.phaseCorrelate(rch, bch)
    return float(np.hypot(dx, dy)) if resp > 0.05 else 0.0


def _flow(a, b):
    flow = cv2.calcOpticalFlowFarneback(_gray(a), _gray(b), None, 0.5, 3, 15, 3, 5, 1.2, 0)
    h, w = flow.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    xs -= w / 2
    ys -= h / 2
    u, v = flow[..., 0], flow[..., 1]
    div = float((u * xs + v * ys).sum() / max(1.0, (xs ** 2 + ys ** 2).sum()))
    return float(u.mean()), float(v.mean()), div


def _sharp(frame):
    g = _gray(frame).astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1)
    return float(np.abs(gx).mean()), float(np.abs(gy).mean())


def _cell_sharp(frame, grid=3):
    """Nitidez (|Laplaciano| médio) por célula de uma grade grid×grid."""
    g = _gray(frame).astype(np.float32)
    lap = np.abs(cv2.Laplacian(g, cv2.CV_32F))
    h, w = lap.shape
    return np.array([lap[i * h // grid:(i + 1) * h // grid, j * w // grid:(j + 1) * w // grid].mean()
                     for i in range(grid) for j in range(grid)])


def _blur_window(frames, s, e, fps):
    """Borrão de movimento em volta de um corte (zoom/whip com blur de ~4–8 quadros).

    Compara cada célula da grade com a mesma célula fora da janela; a mediana das células ignora
    legenda entrando/saindo e tela dividida com metade parada."""
    n = len(frames)
    reach = max(4, int(round(fps * 0.2)))
    pre_idx = [i for i in range(s - 3 * reach, s - reach) if 0 <= i < n]
    post_idx = [i for i in range(e + reach + 1, e + 3 * reach + 1) if 0 <= i < n]
    if len(pre_idx) < 2 or len(post_idx) < 2:
        return None
    # cada lado do corte comparado com ele mesmo: cena lisa depois de cena texturizada não é borrão
    base_pre = np.median(np.stack([_cell_sharp(frames[i]) for i in pre_idx]), axis=0) + 0.5
    base_post = np.median(np.stack([_cell_sharp(frames[i]) for i in post_idx]), axis=0) + 0.5
    # só células com textura nos dois lados (fundo liso dá razão sem sentido); legenda que some
    # também derruba uma célula, por isso exige várias
    textured = (base_pre > 3.0) & (base_post > 3.0)
    if textured.sum() < 4:
        return None
    win = list(range(max(0, s - reach), min(n, e + reach + 1)))
    score = {i: float(np.median((_cell_sharp(frames[i]) / (base_pre if i < s else base_post))[textured]))
             for i in win}
    blurry = [i for i in win if score[i] < 0.5]
    if len(blurry) < 2:
        return None
    # precisa ser um bloco contínuo (tolerando 1 quadro) que encosta no corte
    run = [blurry[0]]
    for i in blurry[1:]:
        if i - run[-1] <= 2:
            run.append(i)
        elif not (run[0] - 1 <= s <= run[-1] + 1):
            run = [i]
    if not (run[0] - 2 <= s <= run[-1] + 2) or len(run) < 2:
        return None
    a, b = run[0], run[-1]
    # as bordas do borrão (entrada/saída do movimento) são mais leves: estende enquanto < 0.82
    while a - 1 in score and score[a - 1] < 0.82:
        a -= 1
    while b + 1 in score and score[b + 1] < 0.82:
        b += 1
    sx = np.mean([_sharp(frames[i])[0] for i in range(a, b + 1)])
    sy = np.mean([_sharp(frames[i])[1] for i in range(a, b + 1)])
    divs = [_flow(frames[i], frames[i + 1])[2] for i in range(max(0, a - 1), min(n - 1, b + 1))]
    return {"inicio": a, "fim": b, "nitidez_min": r(min(score[i] for i in run), 2),
            "sobel_x_y": r(sx / max(1e-3, sy), 2), "divergencia": r(float(np.median(divs)), 4)}


def _partial_cut(before, after):
    """Corte que troca só um lado do quadro (insert numa tela dividida). Retorna a linha divisória."""
    diff = np.abs(after.astype(np.float32) - before.astype(np.float32)).mean(2) / 255.0
    best = None
    for axis, sides in ((1, ("em cima", "embaixo")), (0, ("esquerda", "direita"))):
        prof = diff.mean(axis)  # por linha (axis=1) ou por coluna (axis=0)
        L = len(prof)
        for y in range(int(L * 0.2), int(L * 0.8)):
            a, b = float(prof[:y].mean()), float(prof[y:].mean())
            hi, lo = max(a, b), min(a, b)
            if hi < 0.12 or lo > 0.3 * hi:
                continue
            # ajuste de degrau (dois níveis): maximiza a variância explicada, não só a diferença
            contrast = (hi - lo) ** 2 * y * (L - y) / L ** 2
            if not best or contrast > best[0]:
                best = (contrast, y, sides[0] if a > b else sides[1], axis)
    if not best:
        return None
    _, y, side, axis = best
    # refina pela borda reta mais forte perto do degrau (a costura entre os dois vídeos)
    g = _gray(after).astype(np.float32)
    edges = np.abs(np.diff(g, axis=0 if axis == 1 else 1)).mean(1 if axis == 1 else 0)
    L = len(edges) + 1
    rad = max(2, int(L * 0.06))
    lo_i, hi_i = max(1, y - rad), min(len(edges) - 1, y + rad)
    y = lo_i + int(np.argmax(edges[lo_i:hi_i]))
    pos = (y + 1) / L
    return {"so_muda": side, "linha_divisoria": r(pos, 3),
            "eixo": "horizontal (em cima / embaixo)" if axis == 1 else "vertical (esquerda / direita)"}


def _blend_span(frames, s, e, k):
    """Frames em volta de um pico que são mistura linear do antes e do depois (= dissolve)."""
    n = len(frames)
    ia, ib = max(0, s - 2 * k), min(n - 1, e + 2 * k)
    A, B = frames[ia].astype(np.float32), frames[ib].astype(np.float32)
    denom = float(((A - B) ** 2).sum())
    if denom <= 0:
        return None
    scale = max(1e-3, float(np.abs(A - B).mean()))
    mixed, alphas = [], []
    for j in range(ia + 1, ib):
        M = frames[j].astype(np.float32)
        alpha = float(np.clip(((M - B) * (A - B)).sum() / denom, 0, 1))
        rel = float(np.abs(M - (alpha * A + (1 - alpha) * B)).mean() / scale)
        if 0.08 < alpha < 0.92 and rel < 0.35:
            mixed.append(j)
            alphas.append(alpha)
    if len(mixed) < 3 or not (mixed[0] <= s <= mixed[-1] + 1):
        return None
    # dissolve de verdade: o peso da imagem antiga cai de forma contínua, sem saltos (salto = corte)
    steps = [a - b for a, b in zip(alphas, alphas[1:])]
    falling = sum(1 for st in steps if st >= -0.03) / len(steps)
    if max(alphas) - min(alphas) < 0.4 or falling < 0.8 or max(steps) > 0.25:
        return None
    return mixed[0], mixed[-1]


def _classify(frames, luma, s, e, fps, hard: bool):
    n = len(frames)
    pre, post = max(0, s - 3), min(n - 1, e + 3)
    seg = luma[s:e + 1]
    evidence = {}
    if seg.min() < 0.06 and luma[pre] > 0.1 and luma[post] > 0.1:
        return "dip-to-black", 0.85, evidence
    if seg.max() > 0.82 and seg.max() - max(luma[pre], luma[post]) > 0.15:
        return "flash", 0.8, evidence
    for i in range(s, e + 1):
        std = frames[i].astype(np.float32).std() / 255
        if std < 0.03 and 0.06 < luma[i] < 0.82:
            evidence["cor"] = "#{:02X}{:02X}{:02X}".format(*frames[i].reshape(-1, 3).mean(0).astype(int))
            return "dip-to-color", 0.7, evidence
    # glitch = separação RGB acima da que o próprio conteúdo já tem antes/depois do corte
    window = range(max(0, s - 2), min(n, e + 3))
    shift = max(_chroma_shift(frames[i]) for i in window)
    ref_idx = [i for i in (s - 10, s - 7, e + 7, e + 10) if 0 <= i < n]
    baseline = float(np.median([_chroma_shift(frames[i]) for i in ref_idx])) if ref_idx else 0.0
    if shift > max(1.5, 2.5 * baseline + 0.8):
        evidence["deslocamento_rgb_px"] = r(shift, 2)
        evidence["deslocamento_normal_px"] = r(baseline, 2)
        return "glitch", 0.6, evidence

    before, after = frames[max(0, s - 1)], frames[e]
    if hard:
        blur = _blur_window(frames, s, e, fps)
        if blur:
            a, b = blur.pop("inicio"), blur.pop("fim")
            evidence.update(blur, quadros_borrados=b - a + 1, _span=(a, b))
            ratio = blur["sobel_x_y"]
            if ratio < 0.6 or ratio > 1.7:
                evidence["direcao"] = "horizontal" if ratio < 0.6 else "vertical"
                return "whip-pan", 0.6, evidence
            if abs(blur["divergencia"]) > 0.004:
                return ("zoom-in" if blur["divergencia"] > 0 else "zoom-out"), 0.6, evidence
            return "radial-blur", 0.5, evidence
        (scale, score), base = _zoom_match(before, after)
        if scale > 1.0 and score > 0.72 and score > base + 0.12:
            evidence["escala"] = scale
            return "punch-in", r(min(0.95, score), 2), evidence
        (scale, score), base = _zoom_match(after, before)
        if scale > 1.0 and score > 0.72 and score > base + 0.12:
            evidence["escala"] = scale
            return "punch-out", r(min(0.95, score), 2), evidence
        part = _partial_cut(before, after)
        if part:
            evidence.update(part)
            return "troca de insert (tela dividida)", 0.7, evidence
        if _hdist(_hist(before), _hist(after)) < 0.16:
            return "jump cut", 0.6, evidence
        return "corte seco", 0.9, evidence

    A = frames[pre].astype(np.float32)
    B = frames[post].astype(np.float32)
    M = frames[(s + e) // 2].astype(np.float32)
    denom = float(((A - B) ** 2).sum())
    if denom > 0:
        alpha = float(np.clip(((M - B) * (A - B)).sum() / denom, 0, 1))
        rel = float(np.abs(M - (alpha * A + (1 - alpha) * B)).mean() / max(1e-3, np.abs(A - B).mean()))
        evidence["residuo_dissolve"] = r(rel, 2)
        if rel < 0.25 and 0.1 < alpha < 0.9:
            return "cross-dissolve", r(0.95 - rel, 2), evidence

    mid = (s + e) // 2
    a, b = frames[max(0, mid - 1)], frames[min(n - 1, mid + 1)]
    mu, mv, div = _flow(a, b)
    sx_mid, sy_mid = _sharp(frames[mid])
    sx_ref = (_sharp(frames[pre])[0] + _sharp(frames[post])[0]) / 2
    sy_ref = (_sharp(frames[pre])[1] + _sharp(frames[post])[1]) / 2
    blur_x = sx_mid / max(1e-3, sx_ref)
    blur_y = sy_mid / max(1e-3, sy_ref)
    evidence.update(fluxo_x=r(mu, 2), fluxo_y=r(mv, 2), divergencia=r(div, 4),
                    nitidez_x=r(blur_x, 2), nitidez_y=r(blur_y, 2))
    if min(blur_x, blur_y) < 0.55 and abs(div) > 0.01:
        return "radial-blur" if blur_x < 0.55 and blur_y < 0.55 else ("zoom-in" if div > 0 else "zoom-out"), 0.5, evidence
    if blur_x < 0.5 and blur_x < blur_y * 0.75:
        evidence["direcao"] = "horizontal"
        return "whip-pan", 0.6, evidence
    if blur_y < 0.5 and blur_y < blur_x * 0.75:
        evidence["direcao"] = "vertical"
        return "whip-pan", 0.6, evidence
    if abs(div) > 0.015:
        return ("zoom-in" if div > 0 else "zoom-out"), 0.5, evidence
    if evidence.get("residuo_dissolve", 1) < 0.4:
        return "cross-dissolve", 0.5, evidence
    # mesma cena antes e depois, sem blur/zoom/dissolve: emenda do próprio material
    # (morph entre trechos de vídeo gerado por IA, estabilização, troca de take quase igual)
    if _hdist(_hist(frames[pre]), _hist(frames[post])) < 0.2:
        return "emenda na fonte (morph)", 0.4, evidence
    return "gradual (verificar)", 0.3, evidence


def _shake_after(frames, e, fps) -> float:
    """Tremor logo após o corte: média do deslocamento entre frames consecutivos (px a 96px)."""
    span = frames[e:min(len(frames), e + max(3, int(fps * 0.4)))]
    shifts = []
    for a, b in zip(span, span[1:]):
        (dx, dy), _ = cv2.phaseCorrelate(_gray(a).astype(np.float32), _gray(b).astype(np.float32))
        shifts.append(np.hypot(dx, dy))
    return float(np.mean(shifts)) if shifts else 0.0


def detect(src, info: dict, width=96) -> dict:
    frames, times = decode(src, info, width=width)
    n, fps = len(frames), info.get("fps") or 30.0
    if n < 3:
        return {"planos": [], "transicoes": [], "estatisticas": {}}
    luma = np.array([(0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]).mean() / 255 for f in frames])
    hists = [_hist(f) for f in frames]
    d = np.zeros(n)
    hd = np.zeros(n)
    for i in range(1, n):
        d[i] = _diff(frames[i - 1], frames[i])
        hd[i] = _hdist(hists[i - 1], hists[i])

    # cortes secos: pico isolado frente à vizinhança (limiar adaptativo)
    win = max(4, int(round(fps * 0.25)))
    spikes = []
    for i in range(1, n):
        nb = np.r_[d[max(1, i - win):i], d[i + 1:i + 1 + win]]
        nbh = np.r_[hd[max(1, i - win):i], hd[i + 1:i + 1 + win]]
        base = (np.median(nb) if nb.size else 0) + 0.004
        baseh = (np.median(nbh) if nbh.size else 0) + 0.02
        if (d[i] >= 0.035 and d[i] / base >= 3.5) or (hd[i] >= 0.35 and hd[i] / baseh >= 2.5):
            spikes.append(i)
    clusters = []
    gap = max(3, int(round(fps * 0.15)))
    for i in spikes:
        if clusters and i - clusters[-1][-1] <= gap:
            clusters[-1].append(i)
        else:
            clusters.append([i])
    events = [(c[0], c[-1], True) for c in clusters]
    hard_idx = [i for c in clusters for i in c]

    # transições graduais: rajada de mudança entre dois trechos calmos
    k = max(3, int(round(fps * 0.2)))
    D = np.zeros(n)
    for i in range(k, n - k):
        D[i] = _diff(frames[i - k], frames[i + k])
    for i in range(3 * k, n - 3 * k):
        if D[i] < 0.08 or D[i] < D[i - k:i + k + 1].max():
            continue
        if any(abs(i - h) <= 2 * k for h in hard_idx):
            continue
        inside = d[i - k:i + k + 1].mean()
        outside = (d[i - 3 * k:i - k].mean() + d[i + k + 1:i + 3 * k + 1].mean()) / 2
        if inside < 2 * outside + 0.003:
            continue
        thr = max(0.006, 0.4 * d[i - k:i + k + 1].max())
        idx = [j for j in range(i - 2 * k, i + 2 * k + 1) if d[j] > thr]
        s, e = (idx[0], idx[-1]) if idx else (i - k, i + k)
        if not any(abs(s - es) <= k for es, _, _ in events):
            events.append((s, e, False))
    events.sort()

    # une eventos vizinhos separados por um trecho preto/branco (fade pelo preto, flash)
    merged = []
    max_gap = int(fps * 0.8)
    for s, e, hard in events:
        if merged:
            ps, pe, ph = merged[-1]
            between = luma[pe:s + 1]
            if s - pe <= max_gap and between.size and (between.min() < 0.08 or between.max() > 0.85):
                merged[-1] = (ps, e, False)
                continue
        merged.append((s, e, hard))
    events = merged

    # pico de corte que na verdade é o meio de um dissolve
    for idx, (s, e, hard) in enumerate(events):
        if hard:
            span = _blend_span(frames, s, e, k)
            if span and span[1] - span[0] >= 2:
                events[idx] = (min(s, span[0]), max(e, span[1]), False)

    transitions = []
    for s, e, hard in events:
        kind, conf, ev = _classify(frames, luma, s, e, fps, hard)
        shake = _shake_after(frames, e, fps)
        cut_time = times[s] if hard and s == e else r((times[s] + times[e]) / 2)
        span = ev.pop("_span", None)
        if span:  # corte escondido por borrão: a transição dura o bloco borrado
            s, e, hard = span[0], span[1], False
        item = {
            "tempo": cut_time,
            "inicio": times[max(0, s - 1)] if hard else times[s],
            "fim": times[e],
            "duracao": r(0 if hard and s == e else (e - s + 1) / fps),
            "tipo": kind,
            "tipo_openchatcut": OPENCHATCUT_TRANSITION.get(kind),
            "confianca": conf,
            "detalhes": ev,
        }
        if shake > 1.5:
            item["tremor_apos"] = r(shake, 2)
        transitions.append(item)

    # emendas do material não são cortes de edição; trocas de insert contam (há corte, só que em metade da tela)
    edits = [t for t in transitions if t["tipo"] != "emenda na fonte (morph)"]
    bounds = [0.0] + [t["tempo"] for t in edits] + [info["duracao"]]
    shots = [{"n": i + 1, "inicio": r(a), "fim": r(b), "duracao": r(b - a)}
             for i, (a, b) in enumerate(zip(bounds, bounds[1:])) if b - a > 0.02]
    durs = np.array([s["duracao"] for s in shots]) if shots else np.array([info["duracao"]])
    total = info["duracao"]
    quarters = []
    for q in range(4):
        a, b = total * q / 4, total * (q + 1) / 4
        cuts_in = sum(1 for t in edits if a <= t["tempo"] < b)
        quarters.append({"trecho": f"{r(a, 1)}-{r(b, 1)}s", "cortes": cuts_in,
                         "plano_medio": r((b - a) / (cuts_in + 1), 2)})
    types = {}
    for t in transitions:
        types[t["tipo"]] = types.get(t["tipo"], 0) + 1
    stats = {
        "planos": len(shots),
        "transicoes": len(edits),
        "emendas_na_fonte": len(transitions) - len(edits),
        "cortes_por_minuto": r(len(edits) / max(0.1, total) * 60, 1),
        "plano_medio": r(durs.mean(), 2),
        "plano_mediano": r(np.median(durs), 2),
        "plano_mais_curto": r(durs.min(), 2),
        "plano_mais_longo": r(durs.max(), 2),
        "cortes_nos_3s_iniciais": sum(1 for t in edits if t["tempo"] < 3.0),
        "por_tipo": types,
        "ritmo_por_quarto": quarters,
    }
    return {"planos": shots, "transicoes": transitions, "estatisticas": stats}
