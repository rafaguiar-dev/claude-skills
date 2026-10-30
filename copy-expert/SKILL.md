---
name: copy-expert
description: Pega uma copy (.docx de VSL/anúncio com trechos marcados por cor) e devolve só as frases marcadas, uma por bloco, com [expert] entre elas — e [pessoa 2], [pessoa 3]… quando a copy marca que outro personagem passou a falar. Use quando o usuário disser /copy-expert, mandar um docx de copy e pedir "só as frases marcadas", "coloca o [expert]", "adapta essa copy com o expert", ou repetir o pedido do Melt Peak.
---

# copy-expert

Entrada: caminho de um `.docx` de copy (normalmente da pasta `C:\Users\Rafek\Desktop\IMPETUS\<data>\`).
Saída: um `.txt` ao lado do docx, `<nome do docx> - [expert].txt`. O docx nunca é alterado.

## Regras (combinadas com o Rafael)

- **Não alterar nada do texto.** Só sai frase que tem trecho marcado por cor. Cada frase vai inteira, do começo
  até o ponto (`.`, `!` ou `?`); se o parágrafo tem várias frases, entra só a que contém a marcação.
  Frase sem ponto no original fica sem ponto.
- Pode limpar só espaço: espaço duplo e espaço antes de pontuação ("Melt Peak ." → "Melt Peak.").
- Antes de cada frase, numa linha só, a etiqueta de quem fala:
  ```
  [expert]
  Ich selbst habe über 7.000 Euro ausgegeben, bevor ich Melt Peak entwickelt habe.
  [expert]
  Und die eine bedingungslose 30-Tage-Garantie hat?
  ```
- Quem fala por padrão é o `[expert]`. **Só troca quando a copy diz que trocou**: cor de "troca de avatar"
  da legenda, ou rótulo escrito na copy ("Dr. Anne Fleck:", "[Depoimento 2]", "Avatar 2", "Personagem: …").
  Outro personagem vira `[pessoa 2]`, o seguinte `[pessoa 3]`, e assim por diante, na ordem em que aparecem.
  Se a mesma pessoa volta a falar, volta a etiqueta dela; se a copy indica a volta do expert, volta `[expert]`.
- Fica de fora: a legenda de cores, o cabeçalho (copywriter, produto, potes, links, observações), as cores de
  marcador de edição (pitch, início do bloco de oferta, minuto) e links.

## Passo a passo

1. Rodar o script (lê a legenda do próprio documento, separa as frases e grava o rascunho só com `[expert]`):
   ```bash
   python -I "C:/Users/Rafek/.claude/skills/copy-expert/scripts/extrair.py" "<copy.docx>"
   ```
   Ele imprime: a legenda e o que fez com cada cor (`entra` / `ignorada` / `troca de personagem`), o número de
   frases, as **pistas de troca de personagem** (antes de qual frase) e a lista numerada das frases.
2. Conferir a legenda. Se o script classificou alguma cor errado (legenda com outro texto), dizer ao usuário e
   corrigir à mão no `.txt`.
3. Se houver pistas de troca: abrir as pistas, decidir quem fala em cada trecho e trocar as etiquetas no `.txt`
   (Edit). Na dúvida sobre quem fala (ex.: a pista não diz se é pessoa nova ou a volta do expert), **perguntar**.
   Sem pistas, o rascunho já é o resultado final.
4. Responder com o link do `.txt`, quantas frases entraram, quais trocas de personagem foram feitas e o que
   ficou de fora (só se houver algo além da legenda/cabeçalho, ex.: cor de marcador dentro da copy).

## Observações

- A legenda costuma se repetir no meio da copy ("Cor que sinaliza o pitch"); o script ignora essas linhas.
- Depoimentos *sem* marcação nem rótulo (ex.: a cantora e a médica no meio da copy do Melt Peak) **não** trocam a
  etiqueta — só troca o que está escrito/marcado na copy.
- Python com `-I` (o docx é arquivo de fora). Precisa só da biblioteca padrão.
