# Método: como ler uma referência de anúncio

Inspirado na abordagem de leitura de referência do Hypit (hypit-ai/hypit), adaptado para anúncios
curtos e para o OpenChatCut.

## Duas leituras que se corrigem

1. **O todo.** Assista (visão geral + transcrição) do início ao fim. Responda: o que o anúncio vende,
   para quem, qual a promessa, onde está o gancho, a virada, a prova e o CTA. Forme uma explicação
   provisória de *por que* ele funciona.
2. **O detalhe.** Para cada escolha concreta (um corte, uma legenda, um som), descreva o que é, onde
   está, quando entra, como se comporta, quanto dura e como sai — e o que isso faz pelo espectador
   naquele momento da fala.

Uma leitura revisa a outra. Um detalhe estranho se explica olhando o entorno (a frase dita, o plano
anterior, a próxima aparição). Uma explicação geral só vale se explicar os detalhes.

## Pense em sistemas, não em quadros

Um anúncio tem poucos **sistemas** que se repetem com variações:

| Sistema | O que registrar |
|---|---|
| Legenda (fala) | agrupamento (palavra a palavra / 2–3 palavras / frase), linhas, posição, fonte e peso, cores (texto, contorno, sombra, caixa), destaque da palavra ativa, caixa alta, animação de entrada/saída, quando some (ex.: some quando entra um título) |
| Tipografia de tela | títulos, números, preço, selo, CTA: conteúdo, hierarquia, posição, cor, entrada, permanência |
| A-roll | quem fala, enquadramento (close/médio), olhar, cortes na fala (jump cuts, punch-ins alternando escala) |
| B-roll / produto | o que ilustra, em que palavra entra, duração, se cobre a tela inteira ou é inset |
| Transições | tipo, duração, em que palavra/batida acontecem, se têm som |
| Movimento | zoom lento contínuo, tremor, pan; em que planos |
| Som | música (clima, BPM, entra/sai, sobe no CTA?), SFX (whoosh nas transições, pop nas legendas, impacto no gancho), volume da música sob a voz |
| Cor | look geral (quente/frio, contraste, saturação), se muda entre A-roll e B-roll |

Descreva cada sistema **uma vez** e depois só localize no tempo o que muda ("a partir de 0:12 a
legenda sobe para o meio porque entra o produto embaixo").

## Observação x interpretação

Escreva separado:
- **Observado:** "a palavra ativa fica amarela #FFD84A, entra com escala ~80%→100% em 3–4 frames".
- **Interpretado:** "o pop mantém o olho na legenda durante a fala rápida do gancho".

Se duas leituras conflitam, reabra o trecho (`grade --todos-frames`) até o detalhe ficar legível.
Controles de player e interface de app não fazem parte do design.

## Densidade de amostragem

Amostras mostram só os instantes amostrados. Para entender:
- o argumento → `--cada 1` no vídeo todo;
- uma troca de plano/legenda → `--cada 0.1` em 1–2 s;
- uma animação ou transição → `--todos-frames` em 0.3–0.8 s;
- tipografia → `--em T --recorte ... --celula 900`.

Use `--perto "frase"` para ir direto ao momento em que algo é dito.

## Da referência para o anúncio novo

A copy nova muda número de frases, duração e exemplos. Então o perfil guarda **relações**, não tempos:
- "corte a cada frase curta; punch-in 1.2x alternando a cada 2º corte na fala";
- "B-roll entra exatamente na palavra que nomeia o objeto e dura até o fim da frase";
- "legenda 2–3 palavras, branca com contorno preto grosso, palavra ativa amarela, pop de entrada";
- "whoosh em toda transição não-seca; impacto no primeiro frame do gancho";
- "música ~120 BPM, -18 dB sob a voz, sobe 6 dB no CTA".

Para cada relação diga o **papel** (o que faz pelo espectador) — é o papel que se preserva quando a
forma precisa mudar.
