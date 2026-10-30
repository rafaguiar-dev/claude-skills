---
name: copy-depoimentos
description: Recebe uma pasta com a copy (.docx de VSL com trechos marcados por cor) e o vídeo da VSL, e devolve um docx só com as frases marcadas, separadas por [expert] e [depoimento 1], [depoimento 2]… conforme quem aparece falando no vídeo, com o print do rosto de cada depoimento na primeira vez que a pessoa fala. Usa Whisper pra achar cada frase no vídeo e folhas de prints pra ver quem está na tela. Use quando o usuário disser /copy-depoimentos, mandar "a pasta com a copy e o vídeo", pedir "separa expert e depoimentos com print do rosto", "coloca o print de cada depoimento na copy", ou repetir o pedido do Melt Peak (30-10).
---

# copy-depoimentos

Entrada: uma pasta (ex.: `C:\Users\Rafek\Desktop\IMPETUS\30-10`) com **a copy (.docx)** e **o vídeo da VSL**.
Saída, ao lado da copy (o docx original nunca é alterado):
- `<copy> - [depoimentos].docx`: frases marcadas, cada uma com `[expert]` ou `[depoimento N]` antes, e o print do
  rosto logo abaixo da etiqueta **só na primeira fala** de cada depoimento;
- o mesmo texto em `.txt` (sem imagens);
- pasta `prints depoimentos\` com `depoimento N.jpg` em tamanho cheio.

As frases seguem as regras do `/copy-expert` (mesmo script): só frase com trecho marcado por cor, inteira, sem
mudar palavra, nome do produto como está na copy. A copy costuma trocar o nome do produto (ex.: no vídeo
"SlimJara", na copy "Melt Peak"); isso é normal e o script ignora o nome ao comparar.

## Passo a passo

1. **Preparar** (lê a copy, transcreve com Whisper, acha o tempo de cada parágrafo e de cada frase marcada):
   ```bash
   python -I "C:/Users/Rafek/.claude/skills/copy-depoimentos/scripts/preparar.py" "<pasta>"
   ```
   - Rodar em segundo plano: a transcrição leva uns 5 min por hora de vídeo na RTX 3060. Fica em cache
     (`_copy-depoimentos\transc.json`), então rodar de novo é rápido.
   - Se a pasta tiver mais de um docx ou vídeo, o script lista e para: perguntar qual, ou escolher pelo nome
     e passar `--docx` / `--video`.
   - O nome do produto sai da linha "Produto: X → Y" da copy; se não tiver, passar `--nome-antigo` e `--nome-novo`.
   - **Se avisar que o vídeo não bate com a copy (menos de 70% das frases), parar e falar com o usuário.** Não
     inventar: é outra versão do vídeo (aconteceu no 30-10: o primeiro vídeo era a VSL antiga).

2. **Descobrir quem fala.** Ler `_copy-depoimentos\copia.tsv` (cada parágrafo com tempo e quais frases marcadas
   ele tem) e marcar os trechos em que **outra pessoa** fala: histórias em primeira pessoa de cliente/famoso,
   apresentações ("Ich bin Dr. …", "Ich bin 56 Jahre alt…"), fala depois de uma chamada do expert ("Einige
   prominente Persönlichkeiten…", "Und es sind nicht nur Prominente…"), e a volta do expert ("Du hast diese
   Frauen gehört…", "Das von einer Ärztin wie … zu hören…"). Cor de troca de avatar e rótulos na copy também
   contam (o script imprime as pistas).

3. **Conferir no vídeo.** Olhar (Read) `frases-1.jpg` (um print no meio de cada frase marcada). Muitas frases caem
   em b-roll (potes, natureza); por isso, para cada trecho de depoimento, varrer o trecho inteiro:
   ```bash
   python -I "C:/Users/Rafek/.claude/skills/copy-depoimentos/scripts/varrer.py" "<pasta>" <início_s> <fim_s> --nome dep1
   ```
   e olhar `varre-dep1.jpg`. Conferir: é **uma pessoa só** no trecho (se trocar no meio, é outro depoimento),
   é diferente do expert, e se a mesma pessoa volta mais tarde (volta com o mesmo número). Escolher para cada
   depoimento um segundo com o rosto de frente, sem b-roll por cima. Na dúvida sobre os trechos do expert,
   varrer também (passo maior, ex. `--passo 15`).

4. **Montar.** Escrever `_copy-depoimentos\mapa.json` e rodar o montar:
   ```json
   {"falas": {"5": 1, "6": 2, "8": 4, "9": 4}, "prints": {"1": 2448, "2": 2537, "4": 2740}}
   ```
   `falas` = número da frase marcada → número do depoimento (o que não estiver é `[expert]`); depoimentos
   numerados na ordem em que aparecem. `prints` = depoimento → segundo do print.
   ```bash
   python -I "C:/Users/Rafek/.claude/skills/copy-depoimentos/scripts/montar.py" "<pasta>" "<pasta>/_copy-depoimentos/mapa.json"
   ```

5. **Conferir e responder.** Juntar os prints numa tira (ffmpeg `tile`) e olhar se cada um é um rosto
   diferente e bem visível. Responder com o link do docx, quantas frases, e uma tabela curta: depoimento →
   quem é (como a copy descreve: "a cantora", "a enfermeira"), minuto do print. Não dizer o nome real de
   ninguém pelo rosto; só o que a copy diz.

## Pegadinhas (já aconteceram)

- **Faltou cublas64_12.dll**: `pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"`; o script já aponta pras DLLs.
- **MemoryError no Whisper** com vídeo longo: o script transcreve em pedaços de 10 min por isso.
- `python -I` ignora `PYTHONIOENCODING`; os scripts já reconfiguram a saída para UTF-8.
- Loop de shell com ffmpeg lendo stdin come a lista: os scripts usam `-nostdin`. No Windows, saída do Python
  em loop de bash tem `\r` no fim: fazer os laços em Python.
- O link da VSL na copy também tem o nome trocado e pode dar 404; não é o vídeo.
- Precisa: `faster-whisper`, `python-docx`, ffmpeg no PATH, modelo `mobiuslabsgmbh/faster-whisper-large-v3-turbo`
  (baixa sozinho na 1ª vez). Usa `extrair.py` da skill `copy-expert` (tem que estar instalada ao lado).
