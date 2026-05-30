#!/usr/bin/env bash
set -e

echo "Installing Raspberry Pi dependencies..."

sudo apt update
sudo apt install -y \
  python3-pip \
  python3-venv \
  python3-opencv \
  python3-picamera2 \
  python3-rpi.gpio \
  libportaudio2 \
  git

echo "Creating Python virtual environment..."

python3 -m venv .venv --system-site-packages
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Done."
echo "Activate with:"
echo "  source .venv/bin/activate"
