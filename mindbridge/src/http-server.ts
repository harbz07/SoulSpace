#!/usr/bin/env node
/**
 * HTTP Server mode for MindBridge Agent Mesh
 * Exposes Agent Mesh tools via REST API for external integration
 */

import dotenv from 'dotenv';
import { createServer, type Server, type IncomingMessage, type ServerResponse } from 'http';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { AgentMeshOrchestrator } from './agentMesh/index.js';
import { ProviderFactory } from './providers/index.js';
import { loadConfig } from './config.js';
import type { AgentMeshConfig } from './types.js';

// Load .env from parent directory (calyx root) or current directory
const __dirname = dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: join(__dirname, '..', '..', '.env') });  // Try parent (calyx root)
dotenv.config({ path: join(__dirname, '..', '.env') });        // Fallback to mindbridge dir
dotenv.config();  // Default

interface HttpRequest {
  method: string;
  url: string;
  headers: Record<string, string | string[]>;
  body: unknown;
}

interface HttpResponse {
  status: number;
  body: unknown;
}

type RouteHandler = (req: HttpRequest) => Promise<HttpResponse>;

class MindBridgeHttpServer {
  private server: Server | null = null;
  private orchestrator: AgentMeshOrchestrator;
  private providerFactory: ProviderFactory;
  private port: number;
  private authToken?: string;
  private routes: Map<string, RouteHandler> = new Map();

  constructor(port = 3001, config?: AgentMeshConfig) {
    this.port = port;
    this.orchestrator = new AgentMeshOrchestrator(config);
    this.providerFactory = new ProviderFactory(loadConfig());
    this.authToken = process.env.MINDBRIDGE_HTTP_AUTH_TOKEN;
    this.setupRoutes();
  }

  private setupRoutes(): void {
    // Health check
    this.routes.set('GET /health', async () => ({
      status: 200,
      body: { status: 'ok', service: 'MindBridge HTTP', version: '1.2.0' }
    }));

    // Vessel management
    this.routes.set('POST /vessels', this.handleRegisterVessel.bind(this));
    this.routes.set('GET /vessels', this.handleListVessels.bind(this));

    // Migration management
    this.routes.set('POST /migrations', this.handlePrepareMigration.bind(this));
    this.routes.set('POST /migrations/dispatch', this.handleDispatchMigration.bind(this));
    this.routes.set('GET /migrations', this.handleListMigrations.bind(this));

    // Announcements
    this.routes.set('POST /announce', this.handleAnnounce.bind(this));
    
    // LLM Chat
    this.routes.set('POST /chat', this.handleChat.bind(this));
    this.routes.set('GET /providers', this.handleListProviders.bind(this));
  }

  private async handleRegisterVessel(req: HttpRequest): Promise<HttpResponse> {
    try {
      const body = req.body as Record<string, unknown>;
      const vessel = await this.orchestrator.registerVessel({
        vesselId: String(body.vesselId),
        baseUrl: String(body.baseUrl),
        migrationEndpointPath: body.migrationEndpointPath ? String(body.migrationEndpointPath) : '/migrations/ingest',
        capabilities: Array.isArray(body.capabilities) ? body.capabilities.map(String) : [],
        protocols: Array.isArray(body.protocols) ? body.protocols.map(String) : ['mcp-json'],
        discordWebhookUrl: body.discordWebhookUrl ? String(body.discordWebhookUrl) : undefined,
        forumWebhookUrl: body.forumWebhookUrl ? String(body.forumWebhookUrl) : undefined,
        metadata: typeof body.metadata === 'object' && body.metadata !== null
          ? Object.fromEntries(Object.entries(body.metadata).map(([k, v]) => [k, String(v)]))
          : {}
      });
      return { status: 201, body: { success: true, vessel } };
    } catch (error) {
      return {
        status: 400,
        body: { success: false, error: error instanceof Error ? error.message : 'Unknown error' }
      };
    }
  }

  private async handleListVessels(): Promise<HttpResponse> {
    try {
      const vessels = this.orchestrator.listVessels();
      return { status: 200, body: { success: true, vessels, count: vessels.length } };
    } catch (error) {
      return {
        status: 500,
        body: { success: false, error: error instanceof Error ? error.message : 'Unknown error' }
      };
    }
  }

  private async handlePrepareMigration(req: HttpRequest): Promise<HttpResponse> {
    try {
      const body = req.body as Record<string, unknown>;
      const migration = await this.orchestrator.createMigrationPackage({
        agentId: String(body.agentId),
        sourceVesselId: String(body.sourceVesselId),
        targetVesselId: String(body.targetVesselId),
        state: typeof body.state === 'object' && body.state !== null ? body.state as Record<string, unknown> : {},
        memoryRefs: Array.isArray(body.memoryRefs) ? body.memoryRefs.map(String) : [],
        ttlSeconds: typeof body.ttlSeconds === 'number' ? body.ttlSeconds : 900
      });
      return { status: 201, body: { success: true, migration } };
    } catch (error) {
      return {
        status: 400,
        body: { success: false, error: error instanceof Error ? error.message : 'Unknown error' }
      };
    }
  }

  private async handleDispatchMigration(req: HttpRequest): Promise<HttpResponse> {
    try {
      const body = req.body as Record<string, unknown>;
      const result = await this.orchestrator.dispatchMigration({
        migrationId: String(body.migrationId),
        includeState: body.includeState !== false,
        dryRun: body.dryRun === true,
        discordWebhookUrl: body.discordWebhookUrl ? String(body.discordWebhookUrl) : undefined,
        forumWebhookUrl: body.forumWebhookUrl ? String(body.forumWebhookUrl) : undefined,
        threadName: body.threadName ? String(body.threadName) : undefined
      });
      return { status: 200, body: { success: true, result } };
    } catch (error) {
      return {
        status: 400,
        body: { success: false, error: error instanceof Error ? error.message : 'Unknown error' }
      };
    }
  }

  private async handleListMigrations(req: HttpRequest): Promise<HttpResponse> {
    try {
      const url = new URL(req.url as string, 'http://localhost');
      const status = url.searchParams.get('status') as 'prepared' | 'dispatched' | 'completed' | 'failed' | undefined;
      const limit = parseInt(url.searchParams.get('limit') || '25', 10);
      
      const migrations = this.orchestrator.listMigrations({ status, limit });
      return { status: 200, body: { success: true, migrations, count: migrations.length } };
    } catch (error) {
      return {
        status: 500,
        body: { success: false, error: error instanceof Error ? error.message : 'Unknown error' }
      };
    }
  }

  private async handleAnnounce(req: HttpRequest): Promise<HttpResponse> {
    try {
      const body = req.body as Record<string, unknown>;
      const results = await this.orchestrator.announceEvent({
        content: String(body.content),
        webhookUrl: body.webhookUrl ? String(body.webhookUrl) : undefined,
        forumWebhookUrl: body.forumWebhookUrl ? String(body.forumWebhookUrl) : undefined,
        threadName: body.threadName ? String(body.threadName) : undefined,
        username: body.username ? String(body.username) : undefined,
        avatarUrl: body.avatarUrl ? String(body.avatarUrl) : undefined,
        agentId: body.agentId ? String(body.agentId) : undefined,
        migrationId: body.migrationId ? String(body.migrationId) : undefined
      });
      return { status: 200, body: { success: true, results } };
    } catch (error) {
      return {
        status: 400,
        body: { success: false, error: error instanceof Error ? error.message : 'Unknown error' }
      };
    }
  }

  private async parseBody(req: IncomingMessage): Promise<unknown> {
    return new Promise((resolve) => {
      let data = '';
      req.on('data', chunk => data += chunk);
      req.on('end', () => {
        try {
          resolve(data ? JSON.parse(data) : {});
        } catch {
          resolve({});
        }
      });
    });
  }

  private checkAuth(req: IncomingMessage): boolean {
    if (!this.authToken) return true;
    const authHeader = req.headers['authorization'] || '';
    return authHeader === `Bearer ${this.authToken}`;
  }

  private async handleRequest(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const method = req.method || 'GET';
    const url = new URL(req.url || '/', 'http://localhost');
    const routeKey = `${method} ${url.pathname}`;

    // CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    if (method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return;
    }

    // Check auth
    if (!this.checkAuth(req)) {
      res.writeHead(401, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Unauthorized' }));
      return;
    }

    const handler = this.routes.get(routeKey);
    if (!handler) {
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Not found' }));
      return;
    }

    const body = await this.parseBody(req);
    const response = await handler({
      method,
      url: req.url || '/',
      headers: req.headers as Record<string, string | string[]>,
      body
    });

    res.writeHead(response.status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(response.body));
  }

  private async handleChat(req: HttpRequest): Promise<HttpResponse> {
    try {
      const body = req.body as Record<string, unknown>;
      
      // Validate required fields - accept either prompt or messages
      let promptText = '';
      let systemPrompt = '';
      
      if (body.messages && Array.isArray(body.messages)) {
        // Convert messages array to prompt
        const messages = body.messages as Array<{role: string; content: string}>;
        const userMessages = messages.filter(m => m.role === 'user');
        const systemMessages = messages.filter(m => m.role === 'system');
        
        promptText = userMessages.map(m => m.content).join('\n\n');
        systemPrompt = systemMessages.map(m => m.content).join('\n');
      } else if (body.prompt && typeof body.prompt === 'string') {
        promptText = body.prompt;
        systemPrompt = String(body.systemPrompt || '');
      } else {
        return {
          status: 400,
          body: { success: false, error: 'Either prompt (string) or messages (array) is required' }
        };
      }
      
      const providerName = String(body.provider || 'anthropic').toLowerCase();
      const model = String(body.model || '');
      const temperature = typeof body.temperature === 'number' ? body.temperature : 0.7;
      const maxTokens = typeof body.max_tokens === 'number' ? body.max_tokens : 2000;
      
      // Check if provider exists
      if (!this.providerFactory.hasProvider(providerName)) {
        const available = this.providerFactory.getAvailableProviders();
        return {
          status: 400,
          body: { 
            success: false, 
            error: `Provider "${providerName}" not available. Available: ${available.join(', ')}` 
          }
        };
      }
      
      const provider = this.providerFactory.getProvider(providerName)!;
      
      // Validate model
      if (model && !provider.isValidModel(model)) {
        const availableModels = provider.getAvailableModels();
        return {
          status: 400,
          body: {
            success: false,
            error: `Model "${model}" not found. Available: ${availableModels.join(', ')}`
          }
        };
      }
      
      // Get response from provider
      const result = await provider.getResponse({
        prompt: promptText,
        provider: providerName as 'openai' | 'anthropic' | 'deepseek' | 'google' | 'openrouter' | 'ollama' | 'openaiCompatible',
        model: model || provider.getAvailableModels()[0],
        systemPrompt: systemPrompt || undefined,
        temperature,
        maxTokens,
        reasoning_effort: body.reasoning_effort as 'low' | 'medium' | 'high' | undefined
      });
      
      if (result.isError) {
        return {
          status: 500,
          body: { success: false, error: result.content[0].text }
        };
      }
      
      return {
        status: 200,
        body: { 
          success: true, 
          content: result.content[0].text,
          provider: providerName,
          model: model || provider.getAvailableModels()[0]
        }
      };
    } catch (error) {
      return {
        status: 500,
        body: { 
          success: false, 
          error: error instanceof Error ? error.message : 'Unknown error' 
        }
      };
    }
  }

  private async handleListProviders(): Promise<HttpResponse> {
    try {
      const providers = this.providerFactory.getAvailableProviders();
      const result: Record<string, { models: string[]; supportsReasoning: boolean }> = {};
      
      for (const name of providers) {
        const provider = this.providerFactory.getProvider(name);
        if (provider) {
          result[name] = {
            models: provider.getAvailableModels(),
            supportsReasoning: provider.supportsReasoningEffort()
          };
        }
      }
      
      return {
        status: 200,
        body: { success: true, providers: result }
      };
    } catch (error) {
      return {
        status: 500,
        body: { 
          success: false, 
          error: error instanceof Error ? error.message : 'Unknown error' 
        }
      };
    }
  }

  public async start(): Promise<void> {
    await this.orchestrator.initialize();
    
    this.server = createServer((req, res) => {
      this.handleRequest(req, res).catch(err => {
        console.error('Request handler error:', err);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Internal server error' }));
      });
    });

    return new Promise((resolve, reject) => {
      this.server!.listen(this.port, () => {
        console.log(`✨ MindBridge HTTP Server`);
        console.log(`Version: 1.2.0`);
        console.log(`Port: ${this.port}`);
        console.log(`Auth: ${this.authToken ? 'enabled' : 'disabled'}`);
        console.log('\nEndpoints:');
        console.log('  GET  /health           - Health check');
        console.log('  GET  /vessels          - List vessels');
        console.log('  POST /vessels          - Register vessel');
        console.log('  GET  /migrations       - List migrations');
        console.log('  POST /migrations       - Prepare migration');
        console.log('  POST /migrations/dispatch - Dispatch migration');
        console.log('  POST /announce         - Send Discord announcement');
        console.log('  POST /chat             - LLM chat completion');
        console.log('  GET  /providers        - List available LLM providers\n');
        resolve();
      });

      this.server!.on('error', reject);
    });
  }

  public async stop(): Promise<void> {
    return new Promise((resolve) => {
      if (this.server) {
        this.server.close(() => resolve());
      } else {
        resolve();
      }
    });
  }
}

// Start server if run directly
if (import.meta.url === `file://${process.argv[1]}`) {
  const config = loadConfig();
  const port = parseInt(process.env.MINDBRIDGE_HTTP_PORT || '3001', 10);
  const server = new MindBridgeHttpServer(port, config.agentMesh);
  
  server.start().catch(err => {
    console.error('Failed to start server:', err);
    process.exit(1);
  });

  // Graceful shutdown
  process.on('SIGINT', () => {
    console.log('\nShutting down...');
    server.stop().then(() => process.exit(0));
  });

  process.on('SIGTERM', () => {
    console.log('\nShutting down...');
    server.stop().then(() => process.exit(0));
  });
}

export { MindBridgeHttpServer };
