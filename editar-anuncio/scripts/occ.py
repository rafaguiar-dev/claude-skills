"""occ — controla o OpenChatCut (MCP HTTP + janela do app via CDP) e contorna os defeitos do v0.2.15 no Windows.

Uso (via o wrapper `occ` desta skill):
  occ abrir [PROJETO_ID]            abre o app (com porta de depuração) e, se dado, o editor do projeto
  occ novo-projeto NOME             cria projeto 1080x1920 30fps e abre no editor
  occ sessao                        vincula ao projeto aberto e inicia sessão de edição (auto)
  occ aplicar                       aplica a sessão atual e inicia outra
  occ tools [NOME]                  lista ferramentas (ou o schema de uma)
  occ call FERRAMENTA JSON|@arq     chama uma ferramenta (editSessionId é injetado)
  occ corrigir-midia                copia mídia referenciada para o app e troca o junction do render por hardlinks
  occ transcricao ITEM_NOME TRANSCRIPT.json [--ate SEG] [--projeto ID]
                                    injeta transcrição (formato ref.transcript@1) no(s) clipe(s) com esse nome;
                                    --ate SEG adiciona uma palavra invisível no fim do trecho usado (evita a
                                    última página de legenda ficar 1,5 s a mais na tela)
  occ paginar [--max-chars 17] [--max-palavras 3]
                                    quebra as páginas da legenda pelo comprimento (como CapCut)
  occ quadros SEG[,SEG...] --para arq.jpg   renderiza quadros da timeline lado a lado
  occ exportar SAIDA.mp4 [--nome X]  renderiza em WebM (o MP4 do app quebra: falta libfdk_aac) e converte
  occ copy ARQUIVO.docx             extrai o texto da copy (parágrafos)
"""
import base64
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

HOME = Path.home()
OCC_DIR = HOME / ".openchatcut"
APPDATA = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming")) / "openchatcut"
EXE = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local")) / "Programs/OpenChatCut/OpenChatCut.exe"
STATE = HOME / ".openchatcut" / "occ-cli-state.json"
CDP_PORT = 9223
NO_SESSION_TOOLS = {"openchatcut_status", "list_projects", "target_project", "begin_edit_session", "load_skill",
                    "create_project", "get_editor_url", "list_edit_sessions", "recover_edit_session"}


# ------------------------------------------------------------------ estado local

def _state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(**kw):
    st = _state()
    st.update(kw)
    STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")


def log(*a):
    print("[occ]", *a, file=sys.stderr, flush=True)


# ------------------------------------------------------------------ MCP (streamable HTTP)

def _url():
    port = (OCC_DIR / "mcp-port").read_text().strip() if (OCC_DIR / "mcp-port").exists() else "5199"
    return f"http://localhost:{port}/api/external-mcp/mcp"


def _post(body, sid=None):
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
         "Authorization": "Bearer " + (OCC_DIR / "mcp-token").read_text().strip()}
    if sid:
        h["Mcp-Session-Id"] = sid
    req = urllib.request.Request(_url(), data=json.dumps(body).encode(), headers=h, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=900)
        return resp.status, resp.headers, resp.read().decode("utf8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read().decode("utf8", "replace")


def _parse(text):
    text = text.strip()
    if not text:
        return None
    if text.startswith("{"):
        return json.loads(text)
    out = None
    for line in text.splitlines():
        if line.startswith("data:") and line[5:].strip():
            j = json.loads(line[5:].strip())
            if "result" in j or "error" in j:
                out = j
    return out


def _mcp_session(fresh=False):
    st = _state()
    if st.get("mcp_sid") and not fresh:
        return st["mcp_sid"]
    _, hd, _ = _post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "claude-occ", "version": "1"}}})
    sid = hd.get("Mcp-Session-Id") or hd.get("mcp-session-id") or ""
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    _save(mcp_sid=sid)
    return sid


def rpc(method, params, _retry=True):
    st, _, tx = _post({"jsonrpc": "2.0", "id": 2, "method": method, "params": params}, _mcp_session())
    if st in (400, 404) and _retry:
        _mcp_session(fresh=True)
        return rpc(method, params, False)
    j = _parse(tx)
    if j is None:
        raise SystemExit(f"HTTP {st}: {tx[:400]}")
    return j


def call(tool, args=None, raw=False):
    """Chama uma ferramenta; devolve o JSON do primeiro bloco de texto (ou o texto) e salva imagens."""
    args = dict(args or {})
    if tool not in NO_SESSION_TOOLS and "editSessionId" not in args and _state().get("esid"):
        args["editSessionId"] = _state()["esid"]
    j = rpc("tools/call", {"name": tool, "arguments": args})
    if "error" in j:
        raise RuntimeError(json.dumps(j["error"], ensure_ascii=False))
    res = j["result"]
    if raw:
        return res
    texts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
    body = texts[0] if texts else ""
    try:
        data = json.loads(body)
    except Exception:
        data = body
    if isinstance(data, dict) and data.get("outcome") == "stale" and tool != "target_project":
        log("sessão MCP velha: revinculando")
        _mcp_session(fresh=True)
        start_session()
        return call(tool, args if tool in NO_SESSION_TOOLS else {k: v for k, v in args.items() if k != "editSessionId"}, raw)
    if res.get("isError"):
        raise RuntimeError(body[:2000])
    return data


# ------------------------------------------------------------------ janela do app (CDP)

def _cdp_page():
    pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5))
    return [p for p in pages if p["type"] == "page" and "transcript-window" not in p["url"]][0]


def cdp_eval(expr):
    import websocket
    ws = websocket.create_connection(_cdp_page()["webSocketDebuggerUrl"], timeout=60, suppress_origin=True)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def _cdp_alive():
    try:
        _cdp_page()
        return True
    except Exception:
        return False


def open_app(project=None):
    if not _cdp_alive():
        running = subprocess.run(["tasklist", "/FI", "IMAGENAME eq OpenChatCut.exe"], capture_output=True,
                                 text=True).stdout
        if "OpenChatCut.exe" in running:
            log("app aberto sem porta de depuração: reiniciando")
            subprocess.run(["taskkill", "/F", "/IM", "OpenChatCut.exe"], capture_output=True)
            time.sleep(3)
        subprocess.Popen([str(EXE), f"--remote-debugging-port={CDP_PORT}"], creationflags=0x00000008)
        for _ in range(60):
            time.sleep(1)
            if _cdp_alive():
                break
        else:
            raise SystemExit("app não abriu a porta de depuração")
        time.sleep(3)
    if project:
        cdp_eval(f"location.hash='#/editor/{project}'; 'ok'")
        for _ in range(40):
            time.sleep(1)
            st = call("openchatcut_status")
            if project in (st.get("connectedProjectIds") or []):
                break
        _save(project=project)
        log("editor aberto:", project)


def close_editor():
    """Volta a janela para o painel (o editor salva e larga o projeto)."""
    cdp_eval("location.hash='#/'; 'ok'")
    time.sleep(4)


def start_session():
    st = _state()
    project = st.get("project")
    if not project:
        raise SystemExit("nenhum projeto: use `occ abrir ID` ou `occ novo-projeto NOME`")
    call("target_project", {"projectId": project})
    sessions = call("list_edit_sessions")
    for s in (sessions.get("result") if isinstance(sessions, dict) else sessions) or []:
        if s.get("status") == "drafting":
            actions = s.get("recoveryActions") or []
            if "discard" in actions:
                call("recover_edit_session", {"editSessionId": s["editSessionId"], "action": "discard"})
            else:
                try:  # sessão de outro cliente (ex.: execução anterior do occ) ainda aberta
                    call("discard_edit_session", {"editSessionId": s["editSessionId"]})
                except RuntimeError as exc:
                    log("não consegui descartar", s["editSessionId"], str(exc)[:200])
    res = call("begin_edit_session", {"clientName": "Claude", "approvalMode": "auto"})
    _save(esid=res["editSessionId"])
    log("sessão", res["editSessionId"], res.get("status"))
    return res["editSessionId"]


def apply_session():
    res = call("review_edit_session")
    log("aplicado:", res.get("status"), "operações:", res.get("appliedOperationCount"))
    start_session()
    return res


# ------------------------------------------------------------------ contornos de mídia

def fix_media():
    """1) importações de outro disco viram ponteiros (.references): copia os bytes para uploads/;
    2) o junction remotion-bundle/media/uploads não é seguido pelo Node → pasta real com hardlinks."""
    up = APPDATA / "public/media/uploads"
    refs = up / ".references"
    backup = APPDATA / "public/media/refs-backup"
    backup.mkdir(exist_ok=True)
    for j in list(refs.glob("*.json")) if refs.exists() else []:
        src = Path(json.loads(j.read_text(encoding="utf-8"))["sourcePath"])
        dst = up / j.name[:-5]
        if not dst.exists():
            shutil.copy2(src, dst)
        shutil.move(str(j), str(backup / j.name))
        log("copiado", src.name, "->", dst.name)
    for bundle in APPDATA.glob("remotion-bundle-*"):
        media = bundle / "media/uploads"
        if media.is_junction() if hasattr(media, "is_junction") else os.path.islink(media):
            subprocess.run(["cmd", "/c", "rmdir", str(media)], capture_output=True)
        media.mkdir(parents=True, exist_ok=True)
        (media / "export-references").mkdir(exist_ok=True)
        for f in up.iterdir():
            if f.is_file() and not (media / f.name).exists():
                os.link(f, media / f.name)
        log("render enxerga", sum(1 for _ in media.iterdir()), "arquivos em", media)


# ------------------------------------------------------------------ transcrição

def _words(transcript_path, until=None):
    t = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
    out = []
    for seg in t["segmentos"]:
        for w in seg["palavras"]:
            txt = re.sub(r'[.,!?;:"„“”]+', "", w["texto"].strip().lstrip("-"))
            if txt:
                out.append({"text": txt, "start": int(round(w["inicio"] * 1000)), "end": int(round(w["fim"] * 1000)),
                            "confidence": round(w.get("prob", 1), 3), "speaker": "A", "id": "tw" + secrets.token_hex(6)})
    for a, b in zip(out, out[1:]):
        b["start"] = max(b["start"], a["end"])
        b["end"] = max(b["end"], b["start"])
    if until is not None:
        # palavra invisível logo antes do fim do trecho: vira a última página (vazia) da fonte
        ms = int(until * 1000)
        last = max([w["end"] for w in out if w["end"] <= ms] or [0])
        out = [w for w in out if w["end"] <= ms or w["start"] >= ms]
        out.append({"text": "​", "start": max(last, ms - 70), "end": ms, "confidence": 1, "speaker": "A",
                    "id": "tw" + secrets.token_hex(6)})
        out.sort(key=lambda w: w["start"])
    return out


def inject_transcript(item_name, transcript_path, until=None, project=None):
    project = project or _state().get("project")
    path = OCC_DIR / "project-store-v1" / f"project%3A{project}.json"
    close_editor()
    data = json.loads(path.read_text(encoding="utf-8"))
    shutil.copy2(path, path.with_suffix(f".bak-{int(time.time())}.json"))
    words = _words(transcript_path, until)
    hit = 0
    for tl in data["timelines"]:
        for it in tl["items"]:
            if it.get("name") == item_name:
                it["transcript"] = [dict(w) for w in words]
                it["transcriptGenerationId"] = "tg" + secrets.token_hex(6)
                it.pop("transcriptStale", None)
                hit += 1
    if not hit:
        raise SystemExit(f"nenhum clipe chamado {item_name!r} na timeline")
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    log(f"transcrição com {len(words)} palavras em {hit} clipe(s) '{item_name}'")
    open_app(project)
    _save(mcp_sid=None)
    start_session()


# ------------------------------------------------------------------ paginação da legenda

def read_captions_full(track=None):
    args = {"captionTrackId": track} if track else {}
    res = call("read_captions", args)
    if isinstance(res, dict) and res.get("archived"):
        chunks, off = [], 0
        while True:
            part = call("read_agent_artifact", {"artifactId": res["artifactId"], "offset": off, "limit": 12000})
            chunks.append(part["content"])
            if not part.get("hasMore"):
                break
            off = part["nextOffset"]
        res = json.loads("".join(chunks))
    return res


def paginate(max_chars, max_words=3, track=None):
    """Quebra as páginas da legenda pelo comprimento, como nas legendas de CapCut: a página cresce
    enquanto couber em `max_chars` caracteres e `max_words` palavras. O OpenChatCut só quebra por
    número de palavras (e um limite fixo de 24 caracteres/linha), então forçamos as quebras palavra a palavra."""
    cap = read_captions_full(track)
    lanes = {}
    for page in cap["pages"]:
        for w in page["words"]:
            lane = w["wordRef"].split("%2C")[1] if "%2C" in w["wordRef"] else "single"
            lanes.setdefault(lane, []).append(w)
    overrides = []
    pages = 0
    for words in lanes.values():
        cur_chars, cur_n = 0, 0
        for w in words:
            text = (w.get("override") or {}).get("text") or w["text"]
            if not text.replace("​", "").strip():  # palavra invisível de fim de trecho
                continue
            add = len(text) + (1 if cur_n else 0)
            if cur_n and (cur_chars + add > max_chars or cur_n >= max_words):
                overrides.append({"wordRef": w["wordRef"], "forcePageBreak": True})
                pages += 1
                cur_chars, cur_n = len(text), 1
            else:
                cur_chars, cur_n = cur_chars + add, cur_n + 1
    for i in range(0, len(overrides), 200):
        call("edit_captions", {"action": "display_text", **({"captionTrackId": track} if track else {}),
                               "json": json.dumps({"overrides": overrides[i:i + 200]})})
    log(f"{pages} quebras forçadas (≤{max_chars} caracteres, ≤{max_words} palavras por página)")


# ------------------------------------------------------------------ quadros / export / copy

def frames(seconds, to):
    from PIL import Image
    tmp = []
    for s in seconds:
        res = call("view_timeline_frames", {"seconds": [s]}, raw=True)
        img = [c for c in res.get("content", []) if c.get("type") == "image"]
        if not img:
            raise RuntimeError(json.dumps(res)[:800])
        p = Path(to).with_suffix(f".{len(tmp)}.jpg")
        p.write_bytes(base64.b64decode(img[0]["data"]))
        tmp.append(p)
    ims = [Image.open(p) for p in tmp]
    h = max(i.height for i in ims)
    sheet = Image.new("RGB", (sum(i.width for i in ims), h))
    x = 0
    for i in ims:
        sheet.paste(i, (x, 0))
        x += i.width
    sheet.save(to, quality=90)
    for p in tmp:
        p.unlink()
    print(to)


def export(out_mp4, name=None):
    res = call("submit_render_job", {"format": "video", "codec": "vp8", "videoBitrate": 12000000,
                                     "name": name or Path(out_mp4).stem + ".webm"})
    rid = res["renderId"]
    log("render", rid)
    while True:
        st = call("track_export", {"renderIds": rid, "action": "wait", "timeoutSeconds": 300})
        log("render", st.get("status"), st.get("progress"))
        if st.get("status") not in ("running", "queued"):
            break
    if st.get("status") != "completed":
        raise SystemExit(f"render falhou: {json.dumps(st, ensure_ascii=False)[:1500]}")
    webm = APPDATA / "public" / st["downloadUrl"].lstrip("/")
    Path(out_mp4).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(webm), "-c:v", "libx264", "-crf", "18", "-preset",
                    "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                    str(out_mp4)], check=True)
    print(Path(out_mp4).resolve())


def read_copy(docx):
    z = zipfile.ZipFile(docx)
    xml = z.read("word/document.xml").decode("utf8")
    for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        t = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))
        t = t.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        if t.strip():
            print(t)


# ------------------------------------------------------------------ CLI

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest = a[0], a[1:]

    def opt(flag, default=None):
        if flag in rest:
            i = rest.index(flag)
            v = rest[i + 1]
            del rest[i:i + 2]
            return v
        return default

    if cmd == "abrir":
        open_app(rest[0] if rest else None)
        if rest:
            start_session()
    elif cmd == "novo-projeto":
        open_app()
        res = call("create_project", {"name": " ".join(rest), "compositionWidth": 1080,
                                      "compositionHeight": 1920, "fps": 30})
        print(json.dumps(res, ensure_ascii=False))
        open_app(res["id"])
        start_session()
    elif cmd == "sessao":
        start_session()
    elif cmd == "aplicar":
        print(json.dumps(apply_session(), ensure_ascii=False))
    elif cmd == "tools":
        tools = rpc("tools/list", {})["result"]["tools"]
        for t in tools:
            if rest and t["name"] == rest[0]:
                print(json.dumps(t, indent=1, ensure_ascii=False))
            elif not rest:
                print("-", t["name"], ":", (t.get("description") or "")[:140].replace("\n", " "))
    elif cmd == "call":
        arg = rest[1] if len(rest) > 1 else "{}"
        args = json.loads(Path(arg[1:]).read_text(encoding="utf-8")) if arg.startswith("@") else json.loads(arg)
        res = call(rest[0], args)
        print(json.dumps(res, ensure_ascii=False, indent=1) if not isinstance(res, str) else res)
    elif cmd == "corrigir-midia":
        fix_media()
    elif cmd == "transcricao":
        until = opt("--ate")
        project = opt("--projeto")
        inject_transcript(rest[0], rest[1], float(until) if until else None, project)
    elif cmd == "paginar":
        mc = int(opt("--max-chars", "17"))
        mw = int(opt("--max-palavras", "3"))
        paginate(mc, mw, opt("--trilha"))
    elif cmd == "quadros":
        to = opt("--para", "quadros.jpg")
        frames([float(x) for x in rest[0].split(",")], to)
    elif cmd == "exportar":
        name = opt("--nome")
        export(rest[0], name)
    elif cmd == "copy":
        read_copy(rest[0])
    else:
        print(__doc__)
        raise SystemExit(f"comando desconhecido: {cmd}")


if __name__ == "__main__":
    main()
