#!/bin/bash
# Install Calyx and MindBridge as systemd services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CALYX_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Calyx Systemd Service Installer ===${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

# Check if systemd is available
if ! command -v systemctl &> /dev/null; then
    echo -e "${RED}systemctl not found. Is this a systemd-based system?${NC}"
    exit 1
fi

# Create calyx user if it doesn't exist
if ! id -u calyx &>/dev/null; then
    echo -e "${YELLOW}Creating 'calyx' user...${NC}"
    useradd --system --home-dir "$CALYX_DIR" --shell /bin/false calyx
fi

# Set ownership
echo -e "${YELLOW}Setting file permissions...${NC}"
chown -R calyx:calyx "$CALYX_DIR"
chmod 750 "$CALYX_DIR"
chmod 750 "$CALYX_DIR/logs" 2>/dev/null || mkdir -p "$CALYX_DIR/logs" && chown calyx:calyx "$CALYX_DIR/logs"
chmod 750 "$CALYX_DIR/tokens" 2>/dev/null || mkdir -p "$CALYX_DIR/tokens" && chown calyx:calyx "$CALYX_DIR/tokens"

# Check if .env exists
if [ ! -f "$CALYX_DIR/.env" ]; then
    echo -e "${RED}Warning: .env file not found at $CALYX_DIR/.env${NC}"
    echo "Please create it from .env.example before starting the service."
fi

# Install service files
echo -e "${YELLOW}Installing systemd service files...${NC}"
cp "$SCRIPT_DIR/calyx.service" /etc/systemd/system/
cp "$SCRIPT_DIR/mindbridge.service" /etc/systemd/system/

# Reload systemd
echo -e "${YELLOW}Reloading systemd...${NC}"
systemctl daemon-reload

echo ""
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo ""
echo "Services installed:"
echo "  - calyx.service (Discord Bot)"
echo "  - mindbridge.service (LLM Router)"
echo ""
echo "Usage:"
echo "  sudo systemctl start calyx       # Start the bot"
echo "  sudo systemctl stop calyx        # Stop the bot"
echo "  sudo systemctl restart calyx     # Restart the bot"
echo "  sudo systemctl status calyx      # Check bot status"
echo "  sudo journalctl -u calyx -f      # View bot logs"
echo ""
echo "  sudo systemctl start mindbridge  # Start MindBridge"
echo "  sudo systemctl stop mindbridge   # Stop MindBridge"
echo "  sudo systemctl status mindbridge # Check MindBridge status"
echo ""
echo "Enable auto-start on boot:"
echo "  sudo systemctl enable calyx mindbridge"
echo ""
echo -e "${YELLOW}Make sure to:${NC}"
echo "  1. Configure your .env file with all required tokens"
echo "  2. Add API keys for LLM providers (ANTHROPIC_API_KEY, etc.)"
echo "  3. Start the services: sudo systemctl start calyx mindbridge"
