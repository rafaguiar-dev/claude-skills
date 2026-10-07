# Character sheet para Seedance 2.5

O character sheet é o que trava o rosto entre gerações. Sem ele, o personagem muda de cara no meio do vídeo.

## Modelo de imagem

- **Use GPT-Image / GPT-2** para pessoas — textura de pele realista, poros, imperfeições.
- **Não use Nano Banana Pro** para rosto — entrega pele plástica.
- Nano Banana Pro / Seedream **são bons para locação**.

## Prompt do character sheet

Suba **uma única foto de referência** do personagem junto com este prompt:

```
Create a professional character reference sheet on a plain light grey background,
laid out as a single wide image.

TOP ROW, five full-body views of the same person, evenly spaced, each labelled in
small grey uppercase text above it: FRONT, SIDE, BACK, FRONT CLOSE-UP, TOP-DOWN VIEW.
A vertical centimetre ruler runs down the right edge marked 0 to 180 CM.

BOTTOM ROW, a strip of labelled detail tiles: HAIR DETAIL, EYE DETAIL, FACIAL HAIR
DETAIL, SKIN TEXTURE, <GARMENT> FABRIC, <GARMENT> FABRIC, FOOTWEAR DETAIL, and a
COLOR PALETTE tile with five hex swatches.

BOTTOM BAR, small uppercase text: HEIGHT: <x> CM | WEIGHT: <x> KG | NATIONALITY: <x>
| OCCUPATION: <x> | NOTES: <traços marcantes>

The person: <descrição física completa — idade, tipo físico, cabelo, pelos faciais,
olhos, tom de pele, marcas>.
Wearing: <cada peça de roupa com cor e caimento>.
Neutral expression, arms relaxed at sides, even studio lighting, no shadows on the
background. Photorealistic, natural skin texture with visible pores and imperfections,
no plastic smoothing, no HDR.
```

## Regras

- **Itere.** O primeiro sheet quase nunca é o certo. Teste com chapéu, sem chapéu, cabelo diferente, idade diferente. Você vai *sentir* quando acertar.
- **Um sheet por personagem**, inclusive figurantes que aparecem em close.
- Quando for referenciar no Seedance, suba **2 a 3 vistas** (frontal + perfil + close), não as cinco — o modelo trava melhor o rosto com menos referências conflitantes.
- Para referências visuais de estilo, **não copie** um personagem existente. Use como inspiração e redesenhe com sua própria virada criativa.
- O nome que você usa no bloco `[CAST]` do prompt tem que ser **exatamente** o nome tagueado na referência da plataforma.

## Sheets de produto/locação

Mesma lógica:
- **Produto:** múltiplos ângulos, embalagem legível, fundo neutro, iluminação de estúdio.
- **Locação:** gere **sem pessoas na imagem**, a partir de um frame de referência com o color grade que você quer. É esta imagem que trava o grade do projeto inteiro.
