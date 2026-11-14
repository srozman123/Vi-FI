#!/bin/zsh
# Runs the whole test: ./record.sh
cd "$(dirname "$0")"
.venv/bin/python analysis/record.py
