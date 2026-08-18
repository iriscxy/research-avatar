import { Container, getContainer } from "@cloudflare/containers";

const AUTH_COOKIE = "online_studio_auth";
const GOOGLE_STATE_COOKIE = "online_studio_google_state";
const AUTH_SECONDS = 30 * 24 * 60 * 60;
// Cloudflare Workers Web Crypto currently caps PBKDF2 at 100,000 iterations.
const PASSWORD_ITERATIONS = 100_000;

interface Env {
  ONLINE_STUDIO: DurableObjectNamespace;
  AUTH_DB: D1Database;
  CF_VERSION_METADATA: {
    id: string;
    tag: string;
    timestamp: string;
  };
  GOOGLE_OAUTH_CLIENT_ID?: string;
  GOOGLE_OAUTH_CLIENT_SECRET?: string;
}

interface User {
  id: string;
  email: string;
  provider: "local" | "google";
}

export class OnlineStudioContainer extends Container {
  defaultPort = 8876;
  sleepAfter = "2h";
  envVars = {
    ONLINE_STUDIO_DATA_ROOT: "/srv/online-paper-studio",
    ONLINE_STUDIO_SECURE_COOKIE: "1",
    ONLINE_STUDIO_PUBLIC_REGISTRATION: "1",
    ONLINE_STUDIO_TRUST_PROXY_AUTH: "1",
    ONLINE_STUDIO_IDLE_SECONDS: "5400",
    ONLINE_STUDIO_MAX_SESSIONS: "2",
  };
}

// V2 through V29 (one per past rollout) were retired via a "v31"
// deleted_classes migration in wrangler.jsonc/wrangler.example.jsonc --
// each was an empty pass-through subclass with no traffic once superseded,
// so their Durable Object storage was safe to reclaim. The base
// OnlineStudioContainer class stays: V30 still extends it, and
// deleted_classes only tears down the Durable Object namespace/data, not
// the source class other exports depend on.

// Table-generate-race release: a real user reported clicking into a second
// table right after the first left it stuck "pending" forever.
// scheduleAutomaticTableGenerate marked a table "attempted" before learning
// whether the shared figureRequestBusy lock (still held by another
// in-flight table/figure request) silently dropped its own call -- so it
// could never retry. Now un-marks it and lets a later render retry once
// the lock clears. Rotate proactively per the established pattern.
export class OnlineStudioContainerV30 extends OnlineStudioContainer {}

// Shared-DeepSeek-key release: updating a class's image tag alone does not
// restart already-running instances of that class -- they keep serving the
// previous image until sleepAfter (2h) or a natural cycle. Rotating to a
// fresh class forces Cloudflare to start new instances immediately, so the
// shared-key/spend-cap/demo-view-only changes actually go live right away.
export class OnlineStudioContainerV31 extends OnlineStudioContainer {}

function json(payload: unknown, status = 200, cookie?: string): Response {
  const headers = new Headers({
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });
  if (cookie) headers.append("set-cookie", cookie);
  return new Response(JSON.stringify(payload), { status, headers });
}

function cookieValue(request: Request, name: string): string | null {
  const raw = request.headers.get("cookie") || "";
  for (const item of raw.split(";")) {
    const separator = item.indexOf("=");
    if (separator < 0) continue;
    if (item.slice(0, separator).trim() === name) {
      return item.slice(separator + 1).trim();
    }
  }
  return null;
}

function authCookie(token: string, clear = false): string {
  return [
    `${AUTH_COOKIE}=${clear ? "" : token}`,
    "Path=/",
    "HttpOnly",
    "Secure",
    "SameSite=Strict",
    clear ? "Max-Age=0" : `Max-Age=${AUTH_SECONDS}`,
  ].join("; ");
}

function googleStateCookie(state: string, clear = false): string {
  return [
    `${GOOGLE_STATE_COOKIE}=${clear ? "" : state}`,
    "Path=/auth/google/callback",
    "HttpOnly",
    "Secure",
    "SameSite=Lax",
    clear ? "Max-Age=0" : "Max-Age=600",
  ].join("; ");
}

function randomToken(size = 32): string {
  return bytesToBase64(crypto.getRandomValues(new Uint8Array(size)))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

function normalizeEmail(value: unknown): string {
  const email = String(value || "").trim().toLowerCase();
  if (
    email.length > 254 ||
    !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) ||
    [...email].some((character) => character.charCodeAt(0) < 32)
  ) {
    throw new Error("请输入有效的邮箱地址。");
  }
  return email;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function base64ToBytes(value: string): Uint8Array {
  return Uint8Array.from(atob(value), (character) => character.charCodeAt(0));
}

async function passwordDigest(password: string, salt: Uint8Array): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations: PASSWORD_ITERATIONS },
    key,
    256,
  );
  return new Uint8Array(bits);
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function safeEqual(left: Uint8Array, right: Uint8Array): boolean {
  let difference = left.length ^ right.length;
  const length = Math.max(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    difference |= (left[index] || 0) ^ (right[index] || 0);
  }
  return difference === 0;
}

async function readBody(request: Request): Promise<Record<string, unknown>> {
  const length = Number(request.headers.get("content-length") || "0");
  if (length > 16_384) throw new Error("登录请求过大。");
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    // request.json() throws the raw V8 parser SyntaxError message (e.g.
    // "Unexpected token 'o', \"not json\" is not valid JSON") on malformed
    // input; every caller's catch block surfaces error.message verbatim to
    // the client, so without this it was the one place in signup/login that
    // leaked an internal parser string instead of the file's normal clean
    // Chinese error text.
    throw new Error("请求必须是有效 JSON。");
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw new Error("请求必须是 JSON 对象。");
  }
  return body as Record<string, unknown>;
}

async function rateLimit(request: Request, env: Env): Promise<boolean> {
  const ip = request.headers.get("cf-connecting-ip") || "unknown";
  const bucket = Math.floor(Date.now() / 60_000);
  await env.AUTH_DB.prepare(
    `INSERT INTO auth_attempts (ip, bucket, attempts) VALUES (?, ?, 1)
     ON CONFLICT(ip, bucket) DO UPDATE SET attempts = attempts + 1`,
  ).bind(ip, bucket).run();
  const row = await env.AUTH_DB.prepare(
    "SELECT attempts FROM auth_attempts WHERE ip = ? AND bucket = ?",
  ).bind(ip, bucket).first<{ attempts: number }>();
  if (Math.random() < 0.02) {
    await env.AUTH_DB.prepare("DELETE FROM auth_attempts WHERE bucket < ?")
      .bind(bucket - 5).run();
  }
  return Number(row?.attempts || 0) <= 10;
}

async function currentUser(request: Request, env: Env): Promise<User | null> {
  const token = cookieValue(request, AUTH_COOKIE);
  if (!token) return null;
  return env.AUTH_DB.prepare(
    `SELECT users.id, users.email, users.provider
     FROM auth_sessions
     JOIN users ON users.id = auth_sessions.user_id
     WHERE auth_sessions.token_hash = ? AND auth_sessions.expires_at > ?`,
  ).bind(await sha256(token), Math.floor(Date.now() / 1000)).first<User>();
}

async function createSession(env: Env, userId: string): Promise<string> {
  const token = randomToken(48);
  const now = Math.floor(Date.now() / 1000);
  await env.AUTH_DB.batch([
    env.AUTH_DB.prepare(
      "INSERT INTO auth_sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
    ).bind(await sha256(token), userId, now + AUTH_SECONDS, now),
    env.AUTH_DB.prepare("DELETE FROM auth_sessions WHERE expires_at <= ?").bind(now),
  ]);
  return token;
}

function googleConfigured(env: Env): boolean {
  return Boolean(env.GOOGLE_OAUTH_CLIENT_ID && env.GOOGLE_OAUTH_CLIENT_SECRET);
}

async function googleStart(request: Request, env: Env): Promise<Response> {
  if (!googleConfigured(env)) {
    return Response.redirect(new URL("/?auth_error=google", request.url), 302);
  }
  const state = randomToken();
  const nonce = randomToken();
  const now = Math.floor(Date.now() / 1000);
  await env.AUTH_DB.batch([
    env.AUTH_DB.prepare(
      "INSERT INTO google_oauth_states (state, nonce, expires_at) VALUES (?, ?, ?)",
    ).bind(state, nonce, now + 600),
    env.AUTH_DB.prepare("DELETE FROM google_oauth_states WHERE expires_at <= ?").bind(now),
  ]);
  const redirectUri = new URL("/auth/google/callback", request.url).toString();
  const authorization = new URL("https://accounts.google.com/o/oauth2/v2/auth");
  authorization.search = new URLSearchParams({
    client_id: env.GOOGLE_OAUTH_CLIENT_ID!,
    response_type: "code",
    scope: "openid email",
    redirect_uri: redirectUri,
    state,
    nonce,
  }).toString();
  return new Response(null, {
    status: 302,
    headers: {
      location: authorization.toString(),
      "set-cookie": googleStateCookie(state),
      "cache-control": "no-store",
    },
  });
}

async function googleCallback(request: Request, env: Env): Promise<Response> {
  const headers = new Headers({ location: "/?auth_error=google", "cache-control": "no-store" });
  headers.append("set-cookie", googleStateCookie("", true));
  try {
    if (!googleConfigured(env)) throw new Error("Google OAuth is not configured");
    const url = new URL(request.url);
    const state = url.searchParams.get("state") || "";
    const code = url.searchParams.get("code") || "";
    const cookieState = cookieValue(request, GOOGLE_STATE_COOKIE) || "";
    if (!state || !code || !cookieState || state !== cookieState) {
      throw new Error("Google OAuth state validation failed");
    }
    const stored = await env.AUTH_DB.prepare(
      "SELECT nonce, expires_at FROM google_oauth_states WHERE state = ?",
    ).bind(state).first<{ nonce: string; expires_at: number }>();
    await env.AUTH_DB.prepare("DELETE FROM google_oauth_states WHERE state = ?").bind(state).run();
    if (!stored || stored.expires_at <= Math.floor(Date.now() / 1000)) {
      throw new Error("Google OAuth state expired");
    }
    const redirectUri = new URL("/auth/google/callback", request.url).toString();
    const tokenResponse = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: env.GOOGLE_OAUTH_CLIENT_ID!,
        client_secret: env.GOOGLE_OAUTH_CLIENT_SECRET!,
        redirect_uri: redirectUri,
        grant_type: "authorization_code",
      }),
    });
    if (!tokenResponse.ok) throw new Error("Google token exchange failed");
    const tokenPayload = await tokenResponse.json<{ id_token?: string }>();
    if (!tokenPayload.id_token) throw new Error("Google returned no ID token");
    const verificationResponse = await fetch(
      `https://oauth2.googleapis.com/tokeninfo?id_token=${encodeURIComponent(tokenPayload.id_token)}`,
    );
    if (!verificationResponse.ok) throw new Error("Google ID token verification failed");
    const claims = await verificationResponse.json<Record<string, unknown>>();
    if (
      claims.aud !== env.GOOGLE_OAUTH_CLIENT_ID ||
      claims.nonce !== stored.nonce ||
      String(claims.email_verified) !== "true" ||
      !claims.sub
    ) {
      throw new Error("Google ID token claims are invalid");
    }
    const email = normalizeEmail(claims.email);
    const subject = String(claims.sub);
    let user = await env.AUTH_DB.prepare(
      "SELECT id, email, provider FROM users WHERE provider = 'google' AND subject = ?",
    ).bind(subject).first<User>();
    if (!user) {
      user = { id: crypto.randomUUID(), email, provider: "google" };
      await env.AUTH_DB.prepare(
        `INSERT INTO users (id, provider, subject, email, created_at)
         VALUES (?, 'google', ?, ?, ?)`,
      ).bind(user.id, subject, email, Math.floor(Date.now() / 1000)).run();
    } else if (user.email !== email) {
      await env.AUTH_DB.prepare("UPDATE users SET email = ? WHERE id = ?")
        .bind(email, user.id).run();
    }
    const token = await createSession(env, user.id);
    headers.set("location", "/");
    headers.append("set-cookie", authCookie(token));
  } catch (error) {
    console.error("Google OAuth callback failed", error);
  }
  return new Response(null, { status: 302, headers });
}

async function signup(request: Request, env: Env): Promise<Response> {
  if (!(await rateLimit(request, env))) {
    return json({ ok: false, error: "请求过于频繁，请一分钟后重试。" }, 429);
  }
  try {
    const body = await readBody(request);
    const email = normalizeEmail(body.email);
    const password = String(body.password || "");
    if (password.length < 6 || password.length > 1024) {
      throw new Error("密码必须为 6–1024 个字符。");
    }
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const digest = await passwordDigest(password, salt);
    const user: User = { id: crypto.randomUUID(), email, provider: "local" };
    await env.AUTH_DB.prepare(
      `INSERT INTO users
       (id, provider, subject, email, password_salt, password_hash, created_at)
       VALUES (?, 'local', ?, ?, ?, ?, ?)`,
    ).bind(
      user.id,
      email,
      email,
      bytesToBase64(salt),
      bytesToBase64(digest),
      Math.floor(Date.now() / 1000),
    ).run();
    const token = await createSession(env, user.id);
    return json({ ok: true, user: { email, provider: "local" } }, 200, authCookie(token));
  } catch (error) {
    const message = String(error).includes("UNIQUE constraint failed")
      ? "该邮箱已经注册，请直接登录。"
      : error instanceof Error ? error.message : "注册失败。";
    return json({ ok: false, error: message }, 400);
  }
}

async function login(request: Request, env: Env): Promise<Response> {
  if (!(await rateLimit(request, env))) {
    return json({ ok: false, error: "请求过于频繁，请一分钟后重试。" }, 429);
  }
  try {
    const body = await readBody(request);
    const email = normalizeEmail(body.email);
    const password = String(body.password || "");
    const row = await env.AUTH_DB.prepare(
      `SELECT id, email, provider, password_salt, password_hash
       FROM users WHERE provider = 'local' AND subject = ?`,
    ).bind(email).first<User & { password_salt: string; password_hash: string }>();
    const salt = row ? base64ToBytes(row.password_salt) : new Uint8Array(16);
    const expected = row ? base64ToBytes(row.password_hash) : new Uint8Array(32);
    const actual = await passwordDigest(password, salt);
    if (!row || !safeEqual(actual, expected)) {
      throw new Error("邮箱或密码不正确。");
    }
    const token = await createSession(env, row.id);
    return json(
      { ok: true, user: { email: row.email, provider: row.provider } },
      200,
      authCookie(token),
    );
  } catch (error) {
    return json(
      { ok: false, error: error instanceof Error ? error.message : "登录失败。" },
      400,
    );
  }
}

async function logout(request: Request, env: Env): Promise<Response> {
  const token = cookieValue(request, AUTH_COOKIE);
  if (token) {
    // Resolve identity and ask the container to end this user's writing
    // session (terminate its spawned Paper Studio child process) before the
    // auth row is deleted. The container's own SESSIONS map has no other
    // way to learn that a researcher logged out: it otherwise only reaps a
    // session after four idle hours, so every earlier logout leaked a live
    // child process into the *shared* per-Worker-version container for the
    // rest of that window — starving concurrent researchers' memory and
    // eventually OOM-killing whoever's batch-writing job was heaviest at
    // the time. Best-effort: a container error here must not block logout.
    const user = await currentUser(request, env);
    if (user) {
      try {
        await proxyIdentified(request, env, user, "/api/online/session/close");
      } catch {
        // Best-effort cleanup; logout must still succeed.
      }
    }
    await env.AUTH_DB.prepare("DELETE FROM auth_sessions WHERE token_hash = ?")
      .bind(await sha256(token)).run();
  }
  return json({ ok: true }, 200, authCookie("", true));
}

function identityHeaders(request: Request, user: User | null): Headers {
  const headers = new Headers(request.headers);
  headers.delete("x-online-user-id");
  headers.delete("x-online-user-email");
  headers.delete("x-online-user-provider");
  if (user) {
    headers.set("x-online-user-id", user.id);
    headers.set("x-online-user-email", user.email);
    headers.set("x-online-user-provider", user.provider);
  }
  return headers;
}

function studioContainer(env: Env) {
  // A named container can survive a Worker/image deployment. Scope the name to
  // the immutable Worker version so every release starts from the matching
  // bundled demo project instead of serving a stale prior image indefinitely.
  return getContainer(env.ONLINE_STUDIO, `public-studio-${env.CF_VERSION_METADATA.id}`);
}

async function proxy(request: Request, env: Env, user: User | null): Promise<Response> {
  const forwarded = new Request(request, { headers: identityHeaders(request, user) });
  return studioContainer(env).fetch(forwarded);
}

async function proxyIdentified(
  request: Request,
  env: Env,
  user: User,
  path: string,
): Promise<Response> {
  const url = new URL(request.url);
  url.pathname = path;
  url.search = "";
  const forwarded = new Request(url, {
    method: "POST",
    headers: identityHeaders(request, user),
  });
  return studioContainer(env).fetch(forwarded);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    try {
      const url = new URL(request.url);
      const path = url.pathname;
      if (request.method === "POST" && path === "/api/auth/signup") {
        return signup(request, env);
      }
      if (request.method === "POST" && path === "/api/auth/login") {
        return login(request, env);
      }
      if (request.method === "POST" && path === "/api/auth/logout") {
        return logout(request, env);
      }
      const user = await currentUser(request, env);
      if (
        request.method === "GET"
        && !user
        && (path === "/studio" || path === "/demo-studio" || path.startsWith("/demo-studio/"))
      ) {
        return Response.redirect(new URL("/?login_required=1", request.url), 302);
      }
      if (request.method === "GET" && path === "/api/auth/session") {
        return json({
          ok: true,
          authenticated: user !== null,
          user: user ? { email: user.email, provider: user.provider } : null,
          google_configured: googleConfigured(env),
          access_token_required: false,
        });
      }
      if (request.method === "GET" && path === "/auth/google/start") {
        return googleStart(request, env);
      }
      if (request.method === "GET" && path === "/auth/google/callback") {
        return googleCallback(request, env);
      }
      return proxy(request, env, user);
    } catch (error) {
      console.error(error);
      return json({ ok: false, error: "在线服务暂时不可用，请稍后重试。" }, 500);
    }
  },
};
