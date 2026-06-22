const messagesEl = document.getElementById("messages");
const emptyStateEl = document.getElementById("empty-state");
const queryFormEl = document.getElementById("query-form");
const questionInputEl = document.getElementById("question-input");
const sendButtonEl = document.getElementById("send-button");
const statusEl = document.getElementById("status");
const docListEl = document.getElementById("doc-list");
const uploadZoneEl = document.getElementById("upload-zone");
const fileInputEl = document.getElementById("file-input");
const browseBtn = document.getElementById("browse-btn");
const toastContainerEl = document.getElementById("toast-container");
const modelInfoEl = document.getElementById("model-info");

// ── Toast ─────────────────────────────────────────────────────────
function showToast(message, type = "success", duration = 3500) {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  toastContainerEl.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity 0.3s";
    setTimeout(() => el.remove(), 300);
  }, duration);
}

// ── Status ────────────────────────────────────────────────────────
async function refreshStatus() {
  try {
    const data = await apiFetch("/api/health");
    statusEl.className = `status-pill ${data.vector_store_ok ? "ok" : "error"}`;
    statusEl.querySelector(".status-text").textContent =
      `${data.vector_store} · ${data.embedder_backend} · ${data.llm_backend}`;
    modelInfoEl.textContent =
      `Vector store: ${data.vector_store}\nEmbedder: ${data.embedder_backend}\nLLM: ${data.llm_backend}`;
  } catch {
    statusEl.className = "status-pill error";
    statusEl.querySelector(".status-text").textContent = "unreachable";
  }
}

// ── Document list ─────────────────────────────────────────────────
async function refreshDocuments() {
  try {
    const docs = await apiFetch("/api/documents");
    docListEl.innerHTML = "";

    if (!docs.length) {
      const li = document.createElement("li");
      li.className = "doc-empty";
      li.textContent = "No documents yet.";
      docListEl.appendChild(li);
      return;
    }

    for (const doc of docs) {
      const li = document.createElement("li");
      li.className = "doc-item";
      li.innerHTML = `
        <svg class="doc-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
        <div class="doc-info">
          <span class="doc-name" title="${escHtml(doc.filename)}">${escHtml(doc.filename)}</span>
          <span class="doc-meta">${doc.chunk_count > 0 ? `${doc.chunk_count} chunk${doc.chunk_count !== 1 ? "s" : ""}` : doc.status}</span>
        </div>
        <span class="doc-badge ${doc.status}">${doc.status === "completed" ? "✓" : doc.status}</span>
        <button class="doc-delete" aria-label="Delete ${escHtml(doc.filename)}" data-filename="${escHtml(doc.filename)}">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      `;
      docListEl.appendChild(li);
    }
  } catch (err) {
    docListEl.innerHTML = `<li class="doc-empty">Failed to load documents.</li>`;
  }
}

docListEl.addEventListener("click", async (e) => {
  const btn = e.target.closest(".doc-delete");
  if (!btn) return;
  const filename = btn.dataset.filename;
  btn.disabled = true;
  try {
    await apiFetch(`/api/documents/${encodeURIComponent(filename)}`, { method: "DELETE" });
    showToast(`Deleted "${filename}"`, "info");
    await refreshDocuments();
  } catch (err) {
    showToast(`Failed to delete "${filename}": ${err.message}`, "error");
    btn.disabled = false;
  }
});

// ── Upload ────────────────────────────────────────────────────────
browseBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  fileInputEl.click();
});

uploadZoneEl.addEventListener("click", () => fileInputEl.click());
uploadZoneEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") fileInputEl.click();
});

fileInputEl.addEventListener("change", () => {
  if (fileInputEl.files?.length) uploadFiles([...fileInputEl.files]);
  fileInputEl.value = "";
});

uploadZoneEl.addEventListener("dragover", (e) => {
  e.preventDefault();
  uploadZoneEl.classList.add("drag-over");
});
uploadZoneEl.addEventListener("dragleave", (e) => {
  if (!uploadZoneEl.contains(e.relatedTarget)) uploadZoneEl.classList.remove("drag-over");
});
uploadZoneEl.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadZoneEl.classList.remove("drag-over");
  const files = [...(e.dataTransfer?.files ?? [])];
  if (files.length) uploadFiles(files);
});

async function uploadFiles(files) {
  for (const file of files) {
    showToast(`Uploading "${file.name}"…`, "info", 60000);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await apiFetch("/api/documents/upload", { method: "POST", body: form });

      // clear the long-lived info toast and show outcome
      clearToasts("info");
      if (result.status === "completed") {
        showToast(`"${file.name}" ingested — ${result.chunk_count} chunks`, "success");
      } else {
        showToast(`"${file.name}" failed: ${result.error ?? result.status}`, "error");
      }
    } catch (err) {
      clearToasts("info");
      showToast(`Failed to upload "${file.name}": ${err.message}`, "error");
    }
    await refreshDocuments();
  }
}

function clearToasts(type) {
  toastContainerEl.querySelectorAll(`.toast.${type}`).forEach((t) => t.remove());
}

// ── Messages ──────────────────────────────────────────────────────
let hasMessages = false;

function hideEmptyState() {
  if (!hasMessages) {
    emptyStateEl.remove();
    hasMessages = true;
  }
}

function addUserMessage(text) {
  hideEmptyState();
  const row = document.createElement("div");
  row.className = "message-row user";
  row.innerHTML = `
    <div class="message-label">You</div>
    <div class="message-bubble">${escHtml(text)}</div>
  `;
  messagesEl.appendChild(row);
  scrollBottom();
}

function createAssistantRow() {
  hideEmptyState();
  const row = document.createElement("div");
  row.className = "message-row assistant";
  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  const cursor = document.createElement("span");
  cursor.className = "cursor";
  bubble.appendChild(cursor);
  row.innerHTML = `<div class="message-label">Assistant</div>`;
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollBottom();
  return { row, bubble, cursor };
}

function appendSources(row, sources) {
  if (!sources?.length) return;
  const wrapper = document.createElement("div");
  wrapper.className = "sources";
  wrapper.innerHTML = `<div class="sources-label">Sources (${sources.length})</div>`;
  for (const s of sources) {
    const details = document.createElement("details");
    details.className = "source-item";
    details.innerHTML = `
      <summary>
        ${escHtml(s.filename)} — chunk ${s.chunk_index}
        <span class="score-badge">${s.score.toFixed(2)}</span>
      </summary>
      <div class="source-snippet">${escHtml(s.snippet)}</div>
    `;
    wrapper.appendChild(details);
  }
  row.appendChild(wrapper);
}

function addErrorRow(message) {
  hideEmptyState();
  const row = document.createElement("div");
  row.className = "message-row error";
  row.innerHTML = `
    <div class="message-label">Error</div>
    <div class="message-bubble">${escHtml(message)}</div>
  `;
  messagesEl.appendChild(row);
  scrollBottom();
}

// ── Query (streaming) ─────────────────────────────────────────────
async function submitQuery(question) {
  sendButtonEl.disabled = true;
  addUserMessage(question);

  const { row, bubble, cursor } = createAssistantRow();

  try {
    const response = await fetch("/api/query/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!response.ok) throw new Error(`Server error ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        let event;
        try { event = JSON.parse(line.slice(6)); } catch { continue; }

        if (event.type === "token") {
          cursor.before(document.createTextNode(event.content));
          scrollBottom();
        } else if (event.type === "sources") {
          appendSources(row, event.sources);
        } else if (event.type === "error") {
          cursor.remove();
          addErrorRow(event.message);
          return;
        }
      }
    }
  } catch (err) {
    addErrorRow(err.message);
  } finally {
    cursor.remove();
    sendButtonEl.disabled = false;
    questionInputEl.focus();
    scrollBottom();
  }
}

queryFormEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = questionInputEl.value.trim();
  if (!q || sendButtonEl.disabled) return;
  questionInputEl.value = "";
  questionInputEl.style.height = "auto";
  submitQuery(q);
});

// Enter submits; Shift+Enter inserts newline
questionInputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    queryFormEl.requestSubmit();
  }
});

// Auto-grow textarea
questionInputEl.addEventListener("input", () => {
  questionInputEl.style.height = "auto";
  questionInputEl.style.height = Math.min(questionInputEl.scrollHeight, 160) + "px";
});

// Suggestion chips
document.getElementById("suggestions")?.addEventListener("click", (e) => {
  const btn = e.target.closest(".suggestion");
  if (!btn) return;
  questionInputEl.value = btn.dataset.q;
  questionInputEl.dispatchEvent(new Event("input"));
  questionInputEl.focus();
});

// ── Helpers ───────────────────────────────────────────────────────
function scrollBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function apiFetch(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const j = await res.json(); msg = j.detail ?? msg; } catch {}
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── Init ──────────────────────────────────────────────────────────
refreshStatus();
refreshDocuments();
