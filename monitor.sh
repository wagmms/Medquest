#!/usr/bin/env bash
# MedQuest Live Ingestion Monitor Wrapper
cd "$(dirname "$0")"
app/backend/.venv/bin/python app/backend/scripts/monitor_tier1.py
