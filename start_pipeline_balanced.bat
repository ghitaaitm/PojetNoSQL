@echo off
echo Starting Mastodon ABSA Pipeline - Mode: BALANCED
set FILTER_MODE=balanced
python startup_realtime_v2.py
pause
