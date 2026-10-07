---
name: editar-anuncio
description: Edita um anúncio (ADS) no OpenChatCut a partir da copy do cliente, dos brutos e de um vídeo de referência ou PERFIL.md — monta gancho/body, inserts, tela dividida, legendas no estilo da referência, transições, SFX, exporta MP4 e compara com a referência. Use quando o usuário disser /editar-anuncio, "edita esse anúncio igual à referência", "monta o AD com essa copy e esses brutos", ou pedir uma edição de teste no OpenChatCut.
---

# Editar anúncio no OpenChatCut

Entrada típica (pasta do job): copy (`.docx`), vídeo de referência, `BRUTOS/` (hooks + body).
Saída: projeto no OpenChatCut + MP4 em `EXPORT/` + `comparacao.md` (referência × edição).

Ferramentas:
- `REF=~/.claude/skills/analisar-referencia/ref` — análise de vídeo (skill `analisar-referencia`).
- `OCC=~/.claude/skills/editar-anuncio/occ` — controle do OpenChatCut (MCP + janela do app) e contornos
  dos defeitos do v0.2.15 no Windows. `$OCC --help` lista os comandos.

Leia `references/openchatcut-receitas.md` antes de mexer em legenda, tela dividida ou transição.

## 1. Entender o pedido
1. `$OCC copy <arquivo.docx>` → tipo de AD, formato, qual hook (ex.: nome `…_H1_…` = hook 1), instruções de
   legenda/trilha, qual é a referência.
2. Referência: se já existe `referencias/<nome>/PERFIL.md`, use-o. Senão rode a skill `analisar-referencia`
   (preparar → analisar → ler evidências → PERFIL.md). Confirme no perfil: tela dividida, transições
   (tipo + duração em quadros), paginação da legenda (1 linha? limite de caracteres), SFX, música.
3. Transcreva os brutos com o modelo grande (bem melhor que o Whisper Base do app, principalmente fora do inglês):
   ```bash
   ffmpeg -v error -y -i BRUTOS/HOOKS.mp4 -vn -ac 1 -ar 16000 trabalho/HOOKS.wav
   $REF _transcrever trabalho/HOOKS.wav trabalho/HOOKS.transcript.json cuda large-v3-turbo <idioma>
   ```
   Mapeie cada hook e o body por tempo (primeira/última palavra) comparando com a copy.

## 2. Preparar material
- Inserts/B-roll: da pasta do cliente; se só existirem na referência, recorte com ffmpeg a região útil
  (fora da legenda queimada) e gere arquivos 1080×1920 com a imagem na posição final (o resto preto —
  vai ser cortado com `flexCrop`). Alinhe cada troca de insert à **mesma palavra** da referência.
- Tudo o que for importado precisa estar num caminho local; depois de importar rode `$OCC corrigir-midia`.

## 3. Montar no OpenChatCut
```bash
$OCC novo-projeto "NOME (teste)"        # ou: $OCC abrir <projeto_id>
$OCC call import_assets '{"paths":["D:/.../HOOKS.mp4", ...]}'
$OCC corrigir-midia                     # obrigatório antes de qualquer render/quadro
```
- Timeline: `edit_item` adds com `sourceStartFrame`/`sourceDurationInFrames` (30 fps). V1 = talking head,
  V2 = inserts. Bruto que não é 9:16 exato: `transform.scale` ~1.03 para não sobrar faixa preta.
- `$OCC aplicar` depois de cada bloco de mudanças (renders e quadros só enxergam o que foi aplicado com mídia).
- Transcrição: `$OCC transcricao HOOKS.mp4 trabalho/HOOKS.transcript.json --ate <fim do trecho usado em s>`
  (idem BODY.mp4). Isso fecha o editor, grava a transcrição no projeto e reabre.
- Legenda, tela dividida e transições: receitas em `references/openchatcut-receitas.md`.
- Teste/não publicar: `update_watermark {"enabled":true,"text":"TESTE - NAO PUBLICAR","position":"tr"}`.

## 4. Conferir e exportar
- `$OCC quadros 1,4.5,8.3,30 --para trabalho/check.jpg` e olhe: legenda (linhas, posição), costura da tela
  dividida, faixas pretas, marca d'água.
- `$OCC exportar EXPORT/<nome>.mp4` (renderiza WebM e converte; ~10–15 min para 2 min de vídeo).
- Compare com a referência e corrija o que estiver ⚠️:
  ```bash
  $REF preparar EXPORT/<nome>.mp4 --nome <nome>-edicao --raiz referencias --substituir
  $REF analisar referencias/<nome>-edicao --idioma <idioma> --pular audio,evidencias --sem-shazam
  $REF comparar referencias/<ref> referencias/<nome>-edicao --legenda-size <sizePx usado>
  ```

## Regras
- Não copie marca, logo, pessoas ou claims da referência; inserts da referência só em teste interno.
- Música identificada ≠ música liberada.
- Reporte ao usuário o que ficou diferente da referência (com a tabela do `comparar`), não só o que deu certo.
