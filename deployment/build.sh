#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
PKG_DIR="$ROOT_DIR/deployment/build/function"
ZIP_PATH="$ROOT_DIR/deployment/build/function.zip"
WHEEL_DIR="$ROOT_DIR/deployment/build/wheels"

rm -rf "$PKG_DIR" "$ZIP_PATH" "$WHEEL_DIR"
mkdir -p "$PKG_DIR" "$WHEEL_DIR"

python3 -m pip install --upgrade pip

# Download wheels for Lambda (Amazon Linux 2023 uses manylinux_2_28, Python 3.12, x86_64)
python3 -m pip download \
  --platform manylinux_2_28_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --abi cp312 \
  --only-binary=:all: \
  -r "$ROOT_DIR/deployment/requirements-lambda.txt" \
  -d "$WHEEL_DIR"

# Install from downloaded wheels into the package directory
python3 -m pip install --no-index --find-links "$WHEEL_DIR" -r "$ROOT_DIR/deployment/requirements-lambda.txt" -t "$PKG_DIR"

cp -R "$ROOT_DIR/app" "$PKG_DIR/app"
cp "$ROOT_DIR/handler.py" "$PKG_DIR/handler.py"

( cd "$PKG_DIR" && zip -r "$ZIP_PATH" . )

echo "Built: $ZIP_PATH"


