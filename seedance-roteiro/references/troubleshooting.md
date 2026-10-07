# Diagnóstico — quando a geração não sai como você queria

Tabela construída em cima de gerações reais. Sempre avalie a geração pela **atuação e pela premissa**, não pela beleza da imagem.

| Sintoma | Causa | Correção |
|---|---|---|
| Ficou lindo, cinematográfico, mas não parece o gênero que você queria | O GLOBAL LOOK padrão puxa para longa-metragem | Reescreva o GLOBAL LOOK declarando o gênero na primeira linha: `Single-camera television comedy, not cinematic film`. Suba o T-stop, suba a luz, tire halation e flare |
| Personagens falam coisas que você não escreveu, em idioma inventado | Falta AUDIO LOCK | Adicione o AUDIO LOCK ao fim do GLOBAL LOOK |
| A premissa visual do vídeo não aparece (o contraste, a ausência, a proporção) | A regra estava dentro do bloco CAST | Mova para bloco próprio logo após o GLOBAL LOOK **e repita dentro de cada shot** |
| Descritor ambíguo virou outra coisa (`muscular or heavy-set` → gordo) | Você deu duas saídas e o modelo escolheu a errada | Um termo só, sem "ou", mais negativa explícita: `athletic gym-built. NOT overweight, not plus-size, not chubby` |
| O protagonista não tem o corpo/idade que você descreveu | Atributo declarado só no CAST | Repita corpo e idade **dentro de cada SHOT** em que ele aparece |
| Nenhum dos dois extremos aparece (nem o protagonista extremo, nem os figurantes extremos) | Você pediu dois extremos de uma vez e o modelo normalizou os dois | Escolha **um lado** para carregar o contraste. Deixe o protagonista comum e faça os outros extremos, ou o inverso |
| Extremo veio fraco mesmo com adjetivo forte | Adjetivo absoluto não tem régua | Ancore por comparação com o protagonista: `arms wider than CHICO's thighs`, `he has to turn sideways to fit past him` |
| Prop virou outro objeto (caixa de som → notebook) | Substantivo sem negativa | `a LARGE BLACK PORTABLE BLUETOOTH SPEAKER — a speaker, not a laptop, not a tablet, not a book` |
| Locação genérica errada (ônibus urbano → ônibus escolar) | Categoria ampla demais | Nomeie e negue: `URBAN PUBLIC TRANSIT BUS... This is NOT a yellow school bus` |
| Fala com timecode caiu vários segundos adiantada | O modelo comprimiu o primeiro ato | Divida em 2 gerações de 12–18s e junte na edição |
| Rosto muda no meio do vídeo | Referências demais competindo, ou descrição do CAST variando entre shots | Suba só frontal + perfil + close. Copie a descrição do CAST palavra por palavra em todo shot |
| Fundo vazio, sensação de cidade fantasma | Falta figurante | `Constant background traffic, never empty, people always walking through frame` em cada LOCATION e nos shots |
| Reação longa demais, ritmo arrastado | Ação sem duração declarada | Timing sub-segundo: `half-second laugh, then flat and certain` |

## Última carta: travar no primeiro frame

Quando uma condição visual não cola de jeito nenhum em movimento, gere a **imagem do primeiro frame** de cada ato (Nano Banana Pro) com a condição já resolvida na imagem parada, e use como frame inicial do Seedance.

Travar contraste, proporção ou composição numa imagem estática é muito mais fácil que em vídeo, e o modelo carrega adiante o que já está no primeiro frame.

## Ordem de ataque

Quando várias coisas saem erradas ao mesmo tempo, corrija nesta ordem — as de cima causam as de baixo:

1. GLOBAL LOOK (gênero visual)
2. Bloco de REGRA + repetição por shot
3. Ambiguidade de descritor e negativas
4. Divisão em gerações menores
5. Props e locações
6. Timing de atuação
