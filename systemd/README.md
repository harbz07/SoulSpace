# Systemd Service Setup for Calyx

This directory contains systemd service files for running Calyx and MindBridge as system services.

## Quick Start

```bash
# Run the installer (as root)
sudo ./systemd/install.sh

# Start the services
sudo systemctl start calyx
sudo systemctl start mindbridge

# Enable auto-start on boot
sudo systemctl enable calyx mindbridge

# Check status
sudo systemctl status calyx
sudo systemctl status mindbridge
```

## Service Files

### calyx.service
- **Description**: Main Discord bot
- **User**: `calyx` (system user, created by installer)
- **Working Directory**: `/var/www/calyx`
- **Logs**: `journalctl -u calyx -f`
- **Health Check**: `curl http://localhost:8080/health`

### mindbridge.service
- **Description**: LLM routing HTTP server
- **User**: `calyx`
- **Working Directory**: `/var/www/calyx/mindbridge`
- **Logs**: `journalctl -u mindbridge -f`
- **Endpoint**: `http://localhost:3001`

## Commands

| Command | Description |
|---------|-------------|
| `sudo systemctl start calyx` | Start the Discord bot |
| `sudo systemctl stop calyx` | Stop the Discord bot |
| `sudo systemctl restart calyx` | Restart the bot |
| `sudo systemctl status calyx` | Check bot status |
| `sudo journalctl -u calyx -f` | View live logs |
| `sudo systemctl enable calyx` | Auto-start on boot |
| `sudo systemctl disable calyx` | Disable auto-start |

## Configuration

Services read environment from `/var/www/calyx/.env`. Make sure this file:
- Is owned by `calyx:calyx`
- Has permissions `640` (not world-readable)
- Contains all required API keys

## Troubleshooting

### Service fails to start
```bash
# Check logs
sudo journalctl -u calyx -n 50

# Check if .env is configured
sudo -u calyx cat /var/www/calyx/.env | head -5

# Test manually
sudo -u calyx /var/www/calyx/venv/bin/python /var/www/calyx/calyx.py
```

### Permission denied errors
```bash
# Fix ownership
sudo chown -R calyx:calyx /var/www/calyx
sudo chmod 750 /var/www/calyx
sudo chmod 750 /var/www/calyx/logs
sudo chmod 750 /var/www/calyx/tokens
```

### Port already in use
```bash
# Find process using port 8080
sudo lsof -i :8080

# Kill it if needed
sudo fuser -k 8080/tcp
sudo fuser -k 3001/tcp
```

## Security Features

The service files include:
- **NoNewPrivileges**: Prevents privilege escalation
- **PrivateTmp**: Private /tmp directory
- **ProtectSystem**: Read-only access to system files
- **ProtectHome**: No access to user home directories
- **ReadWritePaths**: Only logs and tokens directories are writable

## Updates

After updating code:
```bash
# Restart services to apply changes
sudo systemctl restart calyx mindbridge

# Or reload if only config changed
sudo systemctl reload calyx
```
