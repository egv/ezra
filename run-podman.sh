#!/bin/bash

set -e

if [ ! -f ".env" ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

echo "Building Ezra bot container..."
podman build -t ezra-bot .

echo "Creating data directory..."
mkdir -p ./data

echo "Starting Ezra bot with podman..."
podman run -d \
    --name ezra-telegram-bot \
    --restart unless-stopped \
    --env-file .env \
    -v ./data:/app/data:Z \
    --user root \
    ezra-bot

echo "Bot started successfully!"
echo "Check logs with: podman logs -f ezra-telegram-bot"
echo "Stop with: podman stop ezra-telegram-bot"
echo "Remove with: podman rm ezra-telegram-bot"