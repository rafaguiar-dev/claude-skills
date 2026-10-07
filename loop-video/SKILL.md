---
name: loop-video
description: Gera um vídeo em loop (padrão 2:30) de um personagem falando a partir de UMA imagem — Kling 2.6 10 s + Kling 2.5 5 s na Magnific (MCP) e emenda/loop com ffmpeg local. Use quando o usuário pedir /loop-video, "loop dessa imagem", "vídeo em loop do personagem", "gera o loop", ou passar imagens de avatar/apresentador pra virar vídeo de fundo de VSL. Aceita uma imagem ou uma pasta (lote).
---

# loop-video

Projeto: `C:\Users\Rafek\Desktop\IMPETUS\loop-video\`
Config: `config.json` (modelos, cortes, pasta de saída, projeto na Magnific). Prompts (não estão mais no config; são os mesmos do license server):
- homem: `a man talking calmly to the camera, subtle natural lip movement, relaxed eyebrows, gentle small head movements, soft friendly expression, hands mostly still, static camera, no zoom, no exaggerated expressions`
- mulher: `a woman talking calmly to the camera, subtle natural lip movement, relaxed eyebrows, gentle small head movements, soft friendly expression, hands mostly still, static camera, no zoom, no exaggerated expressions`
- negativo: `exaggerated expressions, wide open mouth, raised eyebrows, surprised face, laughing, big gestures, camera movement, zoom, muscular neck, thick neck, tense neck muscles, bulging veins, strained neck, clenched jaw, distorted anatomy, body morphing, changing body shape`
Script local: `looper.py` (ffmpeg — probe / prep / build / qc)

Custo: 900 créditos por vídeo final (450 + 450). Tempo: ~3–10 min por geração Kling; ffmpeg < 3 min.

## Entrada

- `IMAGEM` — caminho de um PNG/JPG/WebP (≤ 25 MB), ou pasta → processa cada imagem em lote.
- **Sem argumento** → processa tudo que estiver em `C:\Users\Rafek\Desktop\IMPETUS\loop-video\inbox\` (a "caixa de entrada": o usuário só solta as imagens lá e digita `/loop-video`). Depois de processar, mover a imagem de `inbox/` para a pasta do job (`00_input.<ext>`).
- Opcional: `homem` | `mulher` | prompt livre entre aspas | `--target 150` (segundos) | `--trim 4` | `--head 10`.
- Sem gênero: olhar a imagem (Read numa prévia reduzida) e escolher `homem`/`mulher`; se não der pra saber, `default`.
- Aspect: **não** adivinhar — ler com `ffprobe` e mapear: w/h ≈ 1.78 → `16:9`, ≈ 0.56 → `9:16`, ≈ 0.8 (4:5) → passar `9:16`
  (o Kling ignora o campo e segue a imagem inicial; validar o tamanho do MP4 no probe e avisar se divergir).

## Pipeline (por imagem)

Pasta de trabalho: `<saida.root>/<nome-da-imagem-sem-extensão>/`. Copiar a imagem como `00_input.<ext>`.

1. **Upload da imagem** → `creations_request_upload {mimeType}` → `curl -X PUT -H "Content-Type: <mime>" --data-binary @arquivo <proxyUploadUrl>` → `creations_finalize_upload {path, folderReference}` → guardar `identifier` (ID_IMG).
   Se o PUT falhar, pedir URL nova (não re-PUT).
2. **Kling 2.6, 10 s** → `video_generate {slug:"kling-26", duration:10, resolution:"1080p", aspectRatio, prompt: <prompts[gênero]>, negativePrompt: <prompt_negativo>, keyframes:{start:{type:"image", url:ID_IMG}}, withSoundEffects:false, folderReference}` → ID_10.
3. `creations_wait [ID_10]` em loop (timeoutSeconds 25) até `completed`. Pegar `url` (asset). Baixar: `curl -L -o 01_kling26_10s.mp4 "<url>"`.
4. **Cortes + frames de emenda (fluxo v2, 21/09/2026)** → `python looper.py prep2 01_kling26_10s.mp4 --out-dir <pasta> --trim-frames 4 --head-trim 10`
   → tira os 10 primeiros frames do principal (o Kling "acorda" neles) e gera `02_frame_fim.png` (ÚLTIMO frame do principal, antes
   do corte do fim), `02_frame_inicio.png` (PRIMEIRO frame mantido, o de índice 10) e `revisao_principal.mp4` (só o trecho mantido).
   Anotar `keep10`. **Mostrar `revisao_principal.mp4` ao usuário e esperar aprovação** (aprovar / regerar / regerar com prompt novo) antes de gastar na ponte.
5. **Upload dos dois frames** (passo 1 de novo, `visible:false` no finalize) → ID_FIM, ID_INICIO.
6. **Kling 2.5, 5 s** → `video_generate {slug:"kling-25", duration:5, resolution:"1080p", aspectRatio, prompt: <prompts[gênero]> (O MESMO prompt do passo 2), negativePrompt: <prompt_negativo>, keyframes:{start:{type:"image", url:ID_FIM}, end:{type:"image", url:ID_INICIO}}, folderReference}` → ID_5 (325 créditos). Decisão do usuário 22/09/2026 após comparar 2.6+3.0, 2.5+2.5 e 2.6+2.5: a ponte do Kling 3.0 "arranca" rápido nos primeiros frames e fala num ritmo mais acelerado que o principal; a do 2.5 não. O principal fica no 2.6 (`withSoundEffects:false`, 450 créditos).
   Ponte = do último frame do principal até o primeiro frame mantido; o mesmo prompt nas duas gerações é o que faz o ritmo bater. O negative prompt continua nas duas: o Kling 3.0 tende a atuar mais forte que o 2.6.
7. `creations_wait [ID_5]` até `completed` → baixar `03_kling30_5s.mp4`.
8. **Montagem** → `python looper.py build2 --clip10 01_kling26_10s.mp4 --clip5 03_kling30_5s.mp4 --out-dir <pasta> --head-trim 10 --target T --sem-final`
   → `04_loop_unit.mp4` + `05_previa_20s.mp4`. A emenda é **automática**: o looper mede a diferença entre os candidatos a par de
   emenda (8 frames em cada ponta) e escolhe o par de menor salto (na prática: principal inteiro a partir do frame 10 + ponte inteira,
   porque a ponte nasce do último frame e termina no primeiro mantido); e corrige a **cor da ponte** com uma rampa linear (ganho de luma +
   offset de croma) pra bater com o fim e com o começo do principal — os modelos derivam brilho ao longo do clipe (medido: ~2% entre
   Kling 2.6 e 3.0). O JSON diz `emenda1`/`emenda2` (frames e diferença) e `cor`; diferença ≤ ~3 = nível de movimento normal.
   NÃO cortar os 4 últimos frames do principal (era do fluxo antigo; aqui gera um salto de 4 frames de movimento na emenda).
   **Mostrar a prévia de 20 s ao usuário** (dá pra ver as duas emendas) e esperar aprovação; se reprovar, regerar SÓ a ponte (passo 6, mesmo prompt ou o que ele mandar). Aprovado → rodar de novo sem `--sem-final` → `FINAL_2m30.mp4` (`ok: true` = contagem de frames bateu).
9. **QC** (dois checks, os dois obrigatórios antes de entregar):
   a. Emendas → `python looper.py qc --unit 04_loop_unit.mp4 --keep10 <keep10> --out qc_emendas.png`
      Linha 1 = emenda 10s→5s, linha 2 = volta do loop. As duas metades de cada linha têm que parecer frames consecutivos.
   b. Intensidade de expressão → `python looper.py faces --clip10 01_kling26_10s.mp4 --clip5 03_kling30_5s.mp4 --out qc_faces.png`
      Linhas de cima = rosto do 10 s a 2 fps; linhas de baixo = rosto do 5 s. Ler a imagem e comparar: se o 5 s tem boca escancarada / sobrancelhas arqueadas / "cara de surpresa" enquanto o 10 s está calmo, o loop vai parecer estranho.
   Se (a) tem salto ou (b) tem intensidade discrepante: regerar SÓ o 5 s uma vez (mesmos keyframes, mesmo prompt). Se persistir, regerar o 5 s com `slug:"kling-26"` (mesmo "estilo de atuação" do 10 s). Não passar de 2 regerações (900 créditos extras) sem avisar o usuário.
   Frames (24 fps, típico): principal 241 → mantém 10..240 (231); ponte 121 inteira; unidade 352; FINAL 2:30 = 3600 frames (11 repetições cortadas).
10. **job.json** na pasta: imagem, gênero, prompts usados (incl. negativo), modelos, identifiers das creations (imagem, frame, 10 s, 5 s — e regerações), keep10/keep5/unit_frames/reps/target, créditos gastos, datas.

Em lote: rodar passos 1–3 de todas as imagens primeiro (as gerações rodam em paralelo na Magnific), depois 4–7 de todas, depois 8–10. `creations_wait` aceita até 8 IDs por chamada.

## Entrega

Responder curto: pasta, nome do FINAL, duração/frames confirmados, custo gasto, e mostrar `qc_emendas.png` e `qc_faces.png` (SendUserFile). Não citar identifiers internos.
Se o usuário pediu "só o resultado", não narrar etapas intermediárias.

## Erros comuns

- `creations_wait` devolveu `failed` → tentar gerar de novo 1x com os mesmos parâmetros; se falhar de novo, parar e avisar (não gastar mais crédito).
- MP4 do Kling com tamanho diferente da imagem (ex.: 1072×1928): normal; o `build` escala o clip de 5 s pra bater com o de 10 s.
- fps ≠ 24 em um dos clipes: o `build` converte pro fps do clip de 10 s; conferir `unit.frames` no JSON.
- Imagem > 25 MB: reduzir com `ffmpeg -i in.png -vf scale=iw:ih -compression_level 9 out.png` ou salvar como JPG q=95 antes do upload.
