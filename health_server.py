"""
Health check server for monitoring Calyx bot status.
Runs alongside the Discord bot on port 8080.
"""

import asyncio
import logging
from aiohttp import web
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)


class HealthServer:
    def __init__(self, bot, notion_client, port=8080):
        self.bot = bot
        self.notion = notion_client
        self.port = port
        self.app = web.Application()
        self.runner = None
        self.start_time = datetime.now(timezone.utc)
        
        # Setup routes
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/health/live', self.liveness)
        self.app.router.add_get('/health/ready', self.readiness)
        self.app.router.add_get('/metrics', self.metrics)
    
    async def health_check(self, request):
        """Basic health check endpoint."""
        return web.json_response({
            "status": "healthy",
            "service": "Calyx",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds()
        })
    
    async def liveness(self, request):
        """Kubernetes-style liveness probe."""
        try:
            # Check if bot is responsive
            if self.bot.is_closed():
                return web.json_response(
                    {"status": "unhealthy", "reason": "Bot connection closed"},
                    status=503
                )
            
            return web.json_response({"status": "alive"})
        except Exception as e:
            logger.error(f"Liveness check failed: {e}")
            return web.json_response(
                {"status": "unhealthy", "error": str(e)},
                status=503
            )
    
    async def readiness(self, request):
        """Kubernetes-style readiness probe."""
        checks = {
            "discord": False,
            "notion": False
        }
        
        try:
            # Check Discord connection
            checks["discord"] = self.bot.is_ready() and not self.bot.is_closed()
            
            # Check Notion connection
            if self.notion:
                try:
                    self.notion.users.me()
                    checks["notion"] = True
                except Exception:
                    checks["notion"] = False
            
            all_ready = all(checks.values())
            
            return web.json_response({
                "status": "ready" if all_ready else "not_ready",
                "checks": checks
            }, status=200 if all_ready else 503)
            
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=503
            )
    
    async def metrics(self, request):
        """Basic metrics endpoint."""
        try:
            uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            
            metrics = {
                "uptime_seconds": uptime,
                "discord_latency_ms": round(self.bot.latency * 1000, 2) if self.bot.is_ready() else None,
                "guild_count": len(self.bot.guilds) if self.bot.is_ready() else 0,
                "user_count": sum(g.member_count for g in self.bot.guilds) if self.bot.is_ready() else 0,
                "notion_connected": self.notion is not None
            }
            
            return web.json_response(metrics)
        except Exception as e:
            logger.error(f"Metrics endpoint failed: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def start(self):
        """Start the health check server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"Health check server started on port {self.port}")
    
    async def stop(self):
        """Stop the health check server."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health check server stopped")
