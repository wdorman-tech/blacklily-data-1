@echo off
rem Start Ollama with the server settings every local run used. The runner reads these flags back
rem from this log, so keep the redirect.
set OLLAMA_FLASH_ATTENTION=1
set OLLAMA_KV_CACHE_TYPE=q8_0
set OLLAMA_NUM_PARALLEL=1
set OLLAMA_KEEP_ALIVE=30m
if not exist "%~dp0..\logs" mkdir "%~dp0..\logs"
ollama serve >> "%~dp0..\logs\ollama-server.log" 2>&1
