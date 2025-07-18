#!/usr/bin/env bash
# exit on error
set -e

# Install system dependencies (Tesseract)
apt-get update
apt-get install -y tesseract-ocr

# Install Python dependencies
pip install -r requirements.txt