#!/usr/bin/env bash
set -euo pipefail

# Sincroniza um snapshot enxuto (apenas código-fonte e configs essenciais)
# da branch atual do MedQuest para o repositório espelho wagmmss/Medquest-aistudio,
# mantendo o repositório principal e o deploy (Vercel/Render) intactos.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_REMOTE="${AI_STUDIO_REMOTE:-https://github.com/wagmmss/Medquest-aistudio.git}"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

cd "$REPO_ROOT"

echo "Exportando snapshot enxuto de HEAD ($(git rev-parse --short HEAD))..."
git archive --format=tar HEAD \
  -- . \
  ':!app/backend/data' \
  ':!app/backend/static/images' \
  ':!app/frontend/public/images' \
  ':!docs/audits' \
  ':!archive' \
  | tar -x -C "$TMP_DIR"

cat > "$TMP_DIR/package.json" <<'EOF'
{
  "name": "medquest-aistudio",
  "version": "0.1.0",
  "private": true,
  "workspaces": [
    "app/frontend"
  ],
  "scripts": {
    "dev": "npm --prefix app/frontend run dev",
    "build": "npm --prefix app/frontend run build",
    "start": "npm --prefix app/frontend run start",
    "lint": "npm --prefix app/frontend run lint"
  }
}
EOF

FILE_COUNT="$(find "$TMP_DIR" -type f | wc -l)"
TOTAL_SIZE="$(du -sh "$TMP_DIR" | cut -f1)"
echo "Snapshot gerado: ${FILE_COUNT} arquivos (${TOTAL_SIZE})."

cd "$TMP_DIR"
git init -q -b main
git config user.name "$(git -C "$REPO_ROOT" config user.name || echo 'MedQuest Sync')"
git config user.email "$(git -C "$REPO_ROOT" config user.email || echo 'sync@medquest.local')"
git add -A
git commit -q -m "chore: snapshot enxuto do MedQuest para Google AI Studio ($(git -C "$REPO_ROOT" rev-parse --short HEAD))"

echo "Enviando para ${TARGET_REMOTE}..."
git push --force "$TARGET_REMOTE" main

echo "Concluído! Repositório pronto para importação no Google AI Studio."
