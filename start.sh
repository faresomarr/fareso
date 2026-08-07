#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

exec python bot_core.py
