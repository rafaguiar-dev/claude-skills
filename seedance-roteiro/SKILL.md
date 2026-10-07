---
name: seedance-roteiro
description: Escreve roteiros e prompts para o Seedance 2.5 (vídeos de até 30s, one-shot ou por cena). Use sempre que o usuário pedir roteiro, prompt, script, storyboard ou decupagem para Seedance, Higgsfield, comercial de IA, curta de IA ou vídeo cinematográfico gerado por IA — inclusive ao adaptar/parodiar um vídeo existente. Também use ao montar character sheets, referências de locação ou ao refinar um prompt de Seedance que não deu o resultado esperado.
---

# Roteiro para Seedance 2.5

Metodologia de produção validada: fundação (personagens + locação) → blocagem de atuação → **um único prompt com estrutura travada** → 3 gerações → montagem do melhor de cada.

O erro que mata 90% dos projetos é pular a fundação e escrever prompt solto por clipe. Não faça isso.

## Capacidades do modelo (respeite os limites)

| Recurso | Limite |
|---|---|
| Duração | até **30s** em uma única geração (one-shot) |
| Resolução | **720p** máx. |
| Aspect ratio | 16:9 (padrão), 9:16, 1:1 |
| Referências | até **50** — imagens, **vídeo** (motion), **áudio** (voz) |
| Tamanho do prompt | Higgsfield permite prompts longos (~5.000 caracteres é o alvo); outras plataformas travam em 5.000 |

Cortes internos são feitos pelo próprio modelo: você descreve os cortes dentro do prompt, com timecodes. **Não** gere clipe por clipe se couber em 30s — o one-shot mantém personagem, luz e color grade consistentes de graça.

## Fluxo de trabalho

### 1. Fundação (antes de escrever qualquer prompt)

**a) Mensagem central.** Uma frase: o que o vídeo vende ou diz.

**b) Lista de piadas/tensões.** Brainstorm do que pode ser engraçado, tenso ou surpreendente dentro dessa mensagem. Escolha uma virada.

**c) Character sheets.** Um por personagem. Ver `references/character-sheet.md`.
- Gere com **GPT-Image / GPT-2** (pele realista). Evite Nano Banana Pro para pessoas — dá pele plástica.
- Nano Banana Pro é bom para **locação**, não para rosto.
- Itere até o personagem *parecer certo*. Chapéu, cabelo, idade — teste variações.
- **O sheet manda mais que o texto.** Se o sheet tem cara de adulto de 30, o vídeo vai ter um adulto de 30 por mais que o prompt escreva "17 anos". Quando o sheet já está aprovado, **adapte o roteiro ao sheet** — troque a locação, a idade dos personagens, o contexto — em vez de brigar com ele no texto.

**d) Referência de locação.** Isto trava o **color grade do projeto inteiro**. Nunca use uma foto chapada/nublada. Pegue um frame cinematográfico de referência (Pinterest, Cosmos), suba como referência e peça a locação nesse mesmo grade, **sem pessoas na imagem**.

**e) Sheets de produto/objeto**, se houver produto na cena.

### 2. Blocagem de atuação (a parte que ninguém faz)

Feche os olhos e **dirija a cena em voz alta**, plano a plano. Para cada plano responda:
- Qual o **enquadramento**? (wide / establishing / medium / medium two-shot / close-up / side profile / over-the-shoulder / reveal / behind them)
- Onde está a **câmera** e como ela se move?
- O que cada personagem **faz fisicamente**? (não "ele fica surpreso" — "os olhos arregalam, o maxilar trava, ele engole seco")
- O que se **ouve**? (ambiência, específica: gaivotas, conversa ao fundo, chiado de ônibus)
- O que **se move ao fundo**? Figurantes obrigatórios — sem isso o Seedance entrega cidade fantasma.

### 3. Montar o prompt (estrutura travada)

Ver `references/prompt-template.md` para o template completo e `references/global-look.md` para os presets de câmera.

Ordem obrigatória dos blocos:

```
[GLOBAL LOOK — LOCKED, APPLIES TO EVERY SHOT]
   ... + AUDIO LOCK no fim do bloco
[<NOME> RULE — THE MOST IMPORTANT RULE IN THIS PROMPT]
[CAST — IDENTICAL IN EVERY SHOT]
[LOCATION]
SHOT 1 (0:00-0:0X) — ENQUADRAMENTO
SHOT 2 ...
```

Regras não-negociáveis:
- **Todo shot tem timecode** com início e fim. Some tudo: tem que fechar exatos 30s (ou a duração escolhida).
- **12 a 16 shots** em 30s. Menos que isso fica arrastado.
- **Nomes dos personagens em CAIXA ALTA** no bloco CAST e sempre que falarem. Esses nomes viram as *tags* que você liga às imagens de referência na plataforma.
- **Timing de atuação em frações de segundo.** "Ele ri" → o modelo dá 2 segundos de risada e quebra o ritmo. Escreva "risada obnóxia de meio segundo, depois expressão neutra e firme".
- **Diálogo entre aspas**, com sotaque/entonação declarados antes: `MATE (sotaque australiano): "..."`.
- **Figurantes em movimento ao fundo** em pelo menos metade dos shots.
- **AUDIO LOCK obrigatório** — sem ele o modelo inventa diálogo (inclusive falso, em idioma inventado) nos planos onde você não escreveu fala. Ver abaixo.
- Alvo de tamanho: **~5.000 caracteres**. Prompt curto = atuação genérica. Gaste o orçamento de caracteres em nuance de atuação, não em adjetivos de beleza.

### O bloco de REGRA (quando o vídeo depende de uma condição visual)

Se o vídeo tem **uma premissa visual que precisa ser verdadeira em todo frame** — um contraste, uma ausência, uma proporção — ela **não pode morar dentro do CAST**. O modelo trata o CAST como descrição de figurino e ignora regra enterrada ali. Crie um bloco próprio, logo depois do GLOBAL LOOK, com nome enfático:

```
[CONTRAST RULE — THE MOST IMPORTANT RULE IN THIS PROMPT]
<a condição, afirmada>
<o que a condição significa concretamente>
<o que a condição NÃO significa — negativas explícitas>
If a shot contains other people and <a condição> is not immediately readable,
the shot is wrong.
```

E **repita a condição dentro de cada SHOT**. O Seedance obedece o que é repetido por plano, não o que foi declarado uma vez no topo.

### AUDIO LOCK

Vai no fim do bloco GLOBAL LOOK, sempre:

```
AUDIO LOCK: no music. No spoken dialogue anywhere except the lines explicitly written
below. Every other shot is ambience only — <lista de sons do ambiente>. Never invent
dialogue. Characters do not move their lips unless a written line is given to them.
```

Sem isso o modelo enche os planos silenciosos de fala inventada, e você perde o áudio inteiro.

### Quando dividir em várias gerações

O one-shot de 30s é o padrão, mas o modelo **comprime o primeiro ato** quando há muitos planos curtos no começo. Se o timing importa (piada, batida musical, locução casada), divida em **2 gerações de 12–18s** com os mesmos blocos GLOBAL LOOK / RULE / CAST e junte na edição com corte seco. Você perde nada de consistência e ganha aderência de timecode.

Sinal de que precisa dividir: numa geração anterior, uma fala com timecode caiu mais de 2s adiantada.

### 4. Gerar

- Suba os character sheets + a locação como referências e **tague cada nome do bloco CAST** na sua imagem correspondente.
- 16:9, 720p, duração alvo.
- **Rode 3 gerações do mesmo prompt.** Nunca conte com o primeiro resultado.

### 5. Refinar e montar

- Avalie cada geração pela **atuação**, não pela imagem. "O plano 3 ficou bom, o 7 ficou morto" → volte, ajuste só aqueles shots, gere de novo.
- Da versão aprovada, rode 3x e **garimpe o melhor pedaço de cada uma**, costurando na edição.
- Corte os silêncios extras que o modelo insere entre falas.
- Finalize com color grade sutil próprio + film grain — tira o cheiro de "saiu cru do modelo".

## Ao adaptar / parodiar um vídeo existente

1. Faça a **decupagem do original** primeiro: tabela plano-a-plano com timecode, enquadramento e ação.
2. Identifique **a engrenagem da piada** — o mecanismo, não as falas. Normalmente é uma inversão ou uma quebra de expectativa.
3. Mapeie a substituição **dos dois lados**: se o protagonista muda de grupo, o grupo oposto também precisa existir em cena, senão o contraste some e a piada morre.
4. **Escreva falas novas.** Não transcreva a dublagem original palavra por palavra — reescreva mantendo a estrutura e o timing cômico.
5. Adapte os timecodes do original para o seu prompt de 30s.

## Voz e narração

- Narração em off: gere separado (TTS) e monte por cima, **ou** suba um **áudio de referência** de voz nas referências do Seedance para travar timbre entre gerações.
- Sempre escreva a **direção de voz** junto do roteiro: timbre, idade, cadência, emoção, tratamento (seco/com reverb), ritmo.
- Se o timing da fala for crítico, calibre o corte pelo áudio — não o áudio pelo corte.

## Quando a geração não sai como você queria

Ver `references/troubleshooting.md` — tabela sintoma → causa → correção, construída em cima de gerações reais.

## Checklist antes de gerar

- [ ] Character sheet de cada personagem, feito com modelo de pele realista
- [ ] Roteiro compatível com o que os sheets realmente mostram (idade, porte, contexto)
- [ ] Locação gerada com color grade de referência, sem pessoas
- [ ] Bloco GLOBAL LOOK **do gênero certo** — não caia no cinematográfico por inércia
- [ ] AUDIO LOCK no fim do GLOBAL LOOK
- [ ] Bloco de REGRA próprio, se o vídeo depende de uma condição visual
- [ ] A condição da REGRA repetida dentro de cada shot
- [ ] Bloco CAST com nomes em caixa alta e descrição física fechada
- [ ] Props e locações com negativa explícita (`a speaker, not a laptop`)
- [ ] Todo shot com timecode; soma = duração alvo
- [ ] Atuação descrita fisicamente, com timing sub-segundo nas reações
- [ ] Figurantes em movimento ao fundo
- [ ] Diálogo com sotaque/entonação declarados
- [ ] Referências subidas (frontal + perfil + close apenas) e nomes tagueados
- [ ] Plano de rodar 3 gerações
