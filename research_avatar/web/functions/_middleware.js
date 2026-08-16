function isDemoPageView(request, response) {
  if (request.method !== "GET" || !response.ok) return false;
  const url = new URL(request.url);
  if (url.pathname !== "/" && url.pathname !== "/index.html") return false;
  return (request.headers.get("accept") || "").includes("text/html");
}

async function recordPageView(context) {
  const { request, env } = context;
  if (!env.ANALYTICS_DB) {
    console.warn("Visitor logging is not configured: missing ANALYTICS_DB.");
    return;
  }

  const ipAddress = request.headers.get("CF-Connecting-IP");
  if (!ipAddress) return;

  await env.ANALYTICS_DB.prepare(`
    INSERT INTO page_views (ip_address, visited_at, path)
    VALUES (?1, datetime('now'), ?2)
  `).bind(
    ipAddress,
    new URL(request.url).pathname,
  ).run();
}

export async function onRequest(context) {
  const response = await context.next();
  if (isDemoPageView(context.request, response)) {
    context.waitUntil(recordPageView(context));
  }
  return response;
}
