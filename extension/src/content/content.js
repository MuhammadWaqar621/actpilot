function extractPageText() {
  const clone = document.body.cloneNode(true);
  clone.querySelectorAll("script, style, noscript, template").forEach((el) => el.remove());
  return clone.innerText.replace(/\n{3,}/g, "\n\n").trim();
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "GET_PAGE_DATA") return false;

  sendResponse({
    url: location.href,
    title: document.title,
    text: extractPageText(),
  });
  return true;
});
