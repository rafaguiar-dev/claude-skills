# Perfil de edição para o OpenChatCut

Um perfil transforma a leitura de uma referência em **regras reaplicáveis**: com outra copy e outro
material, o resultado deve ter a mesma linguagem. Escreva em `<pasta-da-referência>/PERFIL.md`.

Recursos citados abaixo existem no OpenChatCut v0.2.15 (conferidos no código-fonte). Se o editor
atualizar, confirme pelo MCP (`load_skill` / descrição das ferramentas) antes de aplicar.

## Legendas (`edit_captions`)

**Templates** (`template`) — escolha o mais próximo e ajuste com `styleOverride`:

| template | aparência |
|---|---|
| `plain` | branco sem contorno (Inter 400) |
| `black-bar` | frase inteira em faixa preta |
| `netflix` | branco com sombra leve |
| `bold-outline` | branco, contorno preto grosso, 3 palavras/página |
| `story` | branco + palavra ativa amarela #FFD84A |
| `tiktok` | branco + fundo rosa #FF2E63 na palavra ativa, contorno |
| `bili` | branco + fundo ciano #6EE7F9 na palavra ativa |
| `submagic` | grande, fundo verde #00E83C na palavra ativa, empilhado |
| `bubble-pop` | Bangers, CAIXA ALTA, grande, amarelo #FFEC1A, 2 palavras |
| `boyz-n-the-hood` | enorme, CAIXA ALTA, amarelo #FFF200, contorno |
| `off-the-wall` | preto em caixa branca, empilhado |
| `the-french-dispatch` | serifada preta, fundo amarelo #F6C239, 3 palavras |
| `studio` / `white-card` | texto escuro em cartão claro |
| `product` / `signal` | fundo neon verde #A3FF12 / ciano #4DFFDF (signal em caixa alta) |
| `dogme` | CAIXA ALTA com brilho colorido |
| `luxe` / `noir` / `atelier` / `persona` | serifadas elegantes (dourado, vinho, tijolo, cinza) |

**styleOverride** (só o que difere do template): `fontFamily`, `fontSize` (fração da altura, ex. 0.042),
`fontWeight`, `color`, `highlightColor`, `highlightBackground`, `strokeColor`, `strokeWidth`,
`textShadow`, `textTransform` (`uppercase`), `wordsPerPage`, `displayMode` (`stacked`|`inline`),
`wholeLine` + `background` (faixa), `letterSpacing`, `lineHeight`, `boxBorderRadius`.

**pacing:** `word` (palavra a palavra) | `phrase`.
**motionPreset:** `none` | `fade-up` | `pop` | `word-pop` | `karaoke-pulse`.
**layout anchor:** `top-*`, `middle-*`/`center`, `bottom-*` (left/center/right).

Paginação: o OpenChatCut quebra por número de palavras; se a referência quebra por comprimento
(`paginacao.quebra`), use maxLines 1 por fonte + `occ paginar --max-chars N` (skill editar-anuncio,
`references/openchatcut-receitas.md`). Última página de cada fonte fica +1,5 s: ver `occ transcricao --ate`.

`analise.json → textos.sugestao_openchatcut` traz um ponto de partida (templates mais próximos +
styleOverride calculado das cores observadas). Corrija com o que você viu nos recortes.

## Transições

`cross-dissolve`, `dip-to-black`, `dip-to-color`, `flash`, `whip-pan`, `soft-wipe`, `luma-blend`,
`page-curl`, `rack-focus`, `organic-dissolve`, `impact-shake`, `anticipation-zoom`, `clean-line-wipe`,
`circle-wipe`, `radial-blur`, `glitch-cut`, `audio-cross-fade` (áudio) e `custom-shader`.

| Na referência | No OpenChatCut |
|---|---|
| corte seco / jump cut | sem transição (só o corte) |
| punch-in / punch-out | sem transição; keyframe de escala no clipe (ex. 100%→120%) ou clipe duplicado ampliado |
| zoom contínuo no plano ("push-in ~5%/s") | keyframes de escala ao longo do clipe |
| dip-to-black / flash / cross-dissolve / whip-pan / glitch | a transição homônima (`glitch` → `glitch-cut`) |
| zoom na transição com borrão (o comum em UGC) | `radial-blur` (o `anticipation-zoom` só escala, sem borrão) |
| troca de insert (tela dividida) | corte só no clipe do insert (V2), sem transição |
| emenda na fonte (morph) | nada — vem do material |
| tremor no impacto | `impact-shake` |

Anote a **duração** (em frames a 30 fps) e **quando** acontece (na batida? na palavra X?).

## Modelo de PERFIL.md

```markdown
# Perfil: <nome> (baseado em <referência>, <data>)

## Quando usar
<tipo de anúncio, plataforma, formato 9:16, duração típica, tom>

## Estrutura
- Gancho (0–3s): <o que acontece, papel>
- Corpo: <problema → solução → prova, como se alternam A-roll e B-roll>
- CTA (últimos Xs): <o que aparece, quanto tempo fica legível>

## Ritmo e cortes
- Plano médio ~X s; corte em toda frase / a cada N palavras; cortes na batida? (sim/não)
- Punch-in: <escala, frequência, alternância>
- Transições: <quais, onde, duração, com que som>

## Legendas
- template `<id>` + styleOverride `{...}`; pacing `<word|phrase>`; wordsPerPage N; motionPreset `<...>`
- posição `<anchor>` (y≈0.xx); regras de exceção (ex.: sobe quando há produto embaixo)

## Textos de tela
- <títulos/preço/CTA: fonte, cor, posição, entrada, duração>

## Som
- Música: clima, BPM ~X, volume sob a voz (-X dB), sobe/cai onde; (faixa original: <título> — só com licença)
- SFX: <whoosh nas transições, pop nas legendas, impacto no gancho…>

## Imagem
- Look/LUT: <quente, contraste alto…>; movimento: <zoom lento nos talking heads…>

## Adaptação para copy nova
- O que manter sempre: <relações e papéis>
- O que ajustar à copy: <número de blocos, duração, exemplos>
- Checklist de revisão: gancho em ≤3s, legenda legível, CTA ≥2s na tela, música não briga com a voz
```

## Instalar como skill do OpenChatCut (com OK do usuário)

Arquivo: `%USERPROFILE%\.openchatcut\skills\perfil-<nome>\SKILL.md`

```markdown
---
name: perfil-<nome>
description: |
  Edita anúncios no estilo <nome>: <resumo em uma linha do estilo>.
  Use quando o usuário pedir o perfil <nome> ou um anúncio "no estilo <referência>".
---

# Perfil <nome>

<conteúdo do PERFIL.md, escrito como instruções diretas para o agente do editor:
"Monte a espinha gancho → ... ", "Aplique legendas com ...", "Coloque whoosh em ...">
```

O agente interno do OpenChatCut passa a oferecer o perfil no chat (`/`), e o Claude Code também pode
lê-lo pelo MCP ou direto do arquivo ao editar.
