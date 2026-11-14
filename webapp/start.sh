#!/bin/zsh
# Starts the live web app. Then open http://localhost:8000
cd "$(dirname "$0")/.."
.venv/bin/python webapp/server.py
