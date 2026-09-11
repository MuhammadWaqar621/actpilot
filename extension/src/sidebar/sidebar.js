const DEFAULT_BACKEND_URL = "http://localhost:8000";

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chatForm");
const questionEl = document.getElementById("question");
const sendBtn = document.getElementById("sendBtn");
const settingsToggle = document.getElementById("settingsToggle");
const settingsPanel = document.getElementById("settingsPanel");
const backendUrlInput = document.getElementById("backendUrl");
const saveSettingsBtn = document.getElementById("saveSettings");

let history = [];

async function getBackendUrl() {
  const { backendUrl } = await chrome.storage.sync.get("backendUrl");
  return backendUrl || DEFAULT_BACKEND_URL;
}

settingsToggle.addEventListener("click", async () => {
  backendUrlInput.value = await getBackendUrl();
  settingsPanel.hidden = !settingsPanel.hidden;
});

saveSettingsBtn.addEventListener("click", async () => {
  await chrome.storage.sync.set({ backendUrl: backendUrlInput.value.trim() });
  settingsPanel.hidden = true;
});

function addMessage(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.textContent = text;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function getPageData(tabId) {
  try {
    return await chrome.tabs.sendMessage(tabId, { type: "GET_PAGE_DATA" });
  } catch {
    return null;
  }
}

async function getScreenshot() {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "CAPTURE_SCREENSHOT" }, (response) => {
      resolve(response?.ok ? response.dataUrl : null);
    });
  });
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionEl.value.trim();
  if (!question) return;

  addMessage("user", question);
  questionEl.value = "";
  sendBtn.disabled = true;
  const pending = addMessage("assistant", "Thinking…");

  try {
    const tab = await getActiveTab();
    if (!tab?.id) throw new Error("No active tab found.");

    const [pageData, screenshot] = await Promise.all([getPageData(tab.id), getScreenshot()]);

    const backendUrl = await getBackendUrl();
    const res = await fetch(`${backendUrl}/api/analyze`, {
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
        history,
      }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }

    const data = await res.json();
    pending.textContent = data.answer;
    history.push({ role: "user", text: question });
    history.push({ role: "assistant", text: data.answer });
  } catch (err) {
    pending.className = "msg error";
    pending.textContent = `Error: ${err.message}`;
  } finally {
    sendBtn.disabled = false;
  }
});
