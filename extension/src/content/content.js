function extractPageText() {
  const clone = document.body.cloneNode(true);
  clone.querySelectorAll("script, style, noscript, template").forEach((el) => el.remove());
  return clone.innerText.replace(/\n{3,}/g, "\n\n").trim();
}

function isVisible(el) {
  const rect = el.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return false;
  const style = getComputedStyle(el);
  return style.visibility !== "hidden" && style.display !== "none";
}

function getAssociatedLabel(el) {
  if (el.id) {
    const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
    if (label?.innerText.trim()) return label.innerText.trim();
  }
  const parentLabel = el.closest("label");
  if (parentLabel?.innerText.trim()) return parentLabel.innerText.trim();
  return null;
}

// Interactive elements the AI can fill/click. Each gets a stable
// data-actpilot-id attribute so actions can target them precisely,
// instead of asking the model to guess a CSS selector.
function extractInteractiveElements() {
  const nodes = Array.from(
    document.querySelectorAll("input, textarea, select, button, a[href], [role='button']")
  )
    .filter(isVisible)
    .slice(0, 80);

  return nodes.map((el, index) => {
    if (!el.dataset.actpilotId) el.dataset.actpilotId = String(index);
    const tag = el.tagName.toLowerCase();
    const isTextInput = tag === "input" || tag === "textarea";
    return {
      id: el.dataset.actpilotId,
      tag,
      type: el.type || null,
      name: el.name || null,
      placeholder: el.placeholder || null,
      label: getAssociatedLabel(el) || el.getAttribute("aria-label") || null,
      text: tag === "button" || tag === "a" ? el.innerText.trim().slice(0, 60) : null,
      value: isTextInput ? el.value : null,
    };
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "GET_PAGE_DATA") return false;

  sendResponse({
    url: location.href,
    title: document.title,
    text: extractPageText(),
    elements: extractInteractiveElements(),
  });
  return true;
});
