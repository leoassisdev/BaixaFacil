#!/usr/bin/env bash
# Empacota o BaixaFacil pra plataforma ATUAL.
#
# O PyInstaller NAO faz build cruzado: mac so gera mac, Windows so gera Windows,
# e mac arm64 so gera arm64. Pras 3 plataformas de uma vez, use o workflow do
# GitHub Actions (.github/workflows/build.yml), que roda numa maquina de cada.
#
# Assim como no Space Scanner, o build acontece no DISCO INTERNO: o repo mora
# no SSD EXTERNO, que e exFAT, e os arquivos-sombra `._*` que o macOS cria la
# entram no bundle e corrompem o empacotamento.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRABALHO="$(mktemp -d /tmp/baixafacil-build.XXXXXX)"
trap 'rm -rf "$TRABALHO"' EXIT

echo "▸ repo:     $RAIZ"
echo "▸ trabalho: $TRABALHO (APFS)"

rsync -a \
  --exclude .venv --exclude venv --exclude build --exclude dist --exclude .git \
  --exclude '._*' --exclude '.DS_Store' --exclude '__pycache__' --exclude '*.dmg' \
  "$RAIZ/" "$TRABALHO/"

cd "$TRABALHO"

echo "▸ criando ambiente e instalando dependencias…"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt pyinstaller pillow

echo "▸ garantindo ffmpeg/ffprobe da plataforma…"
.venv/bin/python scripts/baixar_ffmpeg.py

echo "▸ empacotando…"
.venv/bin/pyinstaller --noconfirm --clean BaixaFacil.spec

echo "▸ trazendo o resultado de volta…"
rm -rf "$RAIZ/dist"
mkdir -p "$RAIZ/dist"
COPYFILE_DISABLE=1 cp -R "$TRABALHO"/dist/* "$RAIZ/dist/"

echo
echo "✓ pronto:"
ls -1 "$RAIZ/dist" | grep -v '^\._' | sed 's/^/   /'
