import type { DiscordWebhookResult } from './types.js';

export interface DiscordWebhookRequest {
  webhookUrl: string;
  content: string;
  username?: string;
  avatarUrl?: string;
  threadName?: string;
}

interface DiscordWebhookResponseBody {
  id?: string;
  channel_id?: string;
  thread?: {
    id?: string;
  };
}

function responseSnippet(input: string, maxLength = 300): string {
  if (input.length <= maxLength) {
    return input;
  }
  return `${input.slice(0, maxLength)}...`;
}

function parseJsonResponse(raw: string): DiscordWebhookResponseBody | undefined {
  if (!raw) {
    return undefined;
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed === 'object' && parsed !== null) {
      return parsed as DiscordWebhookResponseBody;
    }
  } catch {
    return undefined;
  }

  return undefined;
}

function withWaitParam(webhookUrl: string): string {
  const url = new URL(webhookUrl);
  if (!url.searchParams.has('wait')) {
    url.searchParams.set('wait', 'true');
  }
  return url.toString();
}

export async function sendDiscordWebhook(
  input: DiscordWebhookRequest,
): Promise<DiscordWebhookResult> {
  const body: Record<string, unknown> = {
    content: input.content,
  };

  if (input.username) {
    body.username = input.username;
  }

  if (input.avatarUrl) {
    body.avatar_url = input.avatarUrl;
  }

  if (input.threadName) {
    body.thread_name = input.threadName;
  }

  try {
    const response = await fetch(withWaitParam(input.webhookUrl), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    const rawResponse = await response.text();
    const parsedResponse = parseJsonResponse(rawResponse);
    const threadId = parsedResponse?.thread?.id;
    const messageId = parsedResponse?.id;
    const channelId = parsedResponse?.channel_id;

    const details = [
      messageId ? `messageId=${messageId}` : '',
      channelId ? `channelId=${channelId}` : '',
      threadId ? `threadId=${threadId}` : '',
    ]
      .filter(Boolean)
      .join(', ');

    const detailSuffix = details ? ` (${details})` : '';

    return {
      webhookUrl: input.webhookUrl,
      ok: response.ok,
      status: response.status,
      responseSnippet: responseSnippet(
        rawResponse || `${response.status} ${response.statusText}${detailSuffix}`,
      ),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown webhook error';
    return {
      webhookUrl: input.webhookUrl,
      ok: false,
      status: 0,
      responseSnippet: responseSnippet(message),
    };
  }
}
