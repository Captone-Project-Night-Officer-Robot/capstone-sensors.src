#!/usr/bin/env bash
set -e

mkdir -p "$HOME/workspace"
cd "$HOME/workspace"

if [ -d "RaspberryPi-4WD-Car" ]; then
  echo "Official Yahboom repo already exists:"
  echo "  $HOME/workspace/RaspberryPi-4WD-Car"
else
  echo "Cloning official Yahboom RaspberryPi-4WD-Car repo..."
  git clone https://github.com/YahboomTechnology/RaspberryPi-4WD-Car.git
fi

echo ""
echo "Official code folder:"
echo "  $HOME/workspace/RaspberryPi-4WD-Car/4.Code/python"
echo ""
echo "Files:"
ls "$HOME/workspace/RaspberryPi-4WD-Car/4.Code/python" || true
