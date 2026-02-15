// src/remote-server.ts

export interface Env {
  // add KV/D1 bindings later if needed
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return new Response("mindbridge healthy", {
        status: 200,
        headers: { "content-type": "text/plain" },
      });
    }

    // Example: simple JSON echo / placeholder for MindBridge routing
    if (request.method === "POST") {
      const body = await request.json().catch(() => null);
      return new Response(
        JSON.stringify({
          ok: true,
          path: url.pathname,
          body,
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        }
      );
    }

    return new Response("mindbridge worker online", {
      status: 200,
      headers: { "content-type": "text/plain" },
    });
  },
};
