# Receitas OpenChatCut (v0.2.15) — testadas no AD71 (2026-09-29)

Todas as chamadas via `$OCC call <ferramenta> '<json>'`. Parâmetros `json` de `edit_track` e `edit_captions`
são **strings** JSON (JSON dentro de string).

## Timeline básica
```json
{"adds":[
 {"type":"video","assetId":"<HOOKS>","track":"V1","fromFrame":0,"sourceStartFrame":0,"sourceDurationInFrames":242},
 {"type":"video","assetId":"<BODY>","track":"V1","fromFrame":242,"sourceStartFrame":0,"sourceDurationInFrames":3402}]}
```
- V2: `edit_track {"action":"create","json":"{\"trackType\":\"video\"}"}`. Áudio (SFX): idem com `"audio"`.
- Bruto 720×1254 num canvas 1080×1920 fica com faixa preta de ~1%: `transform.scale: 1.03` nos clipes.

## Tela dividida (insert embaixo, rosto em cima)
- Gere o insert como vídeo 1080×1920 com a imagem já na metade de baixo (em cima preto) e corte o topo
  transparente: `{"type":"video","itemId":"<insert>","transform":{"flexCrop":{"top":930}},"volume":0}`.
  930 px = divisória em y≈0,485 (use a `linha_divisoria` do `ref analisar` × 1920).
- A V1 (talking head em tela cheia) mostra naturalmente a cabeça na metade de cima.

## Legendas (estilo CapCut: caixa alta, contorno, palavra falada colorida)
1. Transcrição boa: `$OCC transcricao <clipe> <transcript.json> --ate <fim usado>` para cada clipe falado.
   Sem `--ate`, a última página de cada fonte fica **+1,5 s** na tela (regra do app) e invade o trecho seguinte.
2. `edit_captions {"action":"enable","preset":"story"}` (branco + palavra ativa colorida).
3. Fontes separadas por clipe (para posicionar o gancho e o body diferente):
   `{"action":"source_set","json":"{\"sources\":[{\"itemId\":\"<hook>\"},{\"itemId\":\"<body>\"}]}"}`
   → `source_list` dá os `sourceId`.
4. Posição por fonte (sobrescreve a "evitação de rosto" automática):
   `{"action":"positions","json":"{\"positions\":[{\"sourceId\":\"<s1>\",\"anchor\":\"center\",\"offsetYRatio\":0},{\"sourceId\":\"<s2>\",\"anchor\":\"center\",\"offsetYRatio\":0.273}]}"}`
   offsetYRatio = centro_y da referência − 0,5 (ex.: 0,773 → 0,273).
5. Uma linha só: `{"action":"layout_policy","json":"{\"mode\":\"auto-stack\",\"maxVisibleSources\":2,\"perSource\":{\"<s1>\":{\"maxLines\":1},\"<s2>\":{\"maxLines\":1}}}"}`
   (`mode: single-lane` escondeu as legendas no teste — não use).
6. Estilo: `{"action":"style","json":"{\"fontFamily\":\"Montserrat\",\"fontWeight\":900,\"sizePx\":80,\"color\":\"#FFFFFF\",\"highlightColor\":\"#F5F907\",\"strokeColor\":\"#000000\",\"strokeWidth\":6,\"textTransform\":\"uppercase\",\"wordsPerPage\":3,\"pacing\":\"phrase\"}"}`
   e `{"action":"animation","motionPreset":"none"}` (ou o que a referência mostrar).
7. **Paginação por comprimento** (depois de 1–6): `$OCC paginar --max-chars <limite> --max-palavras 3`.
   O limite vem de `textos.legendas.paginacao.limite_caracteres_por_linha` da análise da referência.
   O app só quebra por número de palavras (e ignora `maxCharsPerLine`), então o `paginar` força as quebras.

**Tamanho da fonte:** `sizePx ≈ altura_linha (OCR da referência) × 1920 × 1,14` para Montserrat 900 com
contorno 6 (calibrado: sizePx 72 → altura medida 0,033). Fontes de CapCut ("The Bold Font") são mais
estreitas e altas que a Montserrat: com a mesma largura de linha a letra fica ~18% mais alta. Alternativas
disponíveis no app para testar: `Inter Tight` 900 (mais estreita), `Archivo Black`, `Anton`/`Oswald`
(condensadas demais). Confira com `$REF comparar` (altura e largura da linha).

## Transições
- IDs: `builtin:tr-<tipo>` — anticipation-zoom, radial-blur, whip-pan, cross-dissolve, dip-to-black,
  dip-to-color, flash, impact-shake, glitch-cut, luma-blend, organic-dissolve, page-curl, rack-focus,
  soft-wipe, circle-wipe, clean-line-wipe.
  `{"adds":[{"type":"transition","assetId":"builtin:tr-radial-blur","outgoingItemId":"<a>","incomingItemId":"<b>","durationInFrames":7}]}`
- "zoom-in com borrão" da análise → `radial-blur` (o `anticipation-zoom` só escala, sem borrão).
- A transição só age na faixa dos dois clipes (V1). Um insert na V2 por cima aparece durante a transição:
  termine o insert quando a transição começa (corte − metade da duração).
- A transição sobrepõe os clipes: o clipe seguinte aparece alguns quadros antes do corte — confira com `$OCC quadros`.

## SFX
- Whoosh: `library:sound:simple-whoosh` (também deep-short / airy-short / soft-air). Precisa de faixa de áudio:
  `{"adds":[{"type":"audio","assetId":"library:sound:simple-whoosh","fromFrame":<corte-6>}]}`.
- Outras: `browse_library {"category":"sound-effects","query":"impact"}`.

## Export
- `$OCC exportar EXPORT/x.mp4`. Não use `submit_render_job` com h264 (falha: libfdk_aac ausente).
- Rode `$OCC corrigir-midia` após qualquer importação; sem isso quadros e render dão 404.
