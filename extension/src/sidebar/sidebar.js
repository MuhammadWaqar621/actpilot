const BACKEND_URL = "http://localhost:8000";
const FREE_MESSAGE_LIMIT = 50;

const REDO_MODIFIERS = {
  retry: null,
  shorter: "Answer again, but make the response noticeably shorter and more concise.",
  longer: "Answer again, but make the response more detailed and thorough.",
};

const messagesEl = document.getElementById("messages");
const suggestionsEl = document.getElementById("suggestions");
const pageContextEl = document.getElementById("pageContext");
const formEl = document.getElementById("chatForm");
const questionEl = document.getElementById("question");
const sendBtn = document.getElementById("sendBtn");
const downloadBtn = document.getElementById("downloadBtn");
const logoEl = document.getElementById("logo");

let history = [];

// Swap the wordmark to match the browser/OS theme, same as the rest of the
// UI (which follows prefers-color-scheme via CSS custom properties).
const darkModeQuery = window.matchMedia("(prefers-color-scheme: dark)");
function updateLogo() {
  logoEl.src = darkModeQuery.matches ? "../icons/actpilot-logo-dark.svg" : "../icons/actpilot-logo-light.svg";
}
updateLogo();
darkModeQuery.addEventListener("change", updateLogo);

function truncate(text, max) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

// Keeps a persistent "Reading: <page title>" indicator so it's always
// obvious which page's content ActPilot is using as context.
async function updatePageContextBanner() {
  updateLogo(); // opportunistic re-check - a side panel often gets reopened
  // rather than staying open across a real theme change, so re-syncing here
  // (a natural "wake" point) is a cheap backstop alongside the change listener.
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.title) {
      pageContextEl.textContent = `Reading: ${truncate(tab.title, 60)}`;
      pageContextEl.hidden = false;
    } else {
      pageContextEl.hidden = true;
    }
  } catch {
    pageContextEl.hidden = true;
  }
}

updatePageContextBanner();
chrome.tabs.onActivated.addListener(updatePageContextBanner);
chrome.tabs.onUpdated.addListener((_tabId, changeInfo) => {
  if (changeInfo.title || changeInfo.status === "complete") updatePageContextBanner();
});

// --- Minimal, safe markdown rendering (bold/italic/code/lists/paragraphs) --
// Builds real DOM nodes via createElement/textContent only - never innerHTML
// with model output, since that text ultimately derives from page content
// the LLM reads and could otherwise be an XSS vector.

function appendInline(parent, text) {
  const regex = /\*\*(.+?)\*\*|`(.+?)`|\*(.+?)\*/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parent.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
    }
    if (match[1] !== undefined) {
      const strong = document.createElement("strong");
      strong.textContent = match[1];
      parent.appendChild(strong);
    } else if (match[2] !== undefined) {
      const code = document.createElement("code");
      code.textContent = match[2];
      parent.appendChild(code);
    } else {
      const em = document.createElement("em");
      em.textContent = match[3];
      parent.appendChild(em);
    }
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    parent.appendChild(document.createTextNode(text.slice(lastIndex)));
  }
}

function renderMarkdown(container, text) {
  container.replaceChildren();
  const lines = text.split("\n");
  let listEl = null;

  for (const line of lines) {
    const bulletMatch = line.match(/^\s*[-*]\s+(.*)/);
    const numberedMatch = line.match(/^\s*\d+[.)]\s+(.*)/);

    if (bulletMatch || numberedMatch) {
      const tag = bulletMatch ? "ul" : "ol";
      if (!listEl || listEl.tagName.toLowerCase() !== tag) {
        listEl = document.createElement(tag);
        container.appendChild(listEl);
      }
      const li = document.createElement("li");
      appendInline(li, (bulletMatch || numberedMatch)[1]);
      listEl.appendChild(li);
      continue;
    }

    listEl = null;
    if (line.trim() === "") continue;

    const p = document.createElement("p");
    appendInline(p, line);
    container.appendChild(p);
  }
}

function addMessage(role, text) {
  suggestionsEl.hidden = true;
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  const textEl = document.createElement("div");
  textEl.className = "msg-text";
  textEl.textContent = text;
  el.appendChild(textEl);
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return { el, textEl };
}

function closeAllRedoMenus() {
  document.querySelectorAll(".redo-menu.open").forEach((menu) => menu.classList.remove("open"));
}

const COPY_ICON =
  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
const CHECK_ICON =
  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';

function attachMessageActions(bubble, exchange) {
  const actions = document.createElement("div");
  actions.className = "msg-actions";

  const copyBtn = document.createElement("button");
  copyBtn.className = "action-btn icon-btn";
  copyBtn.title = "Copy";
  copyBtn.innerHTML = COPY_ICON;
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(exchange.rawText);
      copyBtn.innerHTML = CHECK_ICON;
      copyBtn.title = "Copied";
    } catch {
      copyBtn.title = "Couldn't copy";
    }
    setTimeout(() => {
      copyBtn.innerHTML = COPY_ICON;
      copyBtn.title = "Copy";
    }, 1200);
  });

  const redoWrap = document.createElement("div");
  redoWrap.className = "redo-wrap";

  const redoBtn = document.createElement("button");
  redoBtn.className = "action-btn";
  redoBtn.textContent = "Redo ▾";

  const redoMenu = document.createElement("div");
  redoMenu.className = "redo-menu";
  [
    ["retry", "Try again"],
    ["shorter", "Shorter"],
    ["longer", "Longer"],
  ].forEach(([mode, label]) => {
    const item = document.createElement("button");
    item.textContent = label;
    item.addEventListener("click", () => {
      redoMenu.classList.remove("open");
      regenerate(exchange, mode);
    });
    redoMenu.appendChild(item);
  });

  redoBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    const willOpen = !redoMenu.classList.contains("open");
    closeAllRedoMenus();
    redoMenu.classList.toggle("open", willOpen);
  });

  redoWrap.appendChild(redoBtn);
  redoWrap.appendChild(redoMenu);
  actions.appendChild(redoWrap);
  actions.appendChild(copyBtn);
  bubble.el.appendChild(actions);
}

document.addEventListener("click", closeAllRedoMenus);

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

function withTimeout(promise, ms, fallback) {
  return Promise.race([
    promise,
    new Promise((resolve) => setTimeout(() => resolve(fallback), ms)),
  ]);
}

async function getPageData(tabId) {
  try {
    return await chrome.tabs.sendMessage(tabId, { type: "GET_PAGE_DATA" });
  } catch {
    // No content script listening yet - happens on tabs that were already
    // open before the extension loaded. Inject it now and retry once.
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["src/content/content.js"],
      });
      return await chrome.tabs.sendMessage(tabId, { type: "GET_PAGE_DATA" });
    } catch {
      return null;
    }
  }
}

async function getScreenshot() {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "CAPTURE_SCREENSHOT" }, (response) => {
      resolve(response?.ok ? response.dataUrl : null);
    });
  });
}

// Runs each returned action against the real page. "fill"/"click" target
// elements by the data-actpilot-id the content script assigned during
// extraction - never a raw selector the model made up.
async function executeActions(tabId, actions) {
  const done = [];
  for (const action of actions) {
    try {
      if (action.type === "open_url") {
        await chrome.tabs.create({ url: action.url, active: false });
        done.push("Opened a new tab");
      } else if (action.type === "fill") {
        await chrome.scripting.executeScript({
          target: { tabId },
          func: (id, value) => {
            const el = document.querySelector(`[data-actpilot-id="${id}"]`);
            if (!el) return false;
            el.focus();
            el.value = value;
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
            return true;
          },
          args: [action.id, action.value],
        });
        done.push("Filled a field");
      } else if (action.type === "click") {
        await chrome.scripting.executeScript({
          target: { tabId },
          func: (id) => {
            const el = document.querySelector(`[data-actpilot-id="${id}"]`);
            if (!el) return false;
            el.click();
            return true;
          },
          args: [action.id],
        });
        done.push("Clicked an element");
      }
    } catch {
      // Element may have disappeared/re-rendered since extraction - skip it.
    }
  }
  return done;
}

async function askBackend(question, historyForContext) {
  const tab = await getActiveTab();
  if (!tab?.id) throw new Error("No active tab found.");

  const [pageData, screenshot] = await Promise.all([
    withTimeout(getPageData(tab.id), 8000, null),
    withTimeout(getScreenshot(), 8000, null),
  ]);

  const res = await fetch(`${BACKEND_URL}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      page: {
        url: pageData?.url || tab.url || "",
        title: pageData?.title || tab.title || "",
        text: pageData?.text || "",
        screenshot,
        elements: pageData?.elements || [],
      },
      history: historyForContext,
    }),
  });

  if (res.status === 429) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail?.message || "Free limit reached.");
    err.isRateLimit = true;
    err.resetInSeconds = body.detail?.reset_in_seconds ?? null;
    throw err;
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }

  const data = await res.json();

  let actionsSummary = [];
  if (data.actions?.length) {
    actionsSummary = await executeActions(tab.id, data.actions);
  }

  return { answer: data.answer, actionsSummary };
}

// --- Free-tier message cap ------------------------------------------------
// Enforced server-side (see backend/app/core/rate_limit.py), keyed by
// client IP with a rolling 2-hour window - not just client storage, so it
// can't be reset by clearing the extension's local data.

function formatResetTime(seconds) {
  if (seconds == null) return "";
  const mins = Math.max(1, Math.round(seconds / 60));
  if (mins < 60) return `Try again in about ${mins} minute${mins === 1 ? "" : "s"}.`;
  const hours = Math.round(mins / 60);
  return `Try again in about ${hours} hour${hours === 1 ? "" : "s"}.`;
}

function showUpgradePrompt(resetInSeconds) {
  const { el } = addMessage("assistant", "");
  el.classList.add("upgrade");
  const textEl = el.querySelector(".msg-text");

  const p = document.createElement("p");
  p.textContent = `You've reached the free limit of ${FREE_MESSAGE_LIMIT} messages. ${formatResetTime(resetInSeconds)}`;
  textEl.appendChild(p);

  const upgradeBtn = document.createElement("button");
  upgradeBtn.className = "action-btn upgrade-btn";
  upgradeBtn.textContent = "Upgrade";
  upgradeBtn.addEventListener("click", () => {
    alert("Upgrades aren't available yet - check back soon.");
  });
  textEl.appendChild(upgradeBtn);
}

async function regenerate(exchange, mode) {
  const modifier = REDO_MODIFIERS[mode];
  const question = modifier ? `${exchange.question}\n\n(${modifier})` : exchange.question;

  const previousText = exchange.rawText;
  exchange.textEl.textContent = "Thinking…";

  try {
    const { answer } = await askBackend(question, history.slice(0, exchange.historyIndex - 1));
    renderMarkdown(exchange.textEl, answer);
    exchange.rawText = answer;
    history[exchange.historyIndex] = { role: "assistant", text: answer };
  } catch (err) {
    renderMarkdown(exchange.textEl, previousText);
    if (err.isRateLimit) {
      showUpgradePrompt(err.resetInSeconds);
    } else {
      alert(`Couldn't regenerate: ${err.message}`);
    }
  }
}

function fillAndSend(text) {
  questionEl.value = text;
  formEl.requestSubmit();
}

suggestionsEl.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => fillAndSend(chip.textContent));
});

downloadBtn.addEventListener("click", async () => {
  if (history.length === 0) return;
  downloadBtn.disabled = true;
  downloadBtn.textContent = "…";
  try {
    const tab = await getActiveTab();
    const res = await fetch(`${BACKEND_URL}/api/export-chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history, page_title: tab?.title || "" }),
    });
    if (!res.ok) throw new Error(`Request failed (${res.status})`);

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `actpilot-chat-${Date.now()}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Couldn't download the chat: ${err.message}`);
  } finally {
    downloadBtn.disabled = false;
    downloadBtn.textContent = "Download";
  }
});

questionEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    formEl.requestSubmit();
  }
});

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionEl.value.trim();
  if (!question) return;

  addMessage("user", question);
  questionEl.value = "";
  sendBtn.disabled = true;
  const pending = addMessage("assistant", "Thinking…");

  try {
    const { answer, actionsSummary } = await askBackend(question, history);
    renderMarkdown(pending.textEl, answer);
    if (actionsSummary.length) {
      const note = document.createElement("p");
      note.className = "action-note";
      note.textContent = `✓ ${actionsSummary.join(", ")}`;
      pending.textEl.appendChild(note);
    }

    history.push({ role: "user", text: question });
    history.push({ role: "assistant", text: answer });

    attachMessageActions(pending, {
      question,
      textEl: pending.textEl,
      rawText: answer,
      historyIndex: history.length - 1,
    });
  } catch (err) {
    if (err.isRateLimit) {
      pending.el.remove();
      showUpgradePrompt(err.resetInSeconds);
    } else {
      pending.el.className = "msg error";
      pending.textEl.textContent = `Error: ${err.message}`;
    }
  } finally {
    sendBtn.disabled = false;
  }
});
