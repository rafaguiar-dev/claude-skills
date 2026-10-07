---
name: analisar-referencia
description: Assiste um vídeo de referência (anúncio, reels, VSL) e descreve como ele foi editado — cortes e ritmo, transições (punch-in, dissolve, flash, whip…), legendas (estilo, cor, contorno, ritmo, posição), textos de tela, música (qual é, BPM, cortes na batida), SFX, mixagem, cor e movimento — e transforma isso num perfil de edição para o OpenChatCut. Use quando o usuário disser /analisar-referencia, mandar um vídeo/link "de referência", pedir "edita igual a esse", "copia o estilo desse anúncio", "o que tem nesse vídeo (legenda, transição, música)", ou quiser criar/atualizar um perfil de edição a partir de um exemplo.
---

# Analisar referência

Objetivo: entender **o que** a referência comunica e **como** cada escolha de edição serve a isso,
com detalhe suficiente para recriar a mesma função num anúncio novo (outra copy, outro produto) no
OpenChatCut. Tudo roda local e grátis; só a identificação da música consulta o Shazam (grátis).

Ferramenta: `~/.claude/skills/analisar-referencia/ref` (Git Bash). Abaixo, `REF` = esse caminho.

## 1. Preparar

```bash
REF=~/.claude/skills/analisar-referencia/ref
$REF preparar "<link ou caminho do vídeo>" --nome "<cliente-ou-tema>" --raiz "<projeto>/referencias"
```

- Raiz padrão: `referencias/` na pasta atual (em `D:\EDITOR` → `D:\EDITOR\referencias\<nome>`).
- Pasta já existente → erro; use outro `--nome` ou `--substituir` (apaga a análise anterior).
- Link: baixado com yt-dlp (TikTok, Instagram, YouTube, Facebook Ads Library etc.).
- Primeira execução numa máquina nova instala as dependências (`uv sync`); com GPU NVIDIA rode antes
  `uv sync --project ~/.claude/skills/analisar-referencia --extra gpu` para a transcrição usar a GPU.

## 2. Análise automática

```bash
$REF analisar "<pasta>" --idioma pt
```

Leva ~1–2 min para um anúncio de 30–60 s. Etapas (em cache em `dados/`): `fala` (faster-whisper,
tempo por palavra), `cortes` (planos e transições), `textos` (OCR de legendas e textos de tela),
`audio` (Demucs separa voz/música; BPM, batidas, Shazam, SFX, mixagem), `visual` (cor, movimento
por plano, rosto), `evidencias` (grades de imagens). Opções: `--pular etapa,...`, `--refazer etapa,...|tudo`,
`--sem-shazam`, `--dispositivo cpu`, `--modelo small` (máquina fraca), `--ocr-fps 6` (legenda muito rápida).

Saídas: `resumo.md` (impresso no fim), `analise.json` (todos os dados), `transcript.json`,
`evidencias/` e `audio/stems/` (voz e música separadas — úteis para ouvir a trilha sem a fala).

## 3. Ler de verdade (o trabalho principal)

A máquina entrega **candidatos**. Leia `references/metodo.md` e siga-o: assista o todo, depois confirme
cada sistema nas evidências. Ordem prática:

1. `resumo.md` e `transcript.json` → argumento, gancho, estrutura (gancho → problema → solução → prova → CTA).
2. `evidencias/00_visao_geral*.jpg` e `01_planos*.jpg` → formato, tipos de plano, B-roll, quem aparece.
3. `evidencias/02_transicoes*.jpg` → confirme ou corrija cada rótulo (cada linha = uma transição).
4. `evidencias/legendas/estilo_N.jpg` (recorte em alta) e `entrada_N.jpg` (todos os frames da entrada)
   → fonte aproximada, peso, cor, contorno, sombra, destaque da palavra ativa, animação de entrada.
5. `evidencias/03_textos_na_tela.jpg` → títulos, preços, selos, CTA (tipografia independente da fala).
6. Dúvidas → leitura fina com `grade`:

```bash
$REF grade "<pasta>" --perto "frase falada" --cada 0.1 --para "<pasta>/evidencias/extra/x.jpg"
$REF grade "<pasta>" --inicio 6.8 --fim 7.4 --todos-frames --para "<pasta>/evidencias/extra/y.jpg"
$REF grade "<pasta>" --em 3.2,3.4 --recorte 0,0.6,1,0.3 --celula 900 --para "<pasta>/evidencias/extra/z.jpg"
$REF recorte "<pasta>" --inicio 6.5 --fim 8 --rotular-tempo --para "<pasta>/evidencias/extra/trecho.mp4"
```

`--recorte x,y,w,h` usa frações do quadro (0–1). `--perto` aceita frase sem acento/pontuação;
se repetir, use `--ocorrencia N`. Cada célula mostra o tempo e a fala, com a palavra ativa entre [colchetes].

Limites conhecidos (confirme sempre visualmente):
- OCR perde acentos e às vezes espaços ("COMPREAGORA") — o texto certo está no recorte.
- Rótulos de transição: corte seco, jump cut, punch-in/out (com escala), dip-to-black/color, flash,
  cross-dissolve, whip-pan, zoom-in/out (inclusive corte escondido por borrão de movimento, com a duração em
  quadros), radial-blur, glitch, "troca de insert (tela dividida)", "emenda na fonte (morph)" e
  "gradual (verificar)". Efeitos muito estilizados (shake, glitch, luz) podem vir como "gradual".
- "Emenda na fonte (morph)": transição suave entre trechos da *mesma* cena — típico de vídeo gerado por IA
  (avatar). Não é edição: não recrie nem conte como corte (já sai das estatísticas).
- Tela dividida: detectada a partir de cortes que trocam só um lado do quadro; `cortes.tela_dividida` traz
  início/fim, linha divisória (fração da altura) e as trocas de insert. Sem troca de insert não há semente —
  uma tela dividida estática passa despercebida (olhe a visão geral).
- Legenda: `textos.legendas.paginacao` diz se a página quebra por número de palavras ou por comprimento
  (limite de caracteres/linha, fração em 1 linha). `sugestao_openchatcut` já traz `sizePx` calibrado e os
  comandos de paginação para o OpenChatCut.
- SFX são "prováveis" (whoosh/impacto/pop por energia e frequência) — ouça `audio/stems/musica_e_efeitos.wav`.
- Fonte exata não é identificada; descreva a família (sans pesada, condensada, serifada, arredondada)
  e sugira a mais próxima disponível no OpenChatCut/Google Fonts.

## 4. Registrar

Na pasta da referência, escreva (em português, curto e concreto):

- `ANALISE.md` — visão do todo: objetivo, público provável, estrutura e ritmo, e cada **sistema**
  (legenda, textos de tela, B-roll, transições, som, cor) descrito uma vez, com o que faz pelo espectador.
- `TIMELINE.md` — seções por tempo e fase (`## 0:00–0:03 · Gancho`), ligando o que aparece às palavras
  faladas, com tempos, cores, posições e movimentos necessários para recriar.
- Separe o **observado** (“a legenda entra com escala 80%→100% em 4 frames”) do **interpretado**
  (“o pop dá energia ao gancho”).

Converse com o usuário durante a leitura: mostre 1–3 evidências que explicam o estilo, diga o que você
entendeu e pergunte o que ele quer manter ou mudar (gosto é dele).

## 5. Perfil para o OpenChatCut

Siga `references/perfil-openchatcut.md` para escrever `PERFIL.md` na pasta da referência — regras de
edição que funcionam com **outra copy e outro material**, mapeadas para recursos reais do OpenChatCut
(template de legenda + `styleOverride`, âncora, `pacing`, `motionPreset`, transições, keyframes de zoom,
música/SFX, LUT). Com o OK do usuário, instale também como skill do OpenChatCut em
`%USERPROFILE%\.openchatcut\skills\perfil-<nome>\SKILL.md` (formato no mesmo arquivo de referência).

Depois, para editar um anúncio novo com o perfil: use a skill `editar-anuncio` (copy + brutos + PERFIL.md
→ OpenChatCut → MP4).

## 6. Comparar a edição com a referência
Depois de exportar, analise a edição e compare (gera `comparacao.md` na pasta da edição, com ✅/⚠️ e o
ajuste sugerido para cada diferença — transição faltando, sizePx, linhas da legenda, posição, cores):
```bash
$REF preparar EXPORT/<edição>.mp4 --nome <nome>-edicao --raiz referencias --substituir
$REF analisar referencias/<nome>-edicao --idioma <idioma> --pular audio,evidencias --sem-shazam
$REF comparar referencias/<ref> referencias/<nome>-edicao --legenda-size <sizePx usado>
```

## Regras

- Rótulo automático não é fato: só afirme o que confirmou nas evidências.
- Preserve a **função** (gancho que abre um loop, prova que interrompe, CTA legível), recrie a **forma**.
- Não copie marca, logo, pessoas, claims ou textos da referência para o anúncio do cliente.
- Música identificada ≠ música liberada: avise que usar a faixa exige licença e sugira trilha livre
  com BPM/clima parecidos.
- Referência com interface de app (TikTok/Instagram gravado da tela): ignore os elementos de interface
  (`tipo: interface/marca`) ao descrever o estilo.
