#!/usr/bin/env bash
set -euo pipefail

# Puxa alterações feitas no repositório espelho wagmmss/Medquest-aistudio
# (commits acima do snapshot inicial) e aplica no MedQuest original via patch,
# protegendo imagens e diretórios excluídos do espelho.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_REMOTE="${AI_STUDIO_REMOTE:-https://github.com/wagmmss/Medquest-aistudio.git}"
TMP_DIR="$(mktemp -d)"
PATCH_FILE="$TMP_DIR/ai-studio.patch"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "Clonando ${SOURCE_REMOTE}..."
git clone -q --branch main "$SOURCE_REMOTE" "$TMP_DIR/repo"

cd "$TMP_DIR/repo"
ROOT_COMMIT="$(git rev-list --max-parents=0 HEAD | tail -n 1)"
HEAD_COMMIT="$(git rev-parse HEAD)"

if [ "$ROOT_COMMIT" = "$HEAD_COMMIT" ]; then
  echo "Nenhuma alteração nova encontrada em ${SOURCE_REMOTE} (HEAD ainda está no snapshot base)."
  exit 0
fi

COMMIT_COUNT="$(git rev-list --count "${ROOT_COMMIT}..HEAD")"
echo "Encontrados ${COMMIT_COUNT} commit(s) novos no AI Studio. Gerando patch..."

git diff --binary "${ROOT_COMMIT}..HEAD" -- . \
  ':!package.json' \
  ':!package-lock.json' \
  ':!app/backend/data' \
  ':!app/backend/static/images' \
  ':!app/frontend/public/images' \
  ':!docs/audits' \
  ':!archive' \
  > "$PATCH_FILE"

if [ ! -s "$PATCH_FILE" ]; then
  echo "Patch vazio após filtros de proteção. Nada a aplicar."
  exit 0
fi

cd "$REPO_ROOT"
echo "Verificando aplicação do patch em ${REPO_ROOT}..."
git apply --check "$PATCH_FILE"

echo "Aplicando alterações no working tree do MedQuest..."
git apply --3way "$PATCH_FILE"

echo "Concluído! Revise as alterações com 'git status' e 'git diff' antes de commitar ou rodar ./deploy.sh."
git status -s
