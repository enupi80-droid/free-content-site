/**
 * 記事ページの匿名コメント機能(ログイン不要、Cloudflare Workerで自作したAPIを使う)
 */
(function () {
  const COMMENTS_API_BASE = "https://free-content-site-comments.tigeregg80.workers.dev";

  const root = document.querySelector("[data-comments-slug]");
  if (!root) return;
  const slug = root.dataset.commentsSlug;

  const listEl = document.getElementById("comments-list");
  const formEl = document.getElementById("comment-form");
  const nameEl = document.getElementById("comment-name");
  const textEl = document.getElementById("comment-text");
  const honeypotEl = formEl.querySelector('[name="honeypot"]');
  const statusEl = document.getElementById("comment-status");
  const submitBtn = formEl.querySelector('button[type="submit"]');

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function formatDate(iso) {
    const d = new Date(iso);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  function renderComments(comments) {
    if (!comments.length) {
      listEl.innerHTML = '<p class="comments-empty">まだコメントはありません。最初のコメントを書いてみませんか?</p>';
      return;
    }
    listEl.innerHTML = comments
      .map(
        (c, i) => `
      <div class="comment-item">
        <div class="comment-item-head">
          <span class="comment-item-no">${i + 1}</span>
          <span class="comment-item-name">${escapeHtml(c.name)}</span>
          <span class="comment-item-date">${formatDate(c.created_at)}</span>
        </div>
        <p class="comment-item-text">${escapeHtml(c.text).replace(/\n/g, "<br>")}</p>
      </div>`
      )
      .join("");
  }

  async function loadComments() {
    try {
      const res = await fetch(`${COMMENTS_API_BASE}/comments?slug=${encodeURIComponent(slug)}`);
      const data = await res.json();
      renderComments(data.comments || []);
    } catch (e) {
      listEl.innerHTML = '<p class="comments-empty">コメントを読み込めませんでした。</p>';
    }
  }

  formEl.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = textEl.value.trim();
    if (!text) return;

    submitBtn.disabled = true;
    statusEl.textContent = "";

    try {
      const res = await fetch(`${COMMENTS_API_BASE}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slug,
          name: nameEl.value.trim(),
          text,
          honeypot: honeypotEl.value,
        }),
      });

      if (res.status === 429) {
        statusEl.textContent = "少し時間を空けてから、もう一度投稿してください。";
      } else if (!res.ok) {
        statusEl.textContent = "投稿に失敗しました。もう一度お試しください。";
      } else {
        textEl.value = "";
        statusEl.textContent = "コメントを投稿しました。";
        loadComments();
      }
    } catch (e) {
      statusEl.textContent = "投稿に失敗しました。もう一度お試しください。";
    } finally {
      submitBtn.disabled = false;
    }
  });

  loadComments();
})();
