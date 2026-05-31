@echo off
llama\llama-server.exe ^
  -m models\tinyllama.gguf ^
  -c 4096 ^
  -ngl 999 ^
  --host 127.0.0.1 ^
  --port 8080 ^
  -n 256