const messagesEl = document.getElementById("messages");
const composerEl = document.getElementById("composer");
const inputEl = document.getElementById("query-input");
const sendBtn = document.getElementById("send-btn");
const suggestionsEl = document.getElementById("suggestions");
const statTickets = document.getElementById("stat-tickets");
const statDocs = document.getElementById("stat-docs");

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addUserMessage(text) {
  const msg = document.createElement("div");
  msg.className = "msg msg-user";
  msg.innerHTML = `
    <div class="msg-avatar user">You</div>
    <div class="msg-bubble">${escapeHtml(text)}</div>
  `;
  messagesEl.appendChild(msg);
  scrollToBottom();
}

function addTypingIndicator() {
  const msg = document.createElement("div");
  msg.className = "msg msg-bot";
  msg.id = "typing-indicator";
  msg.innerHTML = `
    <div class="msg-avatar bot">IA</div>
    <div class="msg-bubble">
      <div class="typing"><span></span><span></span><span></span></div>
    </div>
  `;
  messagesEl.appendChild(msg);
  scrollToBottom();
}

function removeTypingIndicator() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

function addBotAnswer(data) {
  const msg = document.createElement("div");
  msg.className = "msg msg-bot";

  const confidenceClass = `confidence-${data.confidence}`;

  let sourcesHtml = "";
  if (data.sources && data.sources.length > 0) {
    sourcesHtml = `
      <div class="section-label">Sources</div>
      <div class="sources">
        ${data.sources.map(s => `
          <div class="source-card type-${s.type}">
            <div>
              <span class="source-key">${escapeHtml(s.key)}</span>
              <span class="source-title">${escapeHtml(s.title)}</span>
            </div>
            <span class="source-score">${s.status} · ${s.score}</span>
          </div>
        `).join("")}
      </div>
    `;
  }

  let stepsHtml = "";
  if (data.next_steps && data.next_steps.length > 0) {
    stepsHtml = `
      <div class="section-label">Suggested next steps</div>
      <ul class="next-steps">
        ${data.next_steps.map(s => `<li>${escapeHtml(s)}</li>`).join("")}
      </ul>
    `;
  }

  msg.innerHTML = `
    <div class="msg-avatar bot">IA</div>
    <div class="msg-bubble">
      <span class="confidence-tag ${confidenceClass}">${data.confidence} confidence</span>
      <div>${escapeHtml(data.summary)}</div>
      ${stepsHtml}
      ${sourcesHtml}
    </div>
  `;
  messagesEl.appendChild(msg);
  scrollToBottom();
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function sendQuery(query) {
  addUserMessage(query);
  inputEl.value = "";
  sendBtn.disabled = true;
  addTypingIndicator();

  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    removeTypingIndicator();
    addBotAnswer(data);
  } catch (err) {
    removeTypingIndicator();
    const msg = document.createElement("div");
    msg.className = "msg msg-bot";
    msg.innerHTML = `
      <div class="msg-avatar bot">IA</div>
      <div class="msg-bubble">Something went wrong reaching the assistant. Please try again.</div>
    `;
    messagesEl.appendChild(msg);
  } finally {
    sendBtn.disabled = false;
    scrollToBottom();
  }
}

composerEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const query = inputEl.value.trim();
  if (!query) return;
  sendQuery(query);
});

async function loadSuggestions() {
  try {
    const res = await fetch("/api/suggestions");
    const data = await res.json();
    suggestionsEl.innerHTML = "";
    data.suggestions.forEach(s => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "suggestion-chip";
      chip.innerHTML = `<span class="chip-category">${escapeHtml(s.category)}</span>${escapeHtml(s.question)}`;
      chip.addEventListener("click", () => sendQuery(s.question));
      suggestionsEl.appendChild(chip);
    });
  } catch (err) {
    suggestionsEl.innerHTML = `<div class="footer-note">Couldn't load suggestions.</div>`;
  }
}

async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    const data = await res.json();
    statTickets.textContent = data.ticket_count;
    statDocs.textContent = data.kb_doc_count;
  } catch (err) {
    statTickets.textContent = "—";
    statDocs.textContent = "—";
  }
}

loadSuggestions();
loadStats();
