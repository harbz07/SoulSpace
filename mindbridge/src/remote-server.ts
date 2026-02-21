// mindbridge/src/remote-server.ts

export interface Env {
  // e.g. MINDBRIDGE_URL?: string; // later when you hook real router
}

type OpenAIChatMessage = {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
};

type OpenAIChatRequest = {
  model: string;
  messages: OpenAIChatMessage[];
  max_tokens?: number;
  temperature?: number;
};

export default {
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    // Health check
    if (url.pathname === "/health") {
      return new Response("ok", {
        status: 200,
        headers: { "content-type": "text/plain" },
      });
    }

    // OpenAI-style chat completions
    if (url.pathname === "/v1/chat/completions" && request.method === "POST") {
      let body: OpenAIChatRequest;
      try {
        body = await request.json() as OpenAIChatRequest;
      } catch {
        return jsonError("Invalid JSON body", 400);
      }

      if (!body || !Array.isArray(body.messages)) {
        return jsonError("`messages` must be an array", 400);
      }

      const last = body.messages[body.messages.length - 1];

      // TODO: replace this with real MindBridge call
      const completion = {
        id: "chatcmpl-mindbridge-placeholder",
        object: "chat.completion",
        created: Math.floor(Date.now() / 1000),
        model: body.model ?? "mindbridge-router",
        choices: [
          {
            index: 0,
            message: {
              role: "assistant",
              content: `MindBridge placeholder at api.soul-os.cc: "${last?.content ?? ""}"`,
            },
            finish_reason: "stop",
          },
        ],
      };

      return new Response(JSON.stringify(completion), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }

    return new Response("Not found", { status: 404 });
  },
};

function jsonError(message: string, status = 400): Response {
  return new Response(JSON.stringify({ error: { message } }), {
    status,
    headers: { "content-type": "application/json" },
  });
}
