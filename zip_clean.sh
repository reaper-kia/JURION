#!/usr/bin/env bash
set -e

PROJECT_NAME="$(basename "$PWD")"
TMP_DIR="/tmp/${PROJECT_NAME}_clean"
ZIP_PATH="../${PROJECT_NAME}_clean.zip"

rm -rf "$TMP_DIR"
rm -f "$ZIP_PATH"

rsync -av ./ "$TMP_DIR" \
  --exclude ".git" \
  --exclude ".idea" \
  --exclude ".vscode" \
  --exclude "myenv" \
  --exclude "venv" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude ".pytest_cache" \
  --exclude ".ruff_cache" \
  --exclude ".mypy_cache" \
  --exclude ".coverage" \
  --exclude "htmlcov" \
  --exclude ".env" \
  --include ".env.example" \
  --include ".env.*.example" \
  --exclude ".env.*" \
  --exclude "*.log" \
  --exclude "logs" \
  --exclude "node_modules" \
  --exclude "frontend/node_modules" \
  --exclude "frontend/dist" \
  --exclude "frontend/.vite" \
  --exclude "dist" \
  --exclude "build" \
  --exclude "*.sqlite" \
  --exclude "*.db" \
  --exclude "uploads" \
  --exclude "media"

cd /tmp
zip -r "${PROJECT_NAME}_clean.zip" "${PROJECT_NAME}_clean" >/dev/null

mv "${PROJECT_NAME}_clean.zip" "$OLDPWD/$ZIP_PATH"

echo "Created: $ZIP_PATH"