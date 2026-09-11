/**
 * free_content_site の記事コメント機能(匿名・ログイン不要)を提供するCloudflare Worker。
 * GET  /comments?slug=xxx   -> そのslugのコメント一覧を返す
 * POST /comments            -> {slug, name, text, honeypot} でコメントを投稿する
 * DELETE /comments/:id      -> 管理者用(X-Admin-Token一致時のみ削除)
 *
 * IPアドレスは平文で保存せず、salt付きハッシュにしてスパム対策のレート制限のみに使う。
 */

const RATE_LIMIT_SECONDS = 20;
const MAX_TEXT_LENGTH = 500;
const MAX_NAME_LENGTH = 30;
const MAX_LIST = 300;

function corsHeaders(origin, allowedOrigin) {
  const headers = {
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Admin-Token",
  };
  if (origin === allowedOrigin) {
    headers["Access-Control-Allow-Origin"] = origin;
  }
  return headers;
}

function json(data, status, extraHeaders) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...extraHeaders },
  });
}

async function hashIp(ip, salt) {
  const enc = new TextEncoder().encode(`${salt}:${ip}`);
  const digest = await crypto.subtle.digest("SHA-256", enc);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin") || "";
    const headers = corsHeaders(origin, env.ALLOWED_ORIGIN);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers });
    }

    if (url.pathname === "/comments" && request.method === "GET") {
      const slug = (url.searchParams.get("slug") || "").slice(0, 200);
      if (!slug) return json({ error: "slug is required" }, 400, headers);

      const { results } = await env.DB.prepare(
        "SELECT id, name, text, created_at FROM comments WHERE slug = ? ORDER BY created_at ASC LIMIT ?"
      )
        .bind(slug, MAX_LIST)
        .all();

      return json({ comments: results }, 200, headers);
    }

    if (url.pathname === "/comments" && request.method === "POST") {
      let body;
      try {
        body = await request.json();
      } catch {
        return json({ error: "invalid json" }, 400, headers);
      }

      const slug = (body.slug || "").toString().slice(0, 200).trim();
      let name = (body.name || "").toString().trim().slice(0, MAX_NAME_LENGTH);
      const text = (body.text || "").toString().trim().slice(0, MAX_TEXT_LENGTH);
      const honeypot = (body.honeypot || "").toString();

      if (honeypot) {
        // ボット対策のダミー項目。人間には見えないフィールドが埋まっていたら黒塗りで拒否。
        return json({ error: "rejected" }, 400, headers);
      }
      if (!slug || !text) {
        return json({ error: "slug and text are required" }, 400, headers);
      }
      if (!name) name = "名無し";

      const ip = request.headers.get("CF-Connecting-IP") || "unknown";
      const ipHash = await hashIp(ip, env.IP_SALT);

      const recent = await env.DB.prepare(
        "SELECT created_at FROM comments WHERE ip_hash = ? ORDER BY created_at DESC LIMIT 1"
      )
        .bind(ipHash)
        .first();

      if (recent) {
        const elapsed = (Date.now() - new Date(recent.created_at).getTime()) / 1000;
        if (elapsed < RATE_LIMIT_SECONDS) {
          return json({ error: "too many requests" }, 429, headers);
        }
      }

      const createdAt = new Date().toISOString();
      const safeName = escapeHtml(name);
      const safeText = escapeHtml(text);

      const result = await env.DB.prepare(
        "INSERT INTO comments (slug, name, text, ip_hash, created_at) VALUES (?, ?, ?, ?, ?) RETURNING id"
      )
        .bind(slug, safeName, safeText, ipHash, createdAt)
        .first();

      return json(
        { id: result.id, name: safeName, text: safeText, created_at: createdAt },
        201,
        headers
      );
    }

    const deleteMatch = url.pathname.match(/^\/comments\/(\d+)$/);
    if (deleteMatch && request.method === "DELETE") {
      const adminToken = request.headers.get("X-Admin-Token") || "";
      if (!env.ADMIN_TOKEN || adminToken !== env.ADMIN_TOKEN) {
        return json({ error: "unauthorized" }, 401, headers);
      }
      await env.DB.prepare("DELETE FROM comments WHERE id = ?").bind(deleteMatch[1]).run();
      return json({ ok: true }, 200, headers);
    }

    return json({ error: "not found" }, 404, headers);
  },
};
