"""
Health check server for monitoring Calyx bot status.
Runs alongside the Discord bot on port 8080.
Also provides Agent Mesh migration ingest endpoint.
"""

import asyncio
import hashlib
import logging
import os
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
        
        # Agent Mesh migration ingest endpoint
        self.app.router.add_post('/migrations/ingest', self.migration_ingest)
        
        # Migration auth token (optional)
        self.migration_auth_token = os.getenv('MIGRATION_AUTH_TOKEN')
    
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
    
    async def migration_ingest(self, request):
        """
        Agent Mesh migration ingest endpoint.
        Receives agent migration packages from MindBridge.
        """
        # Check authorization if token is configured
        if self.migration_auth_token:
            auth_header = request.headers.get('Authorization', '')
            expected = f"Bearer {self.migration_auth_token}"
            if auth_header != expected:
                logger.warning(f"Migration ingest: Invalid auth from {request.remote}")
                return web.json_response(
                    {"error": "Unauthorized", "message": "Invalid or missing authorization"},
                    status=401
                )
        
        try:
            # Parse JSON body
            body = await request.json()
            
            # Validate required fields
            required_fields = ['migrationId', 'agentId', 'sourceVesselId', 'targetVesselId', 
                              'checksum', 'memoryRefs', 'createdAt', 'expiresAt']
            missing = [f for f in required_fields if f not in body]
            if missing:
                return web.json_response(
                    {"error": "Bad Request", "message": f"Missing fields: {missing}"},
                    status=400
                )
            
            migration_id = body['migrationId']
            agent_id = body['agentId']
            source_vessel = body['sourceVesselId']
            target_vessel = body['targetVesselId']
            checksum = body['checksum']
            expires_at = body['expiresAt']
            state = body.get('state', {})
            memory_refs = body.get('memoryRefs', [])
            
            # Check if migration has expired
            try:
                expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if expiry < datetime.now(timezone.utc):
                    logger.warning(f"Migration {migration_id} expired at {expires_at}")
                    return web.json_response(
                        {"error": "Expired", "message": "Migration package has expired"},
                        status=410
                    )
            except ValueError as e:
                return web.json_response(
                    {"error": "Bad Request", "message": f"Invalid expiry format: {e}"},
                    status=400
                )
            
            # Verify checksum if state is provided
            if state:
                state_json = json.dumps(state, sort_keys=True, separators=(',', ':'))
                expected_checksum = hashlib.sha256(state_json.encode()).hexdigest()
                if checksum != expected_checksum:
                    logger.warning(f"Migration {migration_id}: Checksum mismatch")
                    return web.json_response(
                        {"error": "Conflict", "message": "Checksum validation failed"},
                        status=409
                    )
            
            # Log the migration
            logger.info(f"Received migration {migration_id}: {agent_id} from {source_vessel}")
            
            # Send Discord notification to #the-mirror (status channel)
            try:
                from calyx_notion_integration import log_trace
                channel_id = os.getenv('CHANNEL_THE_MIRROR')
                if channel_id and self.bot:
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        import discord
                        embed = discord.Embed(
                            title="🚀 Agent Migration Received",
                            description=f"Agent **{agent_id}** has migrated from `{source_vessel}`",
                            color=discord.Color.blue(),
                            timestamp=datetime.now(timezone.utc)
                        )
                        embed.add_field(name="Migration ID", value=migration_id[:8], inline=True)
                        embed.add_field(name="Target", value=target_vessel, inline=True)
                        embed.add_field(name="Memory Refs", value=str(len(memory_refs)), inline=True)
                        if memory_refs:
                            refs_preview = '\n'.join(memory_refs[:3])
                            if len(memory_refs) > 3:
                                refs_preview += f"\n... and {len(memory_refs) - 3} more"
                            embed.add_field(name="References", value=refs_preview[:1024], inline=False)
                        embed.set_footer(text="Agent Mesh | Migration Ingest")
                        await channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send Discord notification for migration: {e}")
            
            # Store migration info in Notion as a task
            try:
                from calyx_notion_integration import create_task
                await create_task(
                    task_name=f"Agent Migration: {agent_id} from {source_vessel}",
                    status="To-Do",
                    priority="High",
                    assigned_to="Calyx",
                    trigger_source="API",
                    trace_link=None,
                    blocker_reason=None
                )
                logger.info(f"Created task for migration {migration_id}")
            except Exception as e:
                logger.error(f"Failed to create task for migration: {e}")
            
            # Return success response
            return web.json_response({
                "status": "received",
                "migrationId": migration_id,
                "agentId": agent_id,
                "receivedAt": datetime.now(timezone.utc).isoformat(),
                "message": "Migration accepted and queued for processing"
            }, status=202)
            
        except json.JSONDecodeError as e:
            logger.error(f"Migration ingest: Invalid JSON: {e}")
            return web.json_response(
                {"error": "Bad Request", "message": "Invalid JSON body"},
                status=400
            )
        except Exception as e:
            logger.error(f"Migration ingest error: {e}", exc_info=True)
            return web.json_response(
                {"error": "Internal Server Error", "message": str(e)},
                status=500
            )
    
    async def start(self):
        """Start the health check server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        try:
            await site.start()
            logger.info(f"Health check server started on port {self.port}")
        except OSError as e:
            if e.errno == 98:  # Address already in use
                logger.warning(f"Port {self.port} is already in use. Health server will not be available.")
                logger.warning("This is normal if the bot is restarting or another instance is running.")
                await self.runner.cleanup()
                self.runner = None
            else:
                raise
    
    async def stop(self):
        """Stop the health check server."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health check server stopped")
