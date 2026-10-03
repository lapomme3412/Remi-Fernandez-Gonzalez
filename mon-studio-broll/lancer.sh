#!/usr/bin/env bash
# Lance Mon Studio B-roll (installe ce qu'il faut la première fois).
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
.venv/bin/pip install -q -r requirements.txt
exec .venv/bin/python app.py
