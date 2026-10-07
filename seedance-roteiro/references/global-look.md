# Presets de GLOBAL LOOK

O bloco `[GLOBAL LOOK]` vai no topo de **todo** prompt e não muda entre gerações do mesmo projeto. É ele que faz todos os cortes parecerem filmados na mesma câmera, no mesmo dia, com o mesmo grade.

Anatomia: `corpo de câmera` + `família de lentes` + `película/temperatura` + `aspect ratio` + `T-stop` + `tratamento de textura` + `grade nomeado` + `comportamento da câmera` + `regra de performance/áudio`.

Sempre termine com: `Handheld with micro-drift, never locked off. Naturalistic performance, real dialogue sync, no music.` (ajuste o comportamento de câmera conforme o projeto).

---

## Comédia de TV — single-camera

**Este é o preset que mais dá errado se você copiar o de cinema por inércia.** Comédia de TV é
luz alta, chapada, foco mais profundo e sombra fraca. Um bloco cinematográfico (T2.8, halation,
blacks levantados, foco raso) entrega um filme lindo que **não parece comédia de TV**. A
primeira linha tem que negar o cinema explicitamente.

```
Single-camera television comedy, not cinematic film. Arri 416, Zeiss Ultra Prime 24mm and
32mm, 1.78:1 spherical, T4, medium depth of field with both subject and background readable,
bright even key light, soft fill, weak shadows, no deep blacks, no moody shadow pools, low
contrast, mild fine grain, neutral-to-cool white balance, no halation, no lens flare, no
anamorphic look, no HDR. Broadcast comedy grade: naturally lit interiors, warm neutral skin,
walls kept bright and readable, windows softly blown out. Camera handheld but calm, small drift
only, always eye level. Naturalistic comedic performance.
```

## Comercial de praia / verão

```
Arricam LT, Cooke S4/i primes, 35mm Kodak Vision3 500T, 1.85:1 spherical, T2.8,
shallow depth of field, halation on highlights, fine organic grain, lifted milky
blacks, low contrast, no sharpening, no HDR. Riviera Gouache grade: terracotta-warm
skin as the hero tone, aqua-teal sea and sky field, cream sand, chromatic blue
shadows, hazy sun bloom. Handheld with micro-drift, never locked off. Naturalistic
performance, real dialogue sync, no music.
```

## Drama noturno / urbano

```
Arri Alexa 35, Panavision C-series anamorphic, 2.39:1, T2.0, very shallow depth of
field, strong anamorphic flare, heavy halation on sodium practicals, fine grain,
crushed cool blacks, high contrast, no sharpening, no HDR. Sodium-and-cyan night
grade: amber street practicals against cyan ambient spill, wet asphalt speculars,
desaturated skin. Slow dolly moves, never handheld. Naturalistic performance,
real dialogue sync, no music.
```

## Comercial de produto / clean

```
Arri Alexa Mini LF, Zeiss Supreme Prime primes, 1.78:1 spherical, T2.8, shallow
depth of field, minimal halation, very fine grain, neutral blacks, medium contrast,
no sharpening, no HDR. Clean commercial grade: neutral daylight balance, hero
product colour fully saturated, environment desaturated one stop, soft wraparound
key with large source. Locked tripod with micro-drift. Naturalistic performance,
real dialogue sync, no music.
```

## Documentário / found footage

```
Sony FX3, Sigma Art zooms, 1.78:1, T4, deep depth of field, no halation, digital
noise in shadows, neutral contrast, slight over-sharpening, no HDR. Available-light
grade: mixed colour temperature left uncorrected, green fluorescent cast indoors,
blown windows. Shoulder-mounted handheld with search-and-reframe, occasional focus
hunting. Naturalistic performance, real dialogue sync, no music.
```

---

## Como criar um preset novo

1. Ache um frame real que você ama (Pinterest, Cosmos, ShotDeck).
2. Nomeie o grade com uma expressão inventada e evocativa (`Riviera Gouache`, `Sodium-and-cyan night`). O modelo responde bem a nomes de grade.
3. Declare o **tom de pele herói** primeiro — é o que ancora tudo.
4. Declare a **cor das sombras** explicitamente. É o que mais separa look cinematográfico de look de IA.
5. Sempre inclua as negativas de textura: `no sharpening, no HDR` — sem isso vem aquele plástico digital.
6. **Se o alvo não é cinema, negue o cinema na primeira linha.** O default do modelo é filme
   cinematográfico; qualquer outro gênero (TV, documentário, vídeo caseiro, transmissão ao vivo,
   institucional) precisa ser afirmado *e* o cinema negado, ou ele volta ao default.

## Termos que puxam para cinema (use só se você quer cinema)

`shallow depth of field` · `T1.4`–`T2.8` · `halation` · `lifted milky blacks` · `anamorphic` ·
`lens flare` · `500T` · `moody` · `bokeh`

## Termos que puxam para TV / naturalista

`bright even key light` · `T4`–`T5.6` · `medium depth of field` · `weak shadows` ·
`no deep blacks` · `both subject and background readable` · `eye level` · `calm handheld`
