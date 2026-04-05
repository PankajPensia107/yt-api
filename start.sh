#!/usr/bin/env bash

# Install Tesseract
apt-get update
apt-get install -y tesseract-ocr

# Start API
uvicorn main:app --host 0.0.0.0 --port 10000
