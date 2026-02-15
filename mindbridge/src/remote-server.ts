#!/usr/bin/env node

/**
 * Remote MindBridge MCP Server
 * Exposes MindBridge over HTTP for Claude.ai, ChatGPT, Gemini, and Mistral web instances.
 *
 * - MCP over SSE: /sse, /messages (Claude.ai MCP Connector, MCP SuperAssistant)
 * - REST API: /api/tools/* (ChatGPT GPT Actions, Gemini Extensions)
 * - OpenAPI spec: /openapi.json
 */

import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import { loadConfig } from './config.js';
import { ProviderFactory, REASONING_MODELS } from './providers/index.js';
import { GetSecondOpinionSchema } from './types.js';
import MindBridgeServer from './server.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';

const PORT = parseInt(process.env.PORT ?? '3000', 10);

// Initialize config and provider factory
const config = loadConfig();
const providerFactory = new ProviderFactory(config);

const app = express();
app.use(cors({ origin: true })); // Allow all origins for web AI integrations
app.use(express.json());

// Health check
app.get('/health', (_req, res) => {
  res.json({
    status: 'healthy',
    service: 'mindbridge-remote',
    version: '1.2.0',
  });
});

// ============ MCP over SSE (for Claude.ai MCP Connector, MCP SuperAssistant) ============

app.get('/sse', async (req, res) => {
  console.log('New MCP SSE connection');

  const server = new MindBridgeServer();
  const transport = new SSEServerTransport('/messages', res);
  await server.connect(transport);
});

app.post('/messages', (req, res) => {
  // MCP SSE transport handles client messages via POST
  res.status(200).end();
});

// ============ REST API (for ChatGPT GPT Actions, Gemini Extensions, Mistral) ============

app.post('/api/tools/getSecondOpinion', async (req, res) => {
  try {
    const raw = req.body;
    const parseResult = GetSecondOpinionSchema.safeParse(raw);
    if (!parseResult.success) {
      res.status(400).json({
        error: 'Invalid request',
        details: parseResult.error.flatten(),
      });
      return;
    }
    const params = parseResult.data;

    const providerName = params.provider.toLowerCase();
    if (!providerFactory.hasProvider(providerName)) {
      res.status(400).json({
        error: `Provider "${params.provider}" not configured`,
        availableProviders: providerFactory.getAvailableProviders(),
      });
      return;
    }

    const provider = providerFactory.getProvider(providerName)!;
    if (!provider.isValidModel(params.model)) {
      res.status(400).json({
        error: `Model "${params.model}" not found for provider "${params.provider}"`,
        availableModels: provider.getAvailableModels(),
      });
      return;
    }

    const result = await provider.getResponse(params);

    if (result.isError) {
      res.status(500).json({
        error: result.content[0]?.text ?? 'Unknown error',
      });
      return;
    }

    res.json({
      success: true,
      content: result.content[0]?.text ?? '',
    });
  } catch (err) {
    console.error('getSecondOpinion error:', err);
    res.status(500).json({
      error: err instanceof Error ? err.message : 'Internal server error',
    });
  }
});

app.get('/api/tools/listProviders', (_req, res) => {
  try {
    const providers = providerFactory.getAvailableProviders();
    const result: Record<string, { models: string[]; supportsReasoning: boolean }> = {};

    for (const name of providers) {
      result[name] = {
        models: providerFactory.getAvailableModelsForProvider(name),
        supportsReasoning: providerFactory.supportsReasoningEffort(name),
      };
    }

    res.json({ success: true, providers: result });
  } catch (err) {
    console.error('listProviders error:', err);
    res.status(500).json({
      error: err instanceof Error ? err.message : 'Internal server error',
    });
  }
});

app.get('/api/tools/listReasoningModels', (_req, res) => {
  try {
    res.json({
      success: true,
      models: REASONING_MODELS,
      description:
        'Models optimized for reasoning tasks with reasoning_effort parameter support.',
    });
  } catch (err) {
    console.error('listReasoningModels error:', err);
    res.status(500).json({
      error: err instanceof Error ? err.message : 'Internal server error',
    });
  }
});

// ============ OpenAPI spec (for ChatGPT GPT Actions) ============

app.get('/openapi.json', (_req, res) => {
  const baseUrl = process.env.BASE_URL ?? `http://localhost:${PORT}`;
  const spec = {
    openapi: '3.0.0',
    info: {
      title: 'MindBridge API',
      description:
        'Route prompts to any LLM provider. Use getSecondOpinion for responses, listProviders and listReasoningModels for discovery.',
      version: '1.2.0',
    },
    servers: [{ url: baseUrl }],
    paths: {
      '/api/tools/getSecondOpinion': {
        post: {
          summary: 'Get response from an LLM provider',
          operationId: 'getSecondOpinion',
          requestBody: {
            required: true,
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  required: ['provider', 'model', 'prompt'],
                  properties: {
                    provider: {
                      type: 'string',
                      enum: [
                        'openai',
                        'anthropic',
                        'deepseek',
                        'google',
                        'openrouter',
                        'ollama',
                        'openaiCompatible',
                      ],
                    },
                    model: { type: 'string' },
                    prompt: { type: 'string' },
                    systemPrompt: { type: 'string' },
                    temperature: { type: 'number', minimum: 0, maximum: 1 },
                    maxTokens: { type: 'integer', default: 1024 },
                    reasoning_effort: {
                      type: 'string',
                      enum: ['low', 'medium', 'high'],
                    },
                  },
                },
              },
            },
          },
          responses: {
            200: {
              description: 'LLM response',
              content: {
                'application/json': {
                  schema: {
                    type: 'object',
                    properties: {
                      success: { type: 'boolean' },
                      content: { type: 'string' },
                    },
                  },
                },
              },
            },
          },
        },
      },
      '/api/tools/listProviders': {
        get: {
          summary: 'List configured providers and models',
          operationId: 'listProviders',
          responses: {
            200: {
              description: 'Provider list',
              content: {
                'application/json': {
                  schema: {
                    type: 'object',
                    properties: {
                      success: { type: 'boolean' },
                      providers: { type: 'object' },
                    },
                  },
                },
              },
            },
          },
        },
      },
      '/api/tools/listReasoningModels': {
        get: {
          summary: 'List reasoning-optimized models',
          operationId: 'listReasoningModels',
          responses: {
            200: {
              description: 'Reasoning models list',
              content: {
                'application/json': {
                  schema: {
                    type: 'object',
                    properties: {
                      success: { type: 'boolean' },
                      models: { type: 'array', items: { type: 'string' } },
                    },
                  },
                },
              },
            },
          },
        },
      },
    },
  };
  res.json(spec);
});

// ============ Start server ============

app.listen(PORT, () => {
  console.log(`
✨ MindBridge Remote Server ✨

MCP (SSE):
  GET  ${process.env.BASE_URL ?? `http://localhost:${PORT}`}/sse
  POST ${process.env.BASE_URL ?? `http://localhost:${PORT}`}/messages

REST API:
  POST ${process.env.BASE_URL ?? `http://localhost:${PORT}`}/api/tools/getSecondOpinion
  GET  ${process.env.BASE_URL ?? `http://localhost:${PORT}`}/api/tools/listProviders
  GET  ${process.env.BASE_URL ?? `http://localhost:${PORT}`}/api/tools/listReasoningModels

OpenAPI: ${process.env.BASE_URL ?? `http://localhost:${PORT}`}/openapi.json
Health:  ${process.env.BASE_URL ?? `http://localhost:${PORT}`}/health

Configured providers: ${providerFactory.getAvailableProviders().join(', ') || '(none - add API keys to .env)'}
`);
});
