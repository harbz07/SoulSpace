#!/bin/bash
# Quick status check for Calyx services

echo "=== Calyx Service Status ==="
echo ""

# Check if services are installed
if systemctl list-unit-files | grep -q "calyx.service"; then
    echo "✓ calyx.service installed"
    systemctl is-active --quiet calyx && echo "  Status: RUNNING" || echo "  Status: STOPPED"
    systemctl is-enabled --quiet calyx 2>/dev/null && echo "  Auto-start: ENABLED" || echo "  Auto-start: disabled"
else
    echo "✗ calyx.service not installed"
fi

echo ""

if systemctl list-unit-files | grep -q "mindbridge.service"; then
    echo "✓ mindbridge.service installed"
    systemctl is-active --quiet mindbridge && echo "  Status: RUNNING" || echo "  Status: STOPPED"
    systemctl is-enabled --quiet mindbridge 2>/dev/null && echo "  Auto-start: ENABLED" || echo "  Auto-start: disabled"
else
    echo "✗ mindbridge.service not installed"
fi

echo ""
echo "=== Health Checks ==="
echo ""

# Check Calyx health
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "✓ Calyx HTTP (port 8080) - RESPONDING"
    curl -s http://localhost:8080/health | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'  Uptime: {d.get(\"uptime_seconds\", 0):.0f}s')" 2>/dev/null
else
    echo "✗ Calyx HTTP (port 8080) - NOT RESPONDING"
fi

# Check MindBridge health
if curl -s http://localhost:3001/health > /dev/null 2>&1; then
    echo "✓ MindBridge HTTP (port 3001) - RESPONDING"
else
    echo "✗ MindBridge HTTP (port 3001) - NOT RESPONDING"
fi

echo ""
echo "=== Recent Logs ==="
echo ""
echo "Calyx (last 3 lines):"
journalctl -u calyx --no-pager -n 3 2>/dev/null || echo "  No logs available (service may not have run yet)"

echo ""
echo "MindBridge (last 3 lines):"
journalctl -u mindbridge --no-pager -n 3 2>/dev/null || echo "  No logs available (service may not have run yet)"

echo ""
echo "=== Quick Actions ==="
echo ""
echo "Start:   sudo systemctl start calyx mindbridge"
echo "Stop:    sudo systemctl stop calyx mindbridge"
echo "Restart: sudo systemctl restart calyx mindbridge"
echo "Logs:    sudo journalctl -u calyx -f"
echo "         sudo journalctl -u mindbridge -f"
