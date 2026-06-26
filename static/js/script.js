/* ==========================================================
   ZENITH OX v2.7 — Workspace Chat UI
   Thinking levels, token limiting, user-only edit, fresh chat on load, PDF export
   ========================================================== */
(() => {
  // v2.7 — Fresh chat on every dashboard open (no last-chat memory restore)
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.removeItem("zenith_last_chat_restored");
  }

  const chatBox = document.getElementById("chat-box");
  const form = document.getElementById("chatForm");
  const input = document.getElementById("user-input");
  const sendBtn = document.getElementById("sendBtn");
  const clearBtn = document.getElementById("clearBtn");
  const logoutBtn = document.getElementById("logoutBtn");
  const micBtn = document.getElementById("micBtn");
  const exportBtn = document.getElementById("exportBtn");
  const exportDropdown = document.getElementById("exportDropdown");
  const regenerateBtn = document.getElementById("regenerateBtn");
  const fileInput = document.getElementById("fileInput");
  const photoInput = document.getElementById("photoInput");
  const cameraInput = document.getElementById("cameraInput");
  const codeInput = document.getElementById("codeInput");
  const filePreview = document.getElementById("file-preview");
  const fileCount = document.getElementById("fileCount");
  const toastContainer = document.getElementById("toastContainer");
  const composerPlusBtn = document.getElementById("composerPlusBtn");
  const attachSheet = document.getElementById("attachSheet");
  const attachSheetOverlay = document.getElementById("attachSheetOverlay");
  const attachSheetClose = document.getElementById("attachSheetClose");
  const attachImportPanel = document.getElementById("attachImportPanel");
  const attachImportLabel = document.getElementById("attachImportLabel");
  const attachImportUrl = document.getElementById("attachImportUrl");
  const attachImportNote = document.getElementById("attachImportNote");
  const attachImportConfirm = document.getElementById("attachImportConfirm");
  const attachImportCancel = document.getElementById("attachImportCancel");
  const modelSelect = document.getElementById("modelSelect");
  const modelStatus = document.getElementById("modelStatus");

  const MODEL_STORAGE_KEY = "zenith:selected-model";
  const THINK_MIN_MS = 1600;

  // v2.7 — Thinking level state (controlled by dropdown, NOT by user typing temps)
  let _thinkingLevel = "medium";
  let _temperature = 1.4;

  function currentThinkingLevel() { return _thinkingLevel; }
  function currentTemperature() { return _temperature; }

  // Wire up thinking dropdown
  const thinkingToggle = document.getElementById("thinkingToggle");
  const thinkingDropdown = document.getElementById("thinkingDropdown");
  const thinkingStatusLabel = document.getElementById("thinkingStatusLabel");
  const thinkOptions = document.querySelectorAll(".v27-think-option");

  const THINK_LABELS = {
    low:       "🌡 Low thinking",
    medium:    "⚡ Medium thinking",
    high:      "🔥 High thinking",
    high_high: "🚀 High High thinking"
  };

  if (thinkingToggle && thinkingDropdown) {
    thinkingToggle.addEventListener("click", e => {
      e.stopPropagation();
      thinkingDropdown.classList.toggle("open");
      thinkingToggle.classList.toggle("active");
    });
    document.addEventListener("click", () => {
      thinkingDropdown.classList.remove("open");
      thinkingToggle.classList.remove("active");
    });
  }

  thinkOptions && thinkOptions.forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      if (btn.dataset.locked === "true") {
        showToast("High thinking modes require a Pro plan. Upgrade to unlock.", "error");
        return;
      }
      const level = btn.dataset.level;
      const temp  = parseFloat(btn.dataset.temp);
      _thinkingLevel = level;
      _temperature   = temp;
      thinkOptions.forEach(b => b.classList.remove("v27-think-option--active"));
      btn.classList.add("v27-think-option--active");
      if (thinkingStatusLabel) thinkingStatusLabel.textContent = THINK_LABELS[level] || level;
      if (thinkingDropdown) {
        thinkingDropdown.classList.remove("open");
        thinkingToggle && thinkingToggle.classList.remove("active");
      }
    });
  });

  // v2.7 — Model selector in the v27-model-bar (top bar)
  const topModelSelect = document.getElementById("modelSelect");
  const modelStatusBar = document.getElementById("modelStatus");
  if (topModelSelect) {
    topModelSelect.addEventListener("change", () => {
      const opt = topModelSelect.options[topModelSelect.selectedIndex];
      if (opt && opt.dataset.premium === "true" && !window.ZENITH_USER_PREMIUM) {
        showToast("This model requires a Pro plan. Upgrade to unlock.", "error");
        topModelSelect.value = window.ZENITH_SELECTED_MODEL || topModelSelect.options[0].value;
        return;
      }
      if (modelStatusBar) modelStatusBar.textContent = opt ? opt.textContent.replace(" 🔒 Premium", "") : "";
    });
  }
  const FILE_RE = new RegExp("^(?:#|//|/\\s*\\*\\*|<!--)?\\s*File:\\s*(.+?)\\s*(?:\\*/|-->)?$", "i");
  const THINK_STEPS = {
    developer: ["run cat", "run touch", "run nano", "review schema", "shape patch"],
    researcher: ["scan context", "rank sources", "trace facts", "draft answer"],
    story_writer: ["shape tone", "build scene", "refine rhythm", "tighten prose"],
    solve_it: ["parse problem", "set steps", "check math", "verify answer"],
    email_writer: ["read request", "set tone", "draft email", "polish copy"],
    default: ["read prompt", "plan reply", "draft response", "final check"],
  };

  const renderer = new marked.Renderer();
  renderer.code = function({ text, lang }) {
    const code = text || "";
    const language = lang || "plaintext";
    let filename = null;
    let cleanCode = code;
    const lines = code.split("\n");
    if (lines.length > 0) {
      const match = lines[0].trim().match(FILE_RE);
      if (match) {
        filename = match[1].trim();
        cleanCode = lines.slice(1).join("\n").trim();
      }
    }
    let hl;
    try {
      hl = hljs.getLanguage(language)
        ? hljs.highlight(cleanCode, { language }).value
        : hljs.highlightAuto(cleanCode).value;
    } catch (e) {
      hl = cleanCode.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
    const label = filename ? `📄 ${filename}` : language;
    return `<div class="code-block-wrapper"><div class="code-header"><span class="code-lang">${label}</span><button class="copy-btn" onclick="copyCode(this)" data-code="${btoa(unescape(encodeURIComponent(cleanCode)))}">Copy</button></div><pre><code class="hljs ${language}">${hl}</code></pre></div>`;
  };
  marked.setOptions({ renderer, breaks: true, gfm: true });

  window.copyCode = function(btn) {
    const code = decodeURIComponent(escape(atob(btn.dataset.code)));
    navigator.clipboard.writeText(code).then(() => {
      btn.textContent = "Copied!";
      setTimeout(() => { btn.textContent = "Copy"; }, 1600);
    });
  };

  let pendingFiles = [];

  function esc(value) {
    return (value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function currentModelKey() {
    return (modelSelect && modelSelect.value) || window.ZENITH_SELECTED_MODEL || "llama_versatile_31";
  }

  function updateModelStatus() {
    // v2.7 — model selector is now in the top bar (id="modelSelect" in v27-model-bar)
    const ms = document.getElementById("modelStatus");
    const sel = document.getElementById("modelSelect");
    if (!sel || !ms) return;
    const label = sel.options[sel.selectedIndex]?.textContent.replace(" 🔒 Premium", "") || currentModelKey();
    ms.textContent = label;
  }

  function bootModelSelection() {
    if (!modelSelect) return;
    const saved = localStorage.getItem(MODEL_STORAGE_KEY);
    const boot = saved || window.ZENITH_SELECTED_MODEL;
    if (boot && Array.from(modelSelect.options).some(opt => opt.value === boot)) {
      modelSelect.value = boot;
    }
    updateModelStatus();
    modelSelect.addEventListener("change", () => {
      localStorage.setItem(MODEL_STORAGE_KEY, modelSelect.value);
      updateModelStatus();
      showToast(`Model set to ${modelSelect.options[modelSelect.selectedIndex].textContent}`, "info");
    });
  }

  function renderMath(el) {
    if (window.renderMathInElement) {
      renderMathInElement(el, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "$", right: "$", display: false },
          { left: "\\(", right: "\\)", display: false },
          { left: "\\[", right: "\\]", display: true },
        ],
        throwOnError: false,
      });
    }
  }

  function addMessage(text, cls) {
    const d = document.createElement("div");
    d.className = `message ${cls || "bot"}`;
    if (cls && cls.includes("user")) d.textContent = text;
    else d.innerHTML = text;
    chatBox.appendChild(d);
    chatBox.scrollTop = chatBox.scrollHeight;
    return d;
  }

  function addFileIndicator(filename) {
    const d = document.createElement("div");
    d.className = "message user file-indicator";
    d.innerHTML = `📎 ${esc(filename)}`;
    chatBox.appendChild(d);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function addCopyBtn(wrapper, txt) {
    const btn = document.createElement("button");
    btn.className = "msg-copy-btn";
    btn.title = "Copy response";
    btn.innerHTML = "📋";
    btn.addEventListener("click", () => {
      navigator.clipboard.writeText(txt).then(() => {
        btn.innerHTML = "✓";
        setTimeout(() => { btn.innerHTML = "📋"; }, 1600);
      });
    });
    wrapper.appendChild(btn);
  }

  function addMsgActions(wrapper, userText, botText) {
    const actions = document.createElement("div");
    actions.className = "msg-actions";

    const regenBtn = document.createElement("button");
    regenBtn.className = "msg-action-btn";
    regenBtn.innerHTML = "🔄 Regenerate";
    regenBtn.addEventListener("click", () => doRegenerate());
    actions.appendChild(regenBtn);

    const editBtn = document.createElement("button");
    editBtn.className = "msg-action-btn";
    editBtn.innerHTML = "✏️ Edit";
    editBtn.addEventListener("click", () => enableEdit(wrapper, userText || botText));
    actions.appendChild(editBtn);

    wrapper.appendChild(actions);
  }

  function enableEdit(wrapper, currentText) {
    const content = wrapper.querySelector(".md-content");
    if (!content) return;
    const ta = document.createElement("textarea");
    ta.className = "edit-textarea";
    ta.value = currentText;
    content.innerHTML = "";
    content.appendChild(ta);
    const btnRow = document.createElement("div");
    btnRow.className = "edit-actions";
    const saveBtn = document.createElement("button");
    saveBtn.className = "edit-save-btn";
    saveBtn.textContent = "Save";
    const cancelBtn = document.createElement("button");
    cancelBtn.className = "edit-cancel-btn";
    cancelBtn.textContent = "Cancel";
    btnRow.appendChild(saveBtn);
    btnRow.appendChild(cancelBtn);
    content.appendChild(btnRow);
    ta.focus();
    saveBtn.addEventListener("click", () => {
      const newText = ta.value.trim();
      content.innerHTML = marked.parse(newText);
      renderMath(content);
      addCopyBtn(wrapper, newText);
    });
    cancelBtn.addEventListener("click", () => {
      content.innerHTML = marked.parse(currentText);
      renderMath(content);
      addCopyBtn(wrapper, currentText);
    });
  }

  function appendBotResponse(txt, dlUrl, dlName) {
    const wrapper = document.createElement("div");
    wrapper.className = "message bot";
    const content = document.createElement("div");
    content.className = "md-content";
    content.innerHTML = marked.parse(txt || "");
    renderMath(content);
    wrapper.appendChild(content);
    if (dlUrl) {
      const a = document.createElement("a");
      a.href = dlUrl;
      a.download = dlName || "download";
      a.className = "download-btn";
      a.textContent = `📥 Download ${dlName || "file"}`;
      wrapper.appendChild(a);
    }
    if (txt) {
      addCopyBtn(wrapper, txt);
      addMsgActions(wrapper, null, txt);
    }
    chatBox.appendChild(wrapper);
    chatBox.scrollTop = chatBox.scrollHeight;
    return wrapper;
  }

  function createThinkingTrace() {
    const steps = THINK_STEPS[window.ZENITH_MODE] || THINK_STEPS.default;
    const wrapper = document.createElement("div");
    wrapper.className = "message bot thinking-trace";
    wrapper.innerHTML = `
      <div class="thinking-card">
        <div class="thinking-card__head">
          <span class="thinking-dot"></span>
          <strong>Thinking</strong>
          <small class="thinking-elapsed">0.0s</small>
        </div>
        <div class="thinking-card__status">Preparing response...</div>
        <div class="thinking-chip-row">${steps.map(step => `<span>${esc(step)}</span>`).join("")}</div>
      </div>`;
    chatBox.appendChild(wrapper);
    chatBox.scrollTop = chatBox.scrollHeight;

    const status = wrapper.querySelector(".thinking-card__status");
    const elapsed = wrapper.querySelector(".thinking-elapsed");
    const started = Date.now();
    let idx = 0;
    const interval = setInterval(() => {
      const seconds = ((Date.now() - started) / 1000).toFixed(1);
      if (elapsed) elapsed.textContent = `${seconds}s`;
      if (status) status.textContent = steps[idx % steps.length];
      idx += 1;
    }, 260);

    return {
      started,
      wrapper,
      async finalize() {
        const wait = Math.max(0, THINK_MIN_MS - (Date.now() - started));
        if (wait) await new Promise(resolve => setTimeout(resolve, wait));
        clearInterval(interval);
        const total = ((Date.now() - started) / 1000).toFixed(1);
        wrapper.classList.add("thinking-trace--done");
        wrapper.innerHTML = `
          <div class="thinking-card thinking-card--done">
            <div class="thinking-card__head"><span class="thinking-dot"></span><strong>Thought for ${total}s</strong></div>
            <div class="thinking-chip-row">${steps.slice(0, 3).map(step => `<span>${esc(step)}</span>`).join("")}</div>
          </div>`;
      },
      remove() {
        clearInterval(interval);
        wrapper.remove();
      }
    };
  }

  function renderFilePreview() {
    if (!pendingFiles.length) {
      filePreview.classList.add("hidden");
      fileCount.textContent = "";
      return;
    }
    filePreview.classList.remove("hidden");
    filePreview.innerHTML = pendingFiles.map((f, i) => `
      <span class="file-tag">📎 ${esc(f.name)} (${(f.size / 1024).toFixed(1)} KB)
        <button data-index="${i}">✕</button>
      </span>`).join("");
    fileCount.textContent = `${pendingFiles.length} file${pendingFiles.length > 1 ? "s" : ""} selected`;
    filePreview.querySelectorAll("button").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.dataset.index);
        pendingFiles.splice(idx, 1);
        renderFilePreview();
      });
    });
  }

  function addPickedFiles(files) {
    const arr = Array.from(files || []);
    arr.forEach(file => {
      const dup = pendingFiles.some(p => p.name === file.name && p.size === file.size && p.lastModified === file.lastModified);
      if (!dup) pendingFiles.push(file);
    });
    renderFilePreview();
    closeAttachSheet();
  }

  function openAttachSheet() {
    if (!attachSheet || !attachSheetOverlay) return;
    attachSheet.classList.add("open");
    attachSheetOverlay.classList.add("active");
    attachSheet.setAttribute("aria-hidden", "false");
  }

  function closeAttachSheet() {
    if (!attachSheet || !attachSheetOverlay) return;
    attachSheet.classList.remove("open");
    attachSheetOverlay.classList.remove("active");
    attachSheet.setAttribute("aria-hidden", "true");
    hideImportPanel();
  }

  function showImportPanel(provider) {
    const providerMeta = {
      gdrive: {
        label: "Paste Google Drive file link",
        note: "Use a public/shared Google Drive file link.",
        placeholder: "https://drive.google.com/file/d/...",
      },
      github: {
        label: "Paste GitHub link",
        note: "Supports public GitHub repo, blob, raw, archive, or release asset links.",
        placeholder: "https://github.com/...",
      }
    }[provider];
    if (!providerMeta || !attachImportPanel) return;
    attachImportPanel.classList.remove("hidden");
    attachImportLabel.textContent = providerMeta.label;
    attachImportNote.textContent = providerMeta.note;
    attachImportUrl.placeholder = providerMeta.placeholder;
    attachImportUrl.value = "";
    attachImportConfirm.dataset.provider = provider;
    setTimeout(() => attachImportUrl.focus(), 40);
  }

  function hideImportPanel() {
    if (!attachImportPanel) return;
    attachImportPanel.classList.add("hidden");
    attachImportConfirm.dataset.provider = "";
    attachImportUrl.value = "";
  }

  function b64ToBytes(b64) {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
    return out;
  }

  async function importExternal(provider, url) {
    const r = await fetch("/import-external", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, url })
    });
    const data = await r.json();
    if (!data.ok) throw new Error(data.error || "Import failed");
    const bytes = b64ToBytes(data.data_b64);
    const file = new File([bytes], data.filename, { type: data.content_type || "application/octet-stream", lastModified: Date.now() });
    addPickedFiles([file]);
    showToast(`${data.filename} added`, "success");
  }

  async function handleImportConfirm() {
    const provider = attachImportConfirm.dataset.provider;
    const url = (attachImportUrl.value || "").trim();
    if (!provider || !url) {
      showToast("Paste a valid public link", "error");
      return;
    }
    attachImportConfirm.disabled = true;
    const oldLabel = attachImportConfirm.textContent;
    attachImportConfirm.textContent = "Importing...";
    try {
      await importExternal(provider, url);
      hideImportPanel();
      closeAttachSheet();
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      attachImportConfirm.disabled = false;
      attachImportConfirm.textContent = oldLabel;
    }
  }

  function wireAttachSheet() {
    composerPlusBtn && composerPlusBtn.addEventListener("click", openAttachSheet);
    attachSheetOverlay && attachSheetOverlay.addEventListener("click", closeAttachSheet);
    attachSheetClose && attachSheetClose.addEventListener("click", closeAttachSheet);
    attachImportCancel && attachImportCancel.addEventListener("click", hideImportPanel);
    attachImportConfirm && attachImportConfirm.addEventListener("click", handleImportConfirm);
    attachImportUrl && attachImportUrl.addEventListener("keydown", e => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleImportConfirm();
      }
    });

    document.querySelectorAll("[data-attach-action]").forEach(btn => {
      btn.addEventListener("click", () => {
        const action = btn.dataset.attachAction;
        if (action === "camera") cameraInput?.click();
        if (action === "photo") photoInput?.click();
        if (action === "file") fileInput?.click();
        if (action === "code") codeInput?.click();
        if (action === "gdrive" || action === "github") showImportPanel(action);
      });
    });

    [fileInput, photoInput, cameraInput].forEach(el => {
      el && el.addEventListener("change", () => {
        if (el.files?.length) addPickedFiles(el.files);
        el.value = "";
      });
    });
  }

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 170)}px`;
  });
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true }));
    }
  });

  sendBtn.addEventListener("click", e => {
    e.preventDefault();
    form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true }));
  });

  async function streamRender(message, thinking) {
    let wrapper = null;
    let content = null;
    let shown = false;
    let full = "";
    let result = { ok: true, response: "", download_url: null, download_name: null };

    async function ensureVisible() {
      if (shown) return;
      await thinking.finalize();
      wrapper = document.createElement("div");
      wrapper.className = "message bot";
      content = document.createElement("div");
      content.className = "md-content";
      wrapper.appendChild(content);
      chatBox.appendChild(wrapper);
      shown = true;
    }

    try {
      const resp = await fetch("/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, model_key: currentModelKey() })
      });
      if (!resp.ok || !resp.body) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.error || `HTTP ${resp.status}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n\n");
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          let payload;
          try { payload = JSON.parse(line.slice(5).trim()); } catch (e) { continue; }
          if (payload.error) throw new Error(payload.error);
          if (payload.delta) {
            full += payload.delta;
            if (!shown && (Date.now() - thinking.started >= THINK_MIN_MS || full.length > 120)) {
              await ensureVisible();
            }
            if (shown && content) {
              content.innerHTML = marked.parse(full) + '<span class="text-tracker-cursor">▌</span>';
              chatBox.scrollTop = chatBox.scrollHeight;
            }
          }
          if (payload.done) {
            result.download_url = payload.download_url || null;
            result.download_name = payload.download_name || null;
          }
        }
      }
    } catch (err) {
      result.ok = false;
      result.error = err.message;
    }

    await ensureVisible();
    if (content) {
      content.innerHTML = marked.parse(full);
      renderMath(content);
      if (!result.ok) {
        content.innerHTML += `<div class="stream-error">⚠ ${esc(result.error || "Connection error")}</div>`;
      }
    }
    if (result.download_url && wrapper) {
      const a = document.createElement("a");
      a.href = result.download_url;
      a.download = result.download_name || "download";
      a.className = "download-btn";
      a.textContent = `📥 Download ${result.download_name || "file"}`;
      wrapper.appendChild(a);
    }
    if (full && wrapper) {
      addCopyBtn(wrapper, full);
      addMsgActions(wrapper, null, full);
    }

    result.response = full;
    return result;
  }

  window.appendChatMessage = function(role, content) {
    const isUser = role === "user";
    const d = document.createElement("div");
    d.className = `message ${isUser ? "user" : "bot"}`;
    if (isUser) d.textContent = content;
    else {
      d.innerHTML = `<div class="md-content">${marked.parse(content)}</div>`;
      renderMath(d);
      addCopyBtn(d, content);
      addMsgActions(d, null, content);
    }
    chatBox.appendChild(d);
    chatBox.scrollTop = chatBox.scrollHeight;
  };

  async function loadHistory() {
    try {
      const r = await fetch("/history");
      const data = await r.json();
      if (data.ok && data.messages && data.messages.length > 0) {
        const welcome = chatBox.querySelector(".welcome");
        if (welcome) welcome.remove();
        data.messages.forEach(msg => window.appendChatMessage(msg.role, msg.content));
      }
    } catch (e) {}
  }
  if (typeof ChatHistory === "undefined") loadHistory();

  async function sendMessage(message) {
    if (pendingFiles.length) pendingFiles.forEach(f => addFileIndicator(f.name));
    if (message) addMessage(message, "user");
    sendBtn.disabled = true;
    const canStream = !pendingFiles.length && window.ZENITH_MODE !== "pptx_generator";
    const thinking = createThinkingTrace();

    if (canStream) {
      try {
        const result = await streamRender(message, thinking);
        if (typeof ChatHistory !== "undefined") {
          if (message) ChatHistory.appendMessage("user", message);
          if (result.response) ChatHistory.appendMessage("assistant", result.response);
        }
        window.dispatchEvent(new Event("zenith:message-sent"));
      } catch (err) {
        thinking.remove();
        addMessage(`⚠ Connection error: ${err.message}`, "bot error");
      } finally {
        sendBtn.disabled = false;
        input.focus();
      }
      return;
    }

    try {
      let r;
      if (pendingFiles.length) {
        const fd = new FormData();
        pendingFiles.forEach(f => fd.append("files", f));
        fd.append("message", message || "Please analyze these files");
        fd.append("model_key", currentModelKey());
        r = await fetch("/chat", { method: "POST", body: fd });
        pendingFiles = [];
        renderFilePreview();
        fileInput.value = "";
      } else {
        r = await fetch("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            model_key: currentModelKey(),
            thinking_level: currentThinkingLevel(),
            temperature: currentTemperature()
          })
        });
      }
      const data = await r.json();
      await thinking.finalize();
      if (!data.ok) {
        if (data.token_limit_exceeded) {
          showToast(data.error || "Daily token limit reached. Upgrade to Pro for unlimited access.", "error");
          setTimeout(() => { window.location.href = data.redirect || "/paywall"; }, 2000);
          return;
        }
        addMessage(`⚠ ${data.error || "Unknown error"}`, "bot error");
        return;
      }
      appendBotResponse(data.response, data.download_url, data.download_name);
      if (typeof ChatHistory !== "undefined") {
        if (message) ChatHistory.appendMessage("user", message);
        ChatHistory.appendMessage("assistant", data.response);
      }
      window.dispatchEvent(new Event("zenith:message-sent"));
    } catch (err) {
      thinking.remove();
      addMessage(`⚠ Connection error: ${err.message}`, "bot error");
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }

  form.addEventListener("submit", e => {
    e.preventDefault();
    const msg = input.value.trim();
    if (!msg && !pendingFiles.length) return;
    input.value = "";
    input.style.height = "auto";
    sendMessage(msg);
  });

  clearBtn && clearBtn.addEventListener("click", async () => {
    if (!confirm("Clear all chat memory for this mode?")) return;
    try {
      const r = await fetch("/clear", { method: "POST" });
      const data = await r.json();
      if (data.ok) {
        chatBox.innerHTML = "";
        addMessage("Memory cleared. Starting fresh.", "bot welcome");
        if (typeof ChatHistory !== "undefined") ChatHistory.startNewChat(window.ZENITH_MODE);
      }
    } catch (err) {
      addMessage(`⚠ Could not clear: ${err.message}`, "bot error");
    }
  });

  logoutBtn && logoutBtn.addEventListener("click", () => { window.location.href = "/logout"; });

  async function doRegenerate() {
    const thinking = createThinkingTrace();
    if (regenerateBtn) regenerateBtn.disabled = true;
    try {
      const r = await fetch("/regenerate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_key: currentModelKey() })
      });
      const data = await r.json();
      await thinking.finalize();
      if (!data.ok) {
        addMessage(`⚠ ${data.error || "Regeneration failed"}`, "bot error");
        return;
      }
      appendBotResponse(data.response, data.download_url, data.download_name);
      if (typeof ChatHistory !== "undefined") ChatHistory.replaceLastAssistant(data.response);
    } catch (err) {
      thinking.remove();
      addMessage(`⚠ Regeneration error: ${err.message}`, "bot error");
    } finally {
      if (regenerateBtn) regenerateBtn.disabled = false;
    }
  }
  regenerateBtn && regenerateBtn.addEventListener("click", doRegenerate);

  let recognition = null;
  if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = e => {
      const transcript = e.results[0][0].transcript;
      input.value = `${input.value ? `${input.value} ` : ""}${transcript}`;
      input.style.height = "auto";
      input.style.height = `${Math.min(input.scrollHeight, 170)}px`;
      micBtn.classList.remove("voice-recording", "active");
      showToast("Voice captured", "info");
    };
    recognition.onerror = e => {
      micBtn.classList.remove("voice-recording", "active");
      showToast(`Voice error: ${e.error}`, "error");
    };
    recognition.onend = () => { micBtn.classList.remove("voice-recording", "active"); };
    micBtn.addEventListener("click", () => {
      if (micBtn.classList.contains("voice-recording")) {
        recognition.stop();
        return;
      }
      micBtn.classList.add("voice-recording", "active");
      try { recognition.start(); }
      catch (e) {
        micBtn.classList.remove("voice-recording", "active");
        showToast("Could not start voice input", "error");
      }
    });
  } else if (micBtn) {
    micBtn.style.display = "none";
  }

  exportBtn && exportBtn.addEventListener("click", e => {
    e.stopPropagation();
    exportDropdown.classList.toggle("show");
  });
  document.addEventListener("click", () => exportDropdown.classList.remove("show"));
  exportDropdown && exportDropdown.querySelectorAll("button").forEach(btn => {
    btn.addEventListener("click", async () => {
      const fmt = btn.dataset.format;
      const messages = collectMessages();
      if (!messages.length) {
        showToast("No messages to export", "error");
        return;
      }

      if (fmt === "pdf") {
        exportChatAsPDF(messages);
        return;
      }

      try {
        const r = await fetch("/export-chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ format: fmt, mode: window.ZENITH_MODE, messages })
        });
        const data = await r.json();
        if (data.ok) {
          window.location.href = data.url;
          showToast("Chat exported!", "success");
        } else {
          showToast(data.error || "Export failed", "error");
        }
      } catch (err) {
        showToast(`Export error: ${err.message}`, "error");
      }
    });
  });

  function exportChatAsPDF(messages) {
    try {
      if (!window.jspdf) {
        showToast("PDF library not loaded. Check your connection.", "error");
        return;
      }
      const { jsPDF } = window.jspdf;
      const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });

      const pageW = doc.internal.pageSize.getWidth();
      const pageH = doc.internal.pageSize.getHeight();
      const margin = 18;
      const contentW = pageW - margin * 2;
      const now = new Date();
      const modeName = (window.ZENITH_MODE || "workspace").replace(/_/g, " ");
      const timestamp = now.toLocaleString();

      let y = margin;

      function checkPageBreak(needed) {
        if (y + needed > pageH - margin) {
          doc.addPage();
          y = margin;
        }
      }

      function writeLine(text, opts = {}) {
        const { fontSize = 10, bold = false, color = [220, 228, 255], indent = 0 } = opts;
        doc.setFontSize(fontSize);
        doc.setFont("helvetica", bold ? "bold" : "normal");
        doc.setTextColor(...color);
        const lines = doc.splitTextToSize(text, contentW - indent);
        lines.forEach(line => {
          checkPageBreak(fontSize * 0.4 + 2);
          doc.text(line, margin + indent, y);
          y += fontSize * 0.38 + 2;
        });
      }

      doc.setFillColor(7, 12, 28);
      doc.rect(0, 0, pageW, pageH, "F");

      doc.setFillColor(14, 21, 52);
      doc.roundedRect(margin - 4, y - 2, contentW + 8, 22, 4, 4, "F");

      writeLine("✦  ZENITH OX", { fontSize: 14, bold: true, color: [180, 160, 255] });
      writeLine(`Mode: ${modeName.charAt(0).toUpperCase() + modeName.slice(1)}   ·   Exported: ${timestamp}`, {
        fontSize: 8, color: [140, 150, 190]
      });
      y += 6;

      doc.setDrawColor(80, 70, 140);
      doc.setLineWidth(0.3);
      doc.line(margin, y, pageW - margin, y);
      y += 6;

      messages.forEach((msg, i) => {
        const isUser = msg.role === "user";
        const roleLabel = isUser ? "You" : "Zenith OX";
        const roleColor = isUser ? [120, 180, 255] : [160, 120, 255];
        const bubbleColor = isUser ? [14, 28, 58] : [20, 14, 42];

        const bodyLines = doc.splitTextToSize(msg.content || "", contentW - 6);
        const blockH = bodyLines.length * 5.2 + 14;
        checkPageBreak(blockH + 4);

        doc.setFillColor(...bubbleColor);
        doc.roundedRect(margin - 2, y - 1, contentW + 4, blockH, 4, 4, "F");

        doc.setFontSize(8);
        doc.setFont("helvetica", "bold");
        doc.setTextColor(...roleColor);
        doc.text(roleLabel, margin + 2, y + 6);
        y += 10;

        doc.setFontSize(9.5);
        doc.setFont("helvetica", "normal");
        doc.setTextColor(210, 218, 245);
        bodyLines.forEach(line => {
          checkPageBreak(5.2);
          doc.text(line, margin + 2, y);
          y += 5.2;
        });

        y += 6;
      });

      y += 4;
      doc.setDrawColor(60, 55, 110);
      doc.line(margin, y, pageW - margin, y);
      y += 5;
      writeLine(`Zenith OX v2.6  ·  ${messages.length} message${messages.length !== 1 ? "s" : ""}`, {
        fontSize: 7.5, color: [100, 110, 155]
      });

      const safeMode = modeName.replace(/\s+/g, "_").replace(/[^a-z0-9_]/gi, "");
      const dateStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
      doc.save(`zenith_ox_${safeMode}_${dateStr}.pdf`);
      showToast("PDF downloaded!", "success");
    } catch (err) {
      showToast(`PDF error: ${err.message}`, "error");
    }
  }

  function collectMessages() {
    const msgs = [];
    chatBox.querySelectorAll(".message").forEach(m => {
      if (m.classList.contains("welcome") || m.classList.contains("error") || m.classList.contains("file-indicator") || m.classList.contains("thinking-trace")) return;
      const isUser = m.classList.contains("user");
      const content = m.querySelector(".md-content");
      const text = content ? content.textContent : m.textContent;
      msgs.push({ role: isUser ? "user" : "assistant", content: (text || "").trim() });
    });
    return msgs;
  }

  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(() => { toast.classList.add('toast--hide'); setTimeout(() => { toast.remove(); }, 400); }, 5000);
  }
  window.showToast = showToast;

  codeInput && codeInput.addEventListener("change", async () => {
    const file = codeInput.files[0];
    if (!file) return;
    addFileIndicator(file.name);
    const thinking = createThinkingTrace();
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("message", "Analyze and improve this code project");
      fd.append("model_key", currentModelKey());
      const r = await fetch("/upload-code", { method: "POST", body: fd });
      const data = await r.json();
      await thinking.finalize();
      if (!data.ok) {
        addMessage(`⚠ ${data.error || "Upload failed"}`, "bot error");
        return;
      }
      appendBotResponse(data.response, data.download_url, data.download_name);
    } catch (err) {
      thinking.remove();
      addMessage(`⚠ Upload error: ${err.message}`, "bot error");
    } finally {
      codeInput.value = "";
    }
  });

  wireAttachSheet();
  bootModelSelection();
  input.focus();
})();

/* ==========================================================
   MEMORY SIDEBAR
   ========================================================== */
(() => {
  const sidebar = document.getElementById("memorySidebar");
  const overlay = document.getElementById("sidebarOverlay");
  const memoryBtn = document.getElementById("memoryBtn");
  const closeBtn = document.getElementById("sidebarClose");
  const body = document.getElementById("sidebarBody");
  const emptyMsg = document.getElementById("sidebarEmpty");
  const AI_MODES = { researcher: { name: "Researcher", emoji: "🔍" }, developer: { name: "Developer", emoji: "💻" }, story_writer: { name: "Story Writer", emoji: "📖" }, solve_it: { name: "Solve It", emoji: "🧮" }, email_writer: { name: "Email Writer", emoji: "✉️" }, pptx_generator: { name: "Slides", emoji: "📊" } };
  let loaded = false;

  function open() {
    sidebar.classList.add("open");
    overlay.classList.add("active");
    document.body.classList.add("sidebar-open");
    if (!loaded) { load(); loaded = true; }
  }
  function close() {
    sidebar.classList.remove("open");
    overlay.classList.remove("active");
    document.body.classList.remove("sidebar-open");
  }

  if (memoryBtn) memoryBtn.addEventListener("click", open);
  if (closeBtn) closeBtn.addEventListener("click", close);
  if (overlay) overlay.addEventListener("click", close);

  async function load() {
    try {
      const res = await fetch("/memory-sidebar");
      const data = await res.json();
      if (!data.ok) return;
      const modes = data.modes || {};
      let total = 0;
      Object.values(modes).forEach(a => { total += a.length; });
      if (total === 0) {
        emptyMsg && (emptyMsg.style.display = "block");
        return;
      }
      if (emptyMsg) emptyMsg.style.display = "none";
      Object.entries(modes).forEach(([key, exchanges]) => {
        if (!exchanges || !exchanges.length) return;
        const meta = AI_MODES[key] || { name: key, emoji: "🤖" };
        const sec = document.createElement("div");
        sec.className = "sidebar-mode-section";
        const lbl = document.createElement("div");
        lbl.className = "sidebar-mode-label";
        lbl.innerHTML = `<span>${meta.emoji}</span> ${meta.name}`;
        sec.appendChild(lbl);
        exchanges.forEach(ex => {
          const item = document.createElement("div");
          item.className = "sidebar-chat-item";
          item.innerHTML = `<div class="sidebar-chat-user">${esc(ex.user)}</div><div class="sidebar-chat-bot">${esc(ex.assistant)}</div>`;
          sec.appendChild(item);
        });
        body.appendChild(sec);
      });
    } catch (e) {
      console.warn("Memory sidebar:", e);
    }
  }

  function esc(s) {
    return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  window.addEventListener("zenith:message-sent", () => {
    loaded = false;
    if (sidebar.classList.contains("open")) {
      body.innerHTML = "";
      if (emptyMsg) {
        emptyMsg.style.display = "block";
        body.appendChild(emptyMsg);
      }
      load();
      loaded = true;
    }
  });
})();

/* ==========================================================
   MOBILE SIDEBAR TOGGLE + ESCAPE HANDLING
   ========================================================== */
(() => {
  const sidebar = document.getElementById("zh-sidebar");
  const backdrop = document.getElementById("zh-backdrop");
  const toggle = document.getElementById("zh-sidebar-toggle");
  const attachSheet = document.getElementById("attachSheet");
  const attachSheetOverlay = document.getElementById("attachSheetOverlay");
  if (toggle && sidebar) {
    function openSidebar() { sidebar.classList.add("zh-open"); toggle.setAttribute("aria-expanded", "true"); backdrop.style.display = "block"; }
    function closeSidebar() { sidebar.classList.remove("zh-open"); toggle.setAttribute("aria-expanded", "false"); backdrop.style.display = "none"; }
    toggle.addEventListener("click", () => sidebar.classList.contains("zh-open") ? closeSidebar() : openSidebar());
    backdrop.addEventListener("click", closeSidebar);
  }

  document.addEventListener("keydown", e => {
    const isMeta = e.ctrlKey || e.metaKey;
    if (isMeta && e.key.toLowerCase() === "k") {
      const search = document.getElementById("zh-search-input");
      if (search) { e.preventDefault(); search.focus(); search.select(); }
      return;
    }
    if (e.key === "Escape") {
      const memorySidebar = document.getElementById("memorySidebar");
      const sidebarOverlay = document.getElementById("sidebarOverlay");
      if (memorySidebar && memorySidebar.classList.contains("open")) {
        memorySidebar.classList.remove("open");
        sidebarOverlay && sidebarOverlay.classList.remove("active");
        document.body.classList.remove("sidebar-open");
      }
      if (attachSheet && attachSheet.classList.contains("open")) {
        attachSheet.classList.remove("open");
        attachSheetOverlay && attachSheetOverlay.classList.remove("active");
      }
      const exportDropdown = document.getElementById("exportDropdown");
      if (exportDropdown) exportDropdown.classList.remove("show");
      if (sidebar && sidebar.classList.contains("zh-open")) {
        sidebar.classList.remove("zh-open");
        backdrop && (backdrop.style.display = "none");
        toggle && toggle.setAttribute("aria-expanded", "false");
      }
    }
  });
})();

/* ==========================================================
   SCROLL-TO-BOTTOM BUTTON
   ========================================================== */
(() => {
  // v2.7 — Fresh chat on every dashboard open (no last-chat memory restore)
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.removeItem("zenith_last_chat_restored");
  }

  const chatBox = document.getElementById("chat-box");
  const btn = document.getElementById("scrollToBottomBtn");
  if (!chatBox || !btn) return;
  const THRESHOLD = 80;
  function isNearBottom() {
    return chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight < THRESHOLD;
  }
  function update() {
    if (isNearBottom()) btn.classList.add("hidden");
    else btn.classList.remove("hidden");
  }
  chatBox.addEventListener("scroll", update);
  btn.addEventListener("click", () => { chatBox.scrollTo({ top: chatBox.scrollHeight, behavior: "smooth" }); });
  const observer = new MutationObserver(() => { if (isNearBottom()) btn.classList.add("hidden"); });
  observer.observe(chatBox, { childList: true, subtree: true, characterData: true });
  update();
})();
