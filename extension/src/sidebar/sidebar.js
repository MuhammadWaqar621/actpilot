const BACKEND_URL = "http://localhost:8000";

const REDO_MODIFIERS = {
  retry: null,
  shorter: "Answer again, but make the response noticeably shorter and more concise.",
  longer: "Answer again, but make the response more detailed and thorough.",
};

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chatForm");
const questionEl = document.getElementById("question");
const sendBtn = document.getElementById("sendBtn");

let history = [];

function addMessage(role, text) {
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

function attachActions(bubble, exchange) {
  const actions = document.createElement("div");
  actions.className = "msg-actions";

  const copyBtn = document.createElement("button");
  copyBtn.className = "action-btn";
  copyBtn.textContent = "Copy";
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(exchange.textEl.textContent);
      copyBtn.textContent = "Copied";
    } catch {
      copyBtn.textContent = "Couldn't copy";
    }
    setTimeout(() => (copyBtn.textContent = "Copy"), 1200);
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
  actions.appendChild(copyBtn);
  actions.appendChild(redoWrap);
  bubble.el.appendChild(actions);
}

document.addEventListener("click", closeAllRedoMenus);

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
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

async function askBackend(question, historyForContext) {
  const tab = await getActiveTab();
  if (!tab?.id) throw new Error("No active tab found.");

  const [pageData, screenshot] = await Promise.all([getPageData(tab.id), getScreenshot()]);

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
      },
      history: historyForContext,
    }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }

  const data = await res.json();
  return data.answer;
}

async function regenerate(exchange, mode) {
  const modifier = REDO_MODIFIERS[mode];
  const question = modifier ? `${exchange.question}\n\n(${modifier})` : exchange.question;

  const previousText = exchange.textEl.textContent;
  exchange.textEl.textContent = "Thinking…";

  try {
    const answer = await askBackend(question, history.slice(0, exchange.historyIndex - 1));
    exchange.textEl.textContent = answer;
    history[exchange.historyIndex] = { role: "assistant", text: answer };
  } catch (err) {
    exchange.textEl.textContent = previousText;
    alert(`Couldn't regenerate: ${err.message}`);
  }
}

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
    const answer = await askBackend(question, history);
    pending.textEl.textContent = answer;

    history.push({ role: "user", text: question });
    history.push({ role: "assistant", text: answer });

    attachActions(pending, { question, textEl: pending.textEl, historyIndex: history.length - 1 });
  } catch (err) {
    pending.el.className = "msg error";
    pending.textEl.textContent = `Error: ${err.message}`;
  } finally {
    sendBtn.disabled = false;
  }
});
