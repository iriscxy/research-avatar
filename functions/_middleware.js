const BOT_USER_AGENT = /bot|crawler|spider|slurp|preview|facebookexternalhit|headless/i;

function isDemoPageView(request, response) {
  if (request.method !== "GET" || !response.ok) return false;
  const url = new URL(request.url);
  if (url.pathname !== "/" && url.pathname !== "/index.html") return false;
  return (request.headers.get("accept") || "").includes("text/html");
}

async function anonymousVisitorId(ipAddress, salt) {
  const bytes = new TextEncoder().encode(`${salt}:${ipAddress}`);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}

function coordinate(value) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
}

async function recordPageView(context) {
  const { request, env } = context;
  if (!env.ANALYTICS_DB || !env.VISITOR_HASH_SALT) {
    console.warn("Visitor analytics is not configured: missing ANALYTICS_DB or VISITOR_HASH_SALT.");
    return;
  }

  const ipAddress = request.headers.get("CF-Connecting-IP");
  if (!ipAddress) return;

  const cf = request.cf || {};
  const visitorId = await anonymousVisitorId(ipAddress, env.VISITOR_HASH_SALT);
  const userAgent = request.headers.get("user-agent") || "";
  const isBot = BOT_USER_AGENT.test(userAgent) ? 1 : 0;

  await env.ANALYTICS_DB.prepare(`
    INSERT INTO page_views (
      visitor_id, visited_at, country, region, city,
      latitude, longitude, path, is_bot
    ) VALUES (?1, datetime('now'), ?2, ?3, ?4, ?5, ?6, ?7, ?8)
  `).bind(
    visitorId,
    cf.country || "Unknown",
    cf.region || "Unknown",
    cf.city || "Unknown",
    coordinate(cf.latitude),
    coordinate(cf.longitude),
    new URL(request.url).pathname,
    isBot,
  ).run();
}

export async function onRequest(context) {
  const response = await context.next();
  if (isDemoPageView(context.request, response)) {
    context.waitUntil(recordPageView(context));
  }
  return response;
}
