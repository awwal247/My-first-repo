/* ==========================================================
   ZENITH OX v4.0 — Chat History Sidebar
   Features: Search, Pin, Rename, Restore-on-load
   ========================================================== */
const ChatHistory = (() => {
  const chatList = document.getElementById("zh-chat-list");
  const searchInput = document.getElementById("zh-search-input");
  let chats = [];
  let currentChatId = null;
  let currentMessages = [];

  // Snapshot the original "welcome" card markup so we can restore it
  // for brand-new / empty chats without having to hardcode it here.
  const _welcomeBox = document.getElementById("chat-box");
  const _welcomeHTML = _welcomeBox ? _welcomeBox.innerHTML : "";

  async function loadChats() {
    try {
      const r = await fetch("/api/chats");
      const data = await r.json();
      if (!data.ok) return;
      chats = data.chats || [];
      renderChats();
    } catch (e) {
      console.warn("ChatHistory load:", e);
    }
  }

  function renderChats(filter = "") {
    if (!chatList) return;
    chatList.innerHTML = "";
    const filtered = filter
      ? chats.filter(c => (c.title || "").toLowerCase().includes(filter.toLowerCase()))
      : chats;

    if (!filtered.length) {
      chatList.innerHTML = '<div class="zh-empty">No chats yet</div>';
      return;
    }

    const pinned = filtered.filter(c => c.pinned);
    const unpinned = filtered.filter(c => !c.pinned);

    if (pinned.length) {
      const label = document.createElement("div");
      label.className = "zh-date-label";
      label.textContent = "📌 Pinned";
      chatList.appendChild(label);
      pinned.forEach(c => chatList.appendChild(createChatItem(c)));
    }

    if (unpinned.length) {
      const label = document.createElement("div");
      label.className = "zh-date-label";
      label.textContent = "Recent";
      chatList.appendChild(label);
      unpinned.forEach(c => chatList.appendChild(createChatItem(c)));
    }
  }

  function createChatItem(chat) {
    const div = document.createElement("div");
    div.className = "zh-chat-item" + (chat.id === currentChatId ? " zh-active" : "");
    div.dataset.id = chat.id;

    const emoji = getModeEmoji(chat.mode);
    div.innerHTML = `
      <span class="zh-chat-icon">${emoji}</span>
      <div class="zh-chat-body">
        <div class="zh-chat-title">${esc(chat.title || "New chat")}</div>
        <div class="zh-chat-meta">${chat.mode} • ${chat.message_count || 0} messages</div>
      </div>
      <button class="zh-pin-btn ${chat.pinned ? "pinned" : ""}" title="${chat.pinned ? "Unpin" : "Pin"}">📌</button>
      <button class="zh-rename-btn" title="Rename">✏️</button>
      <button class="zh-delete-btn" title="Delete">🗑️</button>
    `;

    div.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      loadChat(chat.id);
    });

    div.querySelector(".zh-pin-btn").addEventListener("click", () => togglePin(chat.id));
    div.querySelector(".zh-rename-btn").addEventListener("click", () => startRename(div, chat));
    div.querySelector(".zh-delete-btn").addEventListener("click", () => deleteChat(chat.id));

    return div;
  }

  function getModeEmoji(mode) {
    const map = { researcher: "🔍", developer: "💻", story_writer: "📖", solve_it: "🧮", email_writer: "✉️", pptx_generator: "📊" };
    return map[mode] || "💬";
  }

  function esc(s) {
    return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  async function loadChat(chatId) {
    try {
      const r = await fetch(`/api/chats/${chatId}`);
      const data = await r.json();
      if (!data.ok) return;
      currentChatId = chatId;
      const chat = data.chat;
      currentMessages = (chat && Array.isArray(chat.messages)) ? chat.messages.slice() : [];
      const box = document.getElementById("chat-box");
      if (box) {
        if (currentMessages.length > 0) {
          box.innerHTML = "";
          currentMessages.forEach(msg => {
            if (window.appendChatMessage) window.appendChatMessage(msg.role, msg.content);
          });
        } else {
          // Nothing in this chat yet — show the welcome card instead of a blank pane.
          box.innerHTML = _welcomeHTML;
        }
      }
      renderChats(searchInput ? searchInput.value : "");
    } catch (e) {
      console.warn("loadChat:", e);
    }
  }

  async function togglePin(chatId) {
    try {
      const r = await fetch(`/api/chats/${chatId}/pin`, { method: "POST" });
      const data = await r.json();
      if (data.ok) loadChats();
    } catch (e) {
      console.warn("togglePin:", e);
    }
  }

  function startRename(div, chat) {
    const body = div.querySelector(".zh-chat-body");
    const titleEl = div.querySelector(".zh-chat-title");
    const oldTitle = chat.title || "New chat";
    const input = document.createElement("input");
    input.className = "zh-rename-input";
    input.value = oldTitle;
    body.replaceChild(input, titleEl);
    input.focus();

    async function save() {
      const newTitle = input.value.trim();
      if (newTitle && newTitle !== oldTitle) {
        try {
          const r = await fetch(`/api/chats/${chat.id}/rename`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: newTitle })
          });
          const data = await r.json();
          if (data.ok) loadChats();
        } catch (e) {
          console.warn("rename:", e);
        }
      }
      body.replaceChild(titleEl, input);
    }

    input.addEventListener("blur", save);
    input.addEventListener("keydown", e => { if (e.key === "Enter") save(); });
  }

  async function deleteChat(chatId) {
    if (!confirm("Delete this chat?")) return;
    try {
      const r = await fetch(`/api/chats/${chatId}`, { method: "DELETE" });
      const data = await r.json();
      if (data.ok) {
        if (currentChatId === chatId) {
          currentChatId = null;
          currentMessages = [];
          const box = document.getElementById("chat-box");
          if (box) box.innerHTML = _welcomeHTML;
        }
        loadChats();
      }
    } catch (e) {
      console.warn("deleteChat:", e);
    }
  }

  async function startNewChat(mode) {
    try {
      const r = await fetch("/api/chats/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "New chat", mode: mode || "researcher", messages: [] })
      });
      const data = await r.json();
      if (data.ok && data.chat_id) {
        currentChatId = data.chat_id;
        currentMessages = [];
        const box = document.getElementById("chat-box");
        if (box) box.innerHTML = _welcomeHTML;
        loadChats();
      }
    } catch (e) {
      console.warn("startNewChat:", e);
    }
  }

  // ------------------------------------------------------------------
  // Message persistence — keeps the active chat's `messages` array
  // (and auto-generated title) in sync with the backend so the
  // sidebar history / "Restore on Load" feature actually works.
  // ------------------------------------------------------------------

  function _autoTitle(text) {
    const clean = (text || "").replace(/\s+/g, " ").trim();
    if (!clean) return "New chat";
    return clean.length > 60 ? clean.slice(0, 60).trim() + "…" : clean;
  }

  async function _ensureChat() {
    if (currentChatId) return currentChatId;
    try {
      const r = await fetch("/api/chats/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "New chat", mode: window.ZENITH_MODE || "researcher", messages: [] })
      });
      const data = await r.json();
      if (data.ok && data.chat_id) {
        currentChatId = data.chat_id;
        currentMessages = [];
      }
    } catch (e) {
      console.warn("ensureChat:", e);
    }
    return currentChatId;
  }

  async function _persist(title) {
    if (!currentChatId) return;
    try {
      const payload = { messages: currentMessages };
      if (title) payload.title = title;
      await fetch(`/api/chats/${currentChatId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      loadChats();
    } catch (e) {
      console.warn("persist chat:", e);
    }
  }

  async function appendMessage(role, content) {
    await _ensureChat();
    if (!currentChatId) return;

    currentMessages.push({ role, content });

    let title = null;
    const userTurns = currentMessages.filter(m => m.role === "user").length;
    if (role === "user" && userTurns === 1) {
      title = _autoTitle(content);
    }
    await _persist(title);
  }

  async function replaceLastAssistant(content) {
    await _ensureChat();
    if (!currentChatId) return;

    for (let i = currentMessages.length - 1; i >= 0; i--) {
      if (currentMessages[i].role === "assistant") {
        currentMessages[i] = { role: "assistant", content };
        await _persist();
        return;
      }
    }
    // No prior assistant message found — just append.
    currentMessages.push({ role: "assistant", content });
    await _persist();
  }
  if (searchInput) {
    searchInput.addEventListener("input", () => renderChats(searchInput.value));
  }

  // Load on startup
  loadChats();

  // Restore most recent chat on load
  async function restoreRecent() {
    try {
      const r = await fetch("/api/chats");
      const data = await r.json();
      if (data.ok && data.chats && data.chats.length > 0) {
        const recent = data.chats[0];
        if (recent) loadChat(recent.id);
      }
    } catch (e) {}
  }
  restoreRecent();

  return { loadChats, startNewChat, appendMessage, replaceLastAssistant };
})();
