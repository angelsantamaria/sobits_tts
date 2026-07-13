#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "========================================"
echo " Preparing Piper TTS runtime"
echo "========================================"

python3 "${script_dir}/scripts/prepare_sobits_tts.py"

echo "========================================"
echo " Piper TTS runtime ready"
echo "========================================"
