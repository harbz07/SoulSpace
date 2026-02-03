# SoulSpace Calyx

A Discord bot for the SoulSpace community with Notion integration, OAuth support, and comprehensive monitoring.

## Features

- 🤖 **Discord Bot**: Interact with users across multiple channels
- 📝 **Notion Integration**: Log traces, create tasks, and monitor agent health
- 🔐 **Google OAuth**: Authenticate with Gmail and Calendar
- 📊 **Health Monitoring**: Built-in health check endpoints for monitoring
- 📝 **Structured Logging**: File-rotated logs with multiple verbosity levels
- ✅ **Comprehensive Testing**: Unit and integration tests with >70% coverage

## Setup

### Prerequisites

- Python 3.12+
- Discord Bot Token
- Notion API Token (optional)
- Google OAuth Credentials (optional)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/harbz07/SoulSpace.git
cd SoulSpace
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
Create a `.env` file in the project root:
```env
# Discord Configuration
DISCORD_TOKEN=your_discord_token

# Channel IDs
CHANNEL_THE_WELL=123456789
CHANNEL_ENGINE_LOGS=987654321
CHANNEL_THE_SCREAM=111222333
CHANNEL_THE_MIRROR=444555666
CHANNEL_THE_COUNSEL=777888999

# Notion Configuration (optional)
NOTION_TOKEN=your_notion_token
NOTION_TASK_BOARD_ID=your_task_board_id
NOTION_TRACE_LOG_ID=your_trace_log_id
NOTION_AGENT_HEALTH_ID=your_agent_health_id
NOTION_KNOWLEDGE_BASE_ID=your_knowledge_base_id
NOTION_MEMORY_ARCHIVE_ID=your_memory_archive_id
JOURNAL_DB_ID=your_journal_db_id

# Google OAuth Configuration (optional)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
```

5. Run the bot:
```bash
python calyx.py
```

## Testing

### Run Tests

Run all tests:
```bash
pytest tests/
```

Run tests with coverage:
```bash
pytest tests/ --cov --cov-report=html
```

Quick smoke test:
```bash
./smoke_test.sh
```

For detailed testing documentation, see [TESTING.md](TESTING.md).

## Logging

The bot uses structured logging with automatic file rotation:

- **Console Output**: Simple format for real-time monitoring
- **Main Log**: Detailed logs in `logs/calyx.log` (rotates at 10MB, keeps 5 backups)
- **Error Log**: Errors only in `logs/errors.log` (rotates at 10MB, keeps 5 backups)

### Log Levels

- `INFO`: General operational messages
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `DEBUG`: Detailed debugging information

### View Logs

```bash
# Tail main log
tail -f logs/calyx.log

# Tail error log
tail -f logs/errors.log

# View recent errors
tail -100 logs/errors.log
```

## Health Checks and Monitoring

The bot includes built-in health check endpoints for monitoring:

### Endpoints

- **`GET /health`**: Basic health status
  ```json
  {
    "status": "healthy",
    "service": "Calyx",
    "timestamp": "2024-01-01T00:00:00.000Z",
    "uptime_seconds": 3600
  }
  ```

- **`GET /health/live`**: Liveness probe (Kubernetes-style)
  ```json
  {
    "status": "alive"
  }
  ```

- **`GET /health/ready`**: Readiness probe (checks Discord and Notion)
  ```json
  {
    "status": "ready",
    "checks": {
      "discord": true,
      "notion": true
    }
  }
  ```

- **`GET /metrics`**: Basic metrics
  ```json
  {
    "uptime_seconds": 3600,
    "discord_latency_ms": 45.2,
    "guild_count": 1,
    "user_count": 150,
    "notion_connected": true
  }
  ```

### Health Server Configuration

The health server runs on port 8080 by default. Access endpoints at:
```
http://localhost:8080/health
http://localhost:8080/health/live
http://localhost:8080/health/ready
http://localhost:8080/metrics
```

### Monitoring with Docker/Kubernetes

Example Kubernetes liveness and readiness probes:
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

## Architecture

### Key Components

- **`calyx.py`**: Main Discord bot implementation
- **`calyx_notion_integration.py`**: Notion API integration
- **`health_server.py`**: Health check and metrics server

### Channel Types

The bot operates across multiple specialized channels:

- **The Well**: Main interaction channel
- **Engine Logs**: System trace logs
- **The Scream**: Error reporting
- **The Mirror**: Status updates
- **The Counsel**: Commands and control

## Commands

### Slash Commands

- `/pause`: Pause bot operations
- `/unpause`: Resume bot operations
- `/export_databases`: Export Notion databases to JSON
- `/connect_gmail`: Connect Gmail account via OAuth
- `/connect_calendar`: Connect Google Calendar via OAuth

## Development

### Project Structure

```
SoulSpace/
├── calyx.py                      # Main bot
├── calyx_notion_integration.py   # Notion integration
├── health_server.py              # Health check server
├── requirements.txt              # Dependencies
├── pytest.ini                    # Test configuration
├── smoke_test.sh                 # Quick test script
├── TESTING.md                    # Testing documentation
├── logs/                         # Log files (git-ignored)
├── tokens/                       # OAuth tokens (git-ignored)
└── tests/                        # Test suite
    ├── __init__.py
    ├── conftest.py
    ├── test_helpers.py
    ├── test_calyx.py
    └── test_notion_integration.py
```

### Adding New Features

1. Write tests first (TDD)
2. Implement the feature
3. Add logging statements
4. Update health checks if needed
5. Update documentation
6. Run tests and ensure coverage

### Code Style

- Use type hints where possible
- Add docstrings to functions
- Follow PEP 8 style guide
- Use structured logging (no print statements)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

[Add your license here]

## Support

For issues and questions:
- Open an issue on GitHub
- Check [TESTING.md](TESTING.md) for testing help
- Review logs in `logs/` directory

## Changelog

### Version 1.1.0 (Current)
- ✅ Added comprehensive test framework with pytest
- ✅ Implemented structured logging with file rotation
- ✅ Added health check endpoints for monitoring
- ✅ Added test coverage reporting
- ✅ Created testing documentation

### Version 1.0.0
- Initial release with Discord bot
- Notion integration
- Google OAuth support
