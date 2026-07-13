#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================"
echo " Installing SoBiTS TTS runtime"
echo "========================================"

if command -v apt-get >/dev/null 2>&1; then
  apt_cmd=(apt-get)
  if [ "$(id -u)" -ne 0 ]; then
    apt_cmd=(sudo apt-get)
  fi
  "${apt_cmd[@]}" update -y
  "${apt_cmd[@]}" install -y \
    pulseaudio \
    pulseaudio-utils \
    python3-pip \
    "ros-${ROS_DISTRO:-jazzy}-vision-msgs"
fi

SOBITS_TTS_DOWNLOAD_MODELS=0 python3 "${script_dir}/scripts/prepare_sobits_tts.py"

echo "========================================"
echo " SoBiTS TTS runtime installation complete"
echo "========================================"
