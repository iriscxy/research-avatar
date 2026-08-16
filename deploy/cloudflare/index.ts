import { Container, getContainer } from "@cloudflare/containers";

const AUTH_COOKIE = "online_studio_auth";
const AUTH_SECONDS = 30 * 24 * 60 * 60;
// Cloudflare Workers Web Crypto currently caps PBKDF2 at 100,000 iterations.
const PASSWORD_ITERATIONS = 100_000;

interface Env {
  ONLINE_STUDIO: DurableObjectNamespace;
  AUTH_DB: D1Database;
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
  const body = await request.json();
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
  const tokenBytes = crypto.getRandomValues(new Uint8Array(48));
  const token = bytesToBase64(tokenBytes)
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
  const now = Math.floor(Date.now() / 1000);
  await env.AUTH_DB.batch([
    env.AUTH_DB.prepare(
      "INSERT INTO auth_sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
    ).bind(await sha256(token), userId, now + AUTH_SECONDS, now),
    env.AUTH_DB.prepare("DELETE FROM auth_sessions WHERE expires_at <= ?").bind(now),
  ]);
  return token;
}

async function signup(request: Request, env: Env): Promise<Response> {
  if (!(await rateLimit(request, env))) {
    return json({ ok: false, error: "请求过于频繁，请一分钟后重试。" }, 429);
  }
  try {
    const body = await readBody(request);
    const email = normalizeEmail(body.email);
    const password = String(body.password || "");
    if (password.length < 12 || password.length > 1024) {
      throw new Error("密码必须为 12–1024 个字符。");
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
    await env.AUTH_DB.prepare("DELETE FROM auth_sessions WHERE token_hash = ?")
      .bind(await sha256(token)).run();
  }
  return json({ ok: true }, 200, authCookie("", true));
}

async function proxy(request: Request, env: Env, user: User | null): Promise<Response> {
  const headers = new Headers(request.headers);
  headers.delete("x-online-user-id");
  headers.delete("x-online-user-email");
  headers.delete("x-online-user-provider");
  if (user) {
    headers.set("x-online-user-id", user.id);
    headers.set("x-online-user-email", user.email);
    headers.set("x-online-user-provider", user.provider);
  }
  const forwarded = new Request(request, { headers });
  return getContainer(env.ONLINE_STUDIO, "public-studio").fetch(forwarded);
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
      if (request.method === "GET" && path === "/api/auth/session") {
        return json({
          ok: true,
          authenticated: user !== null,
          user: user ? { email: user.email, provider: user.provider } : null,
          google_configured: false,
          access_token_required: false,
        });
      }
      if (path.startsWith("/auth/google/")) {
        return Response.redirect(new URL("/?auth_error=google", request.url), 302);
      }
      return proxy(request, env, user);
    } catch (error) {
      console.error(error);
      return json({ ok: false, error: "在线服务暂时不可用，请稍后重试。" }, 500);
    }
  },
};
