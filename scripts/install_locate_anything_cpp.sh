#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/vendor"
mkdir -p "$VENDOR"

cd "$VENDOR"
if [ ! -d locate-anything.cpp ]; then
  git clone --recursive https://github.com/mudler/locate-anything.cpp.git
else
  git -C locate-anything.cpp submodule update --init --recursive
fi

cd locate-anything.cpp
cmake -B build -DLA_BUILD_CLI=ON -DLA_GGML_METAL=ON
cmake --build build --config Release -j"$(sysctl -n hw.logicalcpu)"

cat <<'MSG'

locate-anything.cpp has been built.

Next:
1. Download locate-anything-q8_0.gguf into:
   vendor/locate-anything.cpp/models/locate-anything-q8_0.gguf
2. Smart LabelImg will automatically use LocateAnythingBackend when the CLI and model exist.

Smart LabelImg works now with ClassicalVisionBackend while the 3B model is being prepared.
MSG
