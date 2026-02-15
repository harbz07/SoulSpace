/**
 * MindBridge Cloudflare Worker
 * REST API for Claude.ai, ChatGPT, Gemini, Mistral integrations.
 */

import { ProviderFactory, REASONING_MODELS } from '../src/providers/index.js';
import { GetSecondOpinionSchema } from '../src/types.js';
import type { Env } from './config.js';
import { loadConfigFromEnv } from './config.js';

const CORS_HEADERS: Record<string, string> = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

function jsonResponse(data: unknown, status = 200, init?: ResponseInit): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      ...CORS_HEADERS,
      ...init?.headers,
    },
    ...init,
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    const path = url.pathname;

    try {
      // Health check
      if (path === '/health') {
        return jsonResponse({
          status: 'healthy',
          service: 'mindbridge-worker',
          version: '1.2.0',
        });
      }

      // OpenAPI spec
      if (path === '/openapi.json') {
        const baseUrl = url.origin;
        return jsonResponse(openApiSpec(baseUrl));
      }

      const config = loadConfigFromEnv(env);
      const providerFactory = new ProviderFactory(config);

      // REST API: getSecondOpinion
      if (path === '/api/tools/getSecondOpinion' && request.method === 'POST') {
        const raw = (await request.json()) as unknown;
        const parseResult = GetSecondOpinionSchema.safeParse(raw);

        if (!parseResult.success) {
          return jsonResponse(
            { error: 'Invalid request', details: parseResult.error.flatten() },
            400,
          );
        }
        const params = parseResult.data;
        const providerName = params.provider.toLowerCase();

        if (!providerFactory.hasProvider(providerName)) {
          return jsonResponse(
            {
              error: `Provider "${params.provider}" not configured`,
              availableProviders: providerFactory.getAvailableProviders(),
            },
            400,
          );
        }

        const provider = providerFactory.getProvider(providerName)!;
        if (!provider.isValidModel(params.model)) {
          return jsonResponse(
            {
              error: `Model "${params.model}" not found for provider "${params.provider}"`,
              availableModels: provider.getAvailableModels(),
            },
            400,
          );
        }

        const result = await provider.getResponse(params);

        if (result.isError) {
          return jsonResponse(
            { error: result.content[0]?.text ?? 'Unknown error' },
            500,
          );
        }

        return jsonResponse({
          success: true,
          content: result.content[0]?.text ?? '',
        });
      }

      // REST API: listProviders
      if (path === '/api/tools/listProviders' && request.method === 'GET') {
        const providers = providerFactory.getAvailableProviders();
        const result: Record<string, { models: string[]; supportsReasoning: boolean }> = {};

        for (const name of providers) {
          result[name] = {
            models: providerFactory.getAvailableModelsForProvider(name),
            supportsReasoning: providerFactory.supportsReasoningEffort(name),
          };
        }

        return jsonResponse({ success: true, providers: result });
      }

      // REST API: listReasoningModels
      if (path === '/api/tools/listReasoningModels' && request.method === 'GET') {
        return jsonResponse({
          success: true,
          models: REASONING_MODELS,
          description:
            'Models optimized for reasoning tasks with reasoning_effort parameter support.',
        });
      }

      return jsonResponse({ error: 'Not found' }, 404);
    } catch (err) {
      console.error('MindBridge Worker error:', err);
      return jsonResponse(
        { error: err instanceof Error ? err.message : 'Internal server error' },
        500,
      );
    }
  },
};

function openApiSpec(baseUrl: string) {
  return {
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
}
