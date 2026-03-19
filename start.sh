#!/bin/sh

# Start Ollama server in background
ollama serve &

# Wait for server to start
sleep 5

# Pull model
ollama pull llama3

# Keep container alive
wait