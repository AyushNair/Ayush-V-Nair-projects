const $ = (selector) => document.querySelector(selector);
const content = $("#content");
const message = $("#message");
const resultCard = $("#result");
const scanButton = $("#scanButton");

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

function getPolicySettings() {
  return {
    policy: document.querySelector('input[name="policy"]:checked')?.value || "warn",
    enabled_detectors: [...document.querySelectorAll(".detector-toggle:checked")].map((el) => el.value),
    custom_keywords: $("#keywords").value.split(/\r?\n/).map((value) => value.trim()).filter(Boolean).slice(0, 50),
  };
}

function setMessage(text, kind = "") {
  message.textContent = text;
  message.className = `inline-message ${kind}`;
}

function setBusy(isBusy) {
  scanButton.disabled = isBusy;
  scanButton.querySelector("span").textContent = isBusy ? "SCANNING…" : "SCAN CONTENT";
}

function renderResult(data) {
  resultCard.hidden = false;
  resultCard.dataset.outcome = data.outcome;
  resultCard.replaceChildren();

  const head = document.createElement("div");
  head.className = "result-head";
  const title = document.createElement("strong");
  title.textContent = data.outcome;
  const total = document.createElement("span");
  total.textContent = `${data.finding_count} FINDING${data.finding_count === 1 ? "" : "S"}`;
  head.append(title, total);
  resultCard.append(head);

  if (data.findings.length) {
    const list = document.createElement("ul");
    list.className = "finding-list";
    for (const finding of data.findings) {
      const row = document.createElement("li");
      const details = document.createElement("div");
      const label = document.createElement("b");
      label.textContent = finding.type;
      const explanation = document.createElement("small");
      explanation.textContent = finding.explanation;
      details.append(label, explanation);
      row.append(details);
      list.append(row);
    }
    resultCard.append(list);
  } else {
    const success = document.createElement("p");
    success.textContent = "No enabled rules matched this content. It is ready to use.";
    resultCard.append(success);
  }

  if (data.sanitized_text !== null) {
    const label = document.createElement("div");
    label.className = "sanitized-label";
    label.textContent = "SANITIZED TEXT";
    const output = document.createElement("pre");
    output.className = "sanitized-text";
    output.textContent = data.sanitized_text;
    resultCard.append(label, output);
    content.value = data.sanitized_text;
    updateCount();
  } else if (data.outcome === "Blocked") {
    content.value = "";
    updateCount();
    const blocked = document.createElement("p");
    blocked.textContent = data.blocked_message;
    resultCard.append(blocked);
  }
}

function renderActivity(events) {
  const list = $("#activityList");
  list.replaceChildren();
  $("#logCount").textContent = String(events.length).padStart(2, "0");
  if (!events.length) {
    const empty = document.createElement("div");
    empty.className = "activity-empty";
    empty.textContent = "NO ACTIVITY YET.\nRUN A SCAN TO BEGIN.";
    list.append(empty);
    return;
  }
  for (const event of events.slice(0, 8)) {
    const card = document.createElement("article");
    card.className = "activity-item";
    card.dataset.outcome = event.outcome;
    const time = document.createElement("span");
    time.className = "activity-time";
    time.textContent = new Date(event.timestamp).toLocaleString();
    const policy = document.createElement("span");
    policy.className = "activity-policy";
    policy.textContent = event.policy;
    const outcome = document.createElement("b");
    outcome.className = "activity-outcome";
    outcome.textContent = `${event.outcome} · ${event.finding_count}`;
    const types = document.createElement("span");
    types.className = "activity-types";
    types.textContent = event.finding_types.length ? event.finding_types.join(" · ") : "No matches";
    card.append(time, policy, outcome, types);
    list.append(card);
  }
}

async function refreshAudit() {
  const [events, stats] = await Promise.all([api("/api/audit?limit=50"), api("/api/stats")]);
  renderActivity(events);
  $("#scanTotal").textContent = String(stats.scan_count).padStart(3, "0");
  $("#detectorTotal").textContent = String(stats.active_detectors).padStart(2, "0");
}

async function saveSettings({ quiet = false } = {}) {
  const settings = getPolicySettings();
  const saved = await api("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!quiet) setMessage("POLICY SETTINGS SAVED TO THIS DEVICE.", "settings-saved");
  return saved;
}

async function loadSettings() {
  const settings = await api("/api/settings");
  const policyInput = document.querySelector(`input[name="policy"][value="${settings.policy}"]`);
  if (policyInput) policyInput.checked = true;
  for (const checkbox of document.querySelectorAll(".detector-toggle")) {
    checkbox.checked = settings.enabled_detectors.includes(checkbox.value);
  }
  $("#keywords").value = settings.custom_keywords.join("\n");
  await refreshAudit();
}

function updateCount() {
  $("#charCount").textContent = `${content.value.length.toLocaleString()} / 1,000,000`;
}

async function scan() {
  setMessage("");
  resultCard.hidden = true;
  if (!$("#fileInput").files.length && !content.value.trim()) {
    setMessage("ADD TEXT OR CHOOSE A FILE BEFORE SCANNING.", "settings-error");
    content.focus();
    return;
  }
  setBusy(true);
  try {
    const settings = await saveSettings({ quiet: true });
    let data;
    const file = $("#fileInput").files[0];
    if (file) {
      const form = new FormData();
      form.append("file", file);
      data = await api("/api/scan-file", { method: "POST", body: form });
      $("#fileName").textContent = `${data.file_name} · SCANNED`;
      $("#fileInput").value = "";
    } else {
      data = await api("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: content.value, ...settings }),
      });
    }
    renderResult(data);
    setMessage(`SCAN COMPLETE · ${data.outcome.toUpperCase()}`);
    await refreshAudit();
  } catch (error) {
    setMessage(error.message.toUpperCase(), "settings-error");
  } finally {
    setBusy(false);
  }
}

$("#content").addEventListener("input", updateCount);
document.querySelectorAll(".detector-toggle").forEach((checkbox) => checkbox.addEventListener("change", () => {
  $("#detectorTotal").textContent = String(document.querySelectorAll(".detector-toggle:checked").length).padStart(2, "0");
}));
$("#fileInput").addEventListener("change", () => {
  const file = $("#fileInput").files[0];
  if (!file) return;
  $("#fileName").textContent = file.name;
  if (file.size > 1_000_000 || !file.name.toLowerCase().endsWith(".txt")) {
    setMessage("CHOOSE A .TXT FILE UNDER 1 MB.", "settings-error");
    $("#fileInput").value = "";
    $("#fileName").textContent = "PLAIN TEXT · MAX 1 MB";
  }
});
$("#saveSettings").addEventListener("click", async () => {
  try { await saveSettings(); }
  catch (error) { setMessage(error.message.toUpperCase(), "settings-error"); }
});
$("#scanButton").addEventListener("click", scan);
$("#loadSample").addEventListener("click", () => {
  content.value = "Hi, please send the customer update to priya.shah@example.com. Call me at (415) 555-0138.";
  $("#fileInput").value = "";
  $("#fileName").textContent = "SAMPLE TEXT LOADED";
  updateCount();
  content.focus();
});
$("#clearAudit").addEventListener("click", async () => {
  if (!confirm("Clear the saved audit events from this device?")) return;
  try {
    await api("/api/audit", { method: "DELETE" });
    await refreshAudit();
    setMessage("LOCAL AUDIT LOG CLEARED.", "settings-saved");
  } catch (error) { setMessage(error.message.toUpperCase(), "settings-error"); }
});

Promise.all([loadSettings(), api("/api/health")]).then(([, health]) => {
  $("#connectionText").textContent = "SYSTEM ONLINE";
  $(".connection").classList.add("online");
}).catch((error) => {
  $("#connectionText").textContent = "SYSTEM OFFLINE";
  $(".connection").classList.add("offline");
  setMessage(`BACKEND CONNECTION FAILED: ${error.message.toUpperCase()}`, "settings-error");
});
