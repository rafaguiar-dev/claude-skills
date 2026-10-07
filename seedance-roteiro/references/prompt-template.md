# Template de prompt — Seedance 2.5

Estrutura completa. Preencha os blocos na ordem. Alvo: ~5.000 caracteres para 30s.

```
[GLOBAL LOOK — LOCKED, APPLIES TO EVERY SHOT]
<corpo de câmera>, <família de lentes>, <película/sensor + temperatura>, <aspect ratio>,
<T-stop>, shallow depth of field, halation on highlights, fine organic grain,
lifted milky blacks, low contrast, no sharpening, no HDR.
<Nome do grade>: <tom de pele herói>, <campo de cor dominante>, <cor das sombras>,
<tratamento de luz>. Handheld with micro-drift, never locked off.
Naturalistic performance.

AUDIO LOCK: no music. No spoken dialogue anywhere except the lines explicitly written
below. Every other shot is ambience only — <sons concretos do ambiente>. Never invent
dialogue. Characters do not move their lips unless a written line is given to them.

[<CONDIÇÃO> RULE — THE MOST IMPORTANT RULE IN THIS PROMPT]     ← só quando aplicável
<a condição, afirmada de forma direta>
<o que ela significa concretamente, com exemplo comparativo>
<o que ela NÃO significa — negativas explícitas>
If a shot contains <o elemento> and <a condição> is not immediately readable,
the shot is wrong.

[CAST — IDENTICAL IN EVERY SHOT]
NOME1: idade, tipo físico, cabelo, pelos faciais, olhos, roupa peça a peça com cor,
        marcas de pele (sardas, cicatrizes, tatuagens).
NOME2: ...
NOME3: ...
PROP: objeto-chave com cor e material.

[LOCATION]
Descrição do lugar, elementos de cenário nomeados, onde os personagens estão
posicionados em relação à câmera, e o que existe ao fundo (figurantes, movimento).

SHOT 1 (0:00-0:02.5) — <ENQUADRAMENTO>
Ação física de cada personagem. Movimento de câmera. Detalhe pequeno e concreto
(condensação na garrafa, poeira na luz, reflexo).

SHOT 2 (0:02.5-0:07) — <ENQUADRAMENTO>, <tratamento de foco>
Quem está em foco e quem está desfocado. O gesto exato. O momento da reação.
NOME1: "fala entre aspas"

SHOT 3 (0:07-0:10.5) — CLOSE-UP, NOME2
Direção de atuação com timing sub-segundo.
NOME2 (sotaque/entonação): "fala"

... até fechar a duração alvo.
```

## Vocabulário de enquadramento

`ESTABLISHING SHOT` · `WIDE` · `MEDIUM` · `MEDIUM TWO-SHOT` · `CLOSE-UP` ·
`TIGHT CLOSE-UP` · `EXTREME CLOSE-UP` · `SIDE PROFILE` · `OVER-THE-SHOULDER` ·
`BEHIND THEM` · `REVEAL` · `RACK FOCUS HELD` · `POV` · `TOP-DOWN` · `LOW ANGLE` ·
`SLOW MOTION TWO-SHOT (40% speed)` · `HARD CUT TO`

## Movimento de câmera

`slow handheld drift right` · `push in` · `pull back to reveal` · `slow dolly out` ·
`whip pan` · `camera tracks backward ahead of him` · `locked with micro-drift` ·
`rack focus from X to Y`

## Direção de atuação — antes e depois

| Fraco | Forte |
|---|---|
| ele fica surpreso | os olhos arregalam, o maxilar trava, engole seco |
| ele ri | risada alta e obnóxia de meio segundo, depois expressão neutra e firme |
| ela olha maliciosa | cabeça inclinada pra baixo, sobrancelha franzida, sorriso ladino; lambe os lábios e esfrega as mãos ao mesmo tempo |
| ele fica sem graça | o sorriso desmancha, o olhar cai, ele para de andar |
| eles se entreolham | os dois viram e se olham direto, expressão completamente vazia, 40% da velocidade |

## Ancorar um extremo por comparação

Adjetivo absoluto não tem régua. O modelo não sabe onde fica "enorme". Ancore no protagonista:

| Fraco | Forte |
|---|---|
| um homem muito grande | `arms wider than CHICO's thighs` |
| ele é enorme | `shoulders wider than the aisle itself, turning sideways to pass` |
| ela é muito alta | `she has to duck under the doorframe he walks straight through` |
| um lugar lotado | `he stops walking and the crowd keeps flowing around him` |

## Erros que derrubam a geração

- Shot sem timecode → o modelo redistribui o tempo sozinho e estoura o ritmo
- Fundo sem figurantes → cidade fantasma
- Reação sem duração declarada → risadas de 2 segundos, pausas mortas
- Descrever emoção em vez de gesto → rosto inexpressivo
- Trocar a descrição do personagem entre shots → o rosto muda no meio do vídeo
- Prompt curto → atuação genérica de banco de imagens
- Sem AUDIO LOCK → o modelo enche os planos silenciosos de fala inventada
- Condição visual declarada só uma vez no topo → ignorada
- Descritor com "ou" (`muscular or heavy-set`) → o modelo escolhe a interpretação errada
- Dois extremos ao mesmo tempo → o modelo normaliza os dois e você não fica com nenhum
