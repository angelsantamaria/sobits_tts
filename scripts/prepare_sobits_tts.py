#!/usr/bin/env python3

import importlib.util
import os
from pathlib import Path
import site
import shutil
import subprocess
import sys


PYTHON_PACKAGES = [
    "soundfile",
    "pygame",
    "av",
    "piper-tts",
    "onnxruntime",
]

IMPORT_MODULES = [
    "soundfile",
    "pygame",
    "av",
    "piper",
    "onnxruntime",
]


def env_enabled(name, default=True):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "off", "no"}


def run(command):
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def have_modules():
    return all(importlib.util.find_spec(module) is not None for module in IMPORT_MODULES)


def ensure_pip():
    if subprocess.run([sys.executable, "-m", "pip", "--version"], check=False).returncode == 0:
        return

    apt_get = shutil.which("apt-get")
    if apt_get is None:
        raise RuntimeError("python3-pip is missing and apt-get is unavailable")

    installer = [apt_get]
    if os.geteuid() != 0:
        sudo = shutil.which("sudo")
        if sudo is None:
            raise RuntimeError("python3-pip is missing and sudo is unavailable")
        installer.insert(0, sudo)

    run(installer + ["update", "-y"])
    run(installer + ["install", "-y", "python3-pip"])


def user_site_visible():
    return bool(getattr(site, "ENABLE_USER_SITE", False))


def pip_install(packages):
    if have_modules():
        return

    ensure_pip()
    commands = []

    if user_site_visible():
        commands.append([sys.executable, "-m", "pip", "install", "--user", "--upgrade"] + packages)

    commands.append([
        sys.executable,
        "-m",
        "pip",
        "install",
        "--break-system-packages",
        "--upgrade",
    ] + packages)

    for command in commands:
        result = subprocess.run(command, check=False)
        if result.returncode == 0:
            return

    run(commands[-1])


def requested_models():
    raw_models = os.environ.get("SOBITS_TTS_PIPER_MODELS", "en_US-lessac-medium")
    return [model for model in raw_models.split() if model.strip()]


def download_models():
    if not env_enabled("SOBITS_TTS_DOWNLOAD_MODELS", True):
        return

    model_dir = Path(os.environ.get("SOBITS_TTS_PIPER_MODEL_DIR", "~/.sobits_tts/piper")).expanduser()
    model_dir.mkdir(parents=True, exist_ok=True)

    for model in requested_models():
        model_name = model.removesuffix(".onnx")
        model_path = model_dir / f"{model_name}.onnx"
        config_path = model_dir / f"{model_name}.onnx.json"
        if model_path.exists() and config_path.exists():
            print(f"[sobits_tts] Piper model already present: {model_name}", flush=True)
            continue
        run([
            sys.executable,
            "-m",
            "piper.download_voices",
            model_name,
            "--download-dir",
            str(model_dir),
        ])


def main():
    if not env_enabled("SOBITS_TTS_PREPARE_RUNTIME", True):
        print("[sobits_tts] Runtime preparation disabled by SOBITS_TTS_PREPARE_RUNTIME", flush=True)
        return

    if env_enabled("SOBITS_TTS_INSTALL_PYTHON_DEPS", True):
        pip_install(PYTHON_PACKAGES)
    download_models()


if __name__ == "__main__":
    main()
