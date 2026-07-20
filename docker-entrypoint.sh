#!/bin/bash
ollama serve &
sleep 3

ollama pull qwen2.5:3b-instruct
ollama pull deepseek-r1:7b
ollama pull minicpm-v:latest
ollama pull qwen3:4b-instruct
ollama pull qwen2.5:7b-instruct

python start.py