# Ezra - Telegram Digest Bot

Ezra is a Telegram bot that collects data from different sources (telegram channels) and forms daily digest with the most important messages. It handles message deduplication and uses LLMs like ChatGPT for summarizing content.

## Name Origin

The bot is named after Ezra the Scribe, a Jewish priest and scholar who led the return of exiles from Babylon and is credited with restoring and preserving the Torah in the 5th century BCE. Just as Ezra gathered and preserved important texts for his people, this bot collects and preserves important messages from various channels, creating meaningful digests for its users.

## Features

- **Daily Digest**: Automatically generates and sends digest at 08:00 daily
- **Admin Controls**: Admin can manage channel sources
- **Message Deduplication**: Prevents duplicate content in digests  
- **LLM Summarization**: Uses OpenAI GPT for intelligent content summarization
- **User Management**: Users can subscribe/unsubscribe from digests
- **Containerized**: Runs in Podman/Docker containers

## Admin Features

- List, add and remove channels from bot's sources
- Add channels by forwarding messages from them
- Only @jewpacabra has admin privileges

## User Commands

- `/start` - Subscribe to daily digests at 08:00
- `/stop` - Unsubscribe from daily digests  
- `/digest` - Get the latest digest manually

## Admin Commands

- `/list_channels` - Show all configured channels
- `/add_channel <channel_id>` - Add channel by ID
- `/remove_channel <channel_id>` - Remove channel by ID
- `/regenerate` - Manually regenerate and send today's digest
- Forward any message from a channel to automatically add it

## Setup

### Prerequisites

- Python 3.12+
- Telegram Bot Token (from @BotFather)
- OpenAI API Key
- Podman or Docker

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd ezra
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your tokens
   ```

3. **Configure environment variables**:
   ```bash
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   OPENAI_API_KEY=your_openai_api_key
   OPENAI_MODEL=gpt-3.5-turbo
   ```

### Running with Podman

```bash
# Make script executable and run
./run-podman.sh
```

### Running with Docker Compose

```bash
docker-compose up -d
```

### Running Locally

```bash
# Install dependencies
uv sync

# Run the bot
uv run python main.py
```

## Architecture

- **Database**: SQLite with tables for users, channels, messages, and digests
- **Scheduler**: APScheduler for daily digest generation at 08:00
- **LLM**: OpenAI GPT integration for content summarization
- **Bot Framework**: python-telegram-bot for Telegram API

## Container Setup

The bot runs as root inside the container to avoid permission issues with the mounted SQLite database volume. Data is persisted in `./data/ezra.db`.

## Development

```bash
# Install dependencies
uv add <package-name>

# Run locally for development
uv run python main.py
```


