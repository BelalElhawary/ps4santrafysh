@echo off
cd /d "%~dp0"
python update_cache_hashes.py %*
pause
