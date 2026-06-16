#!/bin/bash
echo "=== Installing ffmpeg ==="
apt-get update
apt-get install -y ffmpeg
echo "=== Installing Python dependencies ==="
pip install -r requirements.txt
echo "=== Checking ffmpeg ==="
ffmpeg -version
