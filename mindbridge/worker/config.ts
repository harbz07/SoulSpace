/**
 * Worker config — builds ServerConfig from Cloudflare Worker env bindings.
 * Use wrangler secret put OPENAI_API_KEY etc. for production.
 */

import type { ServerConfig } from '../src/types.js';

export interface Env {
  OPENAI_API_KEY?: string;
  ANTHROPIC_API_KEY?: string;
  DEEPSEEK_API_KEY?: string;
  GOOGLE_API_KEY?: string;
  OPENROUTER_API_KEY?: string;
  OLLAMA_BASE_URL?: string;
  OPENAI_COMPATIBLE_API_KEY?: string;
  OPENAI_COMPATIBLE_API_BASE_URL?: string;
  OPENAI_COMPATIBLE_API_MODELS?: string;
  DEEPSEEK_BASE_URL?: string;
  GOOGLE_BASE_URL?: string;
  
  // MindBridge Router backend
  MINDBRIDGE_ROUTER_URL?: string;
  MINDBRIDGE_API_KEY?: string;
}

function getBaseUrl(env: Env, key: keyof Env, defaultUrl: string): string {
  const url = env[key];
  return (typeof url === 'string' ? url : undefined) ?? defaultUrl;
}

export function loadConfigFromEnv(env: Env): ServerConfig {
  const config: ServerConfig = {};

  if (env.OPENAI_API_KEY) {
    config.openai = {
      apiKey: env.OPENAI_API_KEY,
      baseUrl: 'https://api.openai.com/v1',
    };
  }

  if (env.ANTHROPIC_API_KEY) {
    config.anthropic = {
      apiKey: env.ANTHROPIC_API_KEY,
      baseUrl: 'https://api.anthropic.com',
    };
  }

  if (env.DEEPSEEK_API_KEY) {
    config.deepseek = {
      apiKey: env.DEEPSEEK_API_KEY,
      baseUrl: getBaseUrl(env, 'DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
    };
  }

  if (env.GOOGLE_API_KEY) {
    config.google = {
      apiKey: env.GOOGLE_API_KEY,
      baseUrl: getBaseUrl(
        env,
        'GOOGLE_BASE_URL',
        'https://generativelanguage.googleapis.com/v1beta',
      ),
    };
  }

  if (env.OPENROUTER_API_KEY) {
    config.openrouter = {
      apiKey: env.OPENROUTER_API_KEY,
    };
  }

  if (env.OPENAI_COMPATIBLE_API_BASE_URL) {
    const modelsStr = env.OPENAI_COMPATIBLE_API_MODELS;
    const availableModels = modelsStr
      ? modelsStr.split(',').map((m) => m.trim())
      : [];

    config.openaiCompatible = {
      apiKey: env.OPENAI_COMPATIBLE_API_KEY,
      baseUrl: env.OPENAI_COMPATIBLE_API_BASE_URL,
      availableModels,
    };
  }

  // Ollama: only include if base URL points to a reachable host (Workers can't reach localhost)
  const ollamaUrl = getBaseUrl(env, 'OLLAMA_BASE_URL', 'http://localhost:11434');
  if (!ollamaUrl.includes('localhost') && !ollamaUrl.includes('127.0.0.1')) {
    config.ollama = { baseUrl: ollamaUrl };
  }

  return config;
}
