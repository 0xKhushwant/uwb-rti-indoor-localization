const boardEl = document.querySelector("#boards");
const linkEl = document.querySelector("#links");
const badgeEl = document.querySelector("#recordingBadge");
const startBtn = document.querySelector("#startBtn");
const stopBtn = document.querySelector("#stopBtn");

function numberCell(value, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${Number(value).toFixed(2)}${suffix}`;
}

function ageCell(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${Number(value).toFixed(1)} s`;
}

async function postJson(url) {
  await fetch(url, { method: "POST" });
  await refresh();
}

function renderBoards(boards) {
  boardEl.innerHTML = boards.map((board) => {
    const online = board.online ? "online" : "";
    const label = board.online ? "Online" : "Offline";
    return `
      <article class="board ${online}">
        <div class="node">${board.node}</div>
        <div class="status">${label}</div>
        <div class="meta">RSSI: ${board.wifi_rssi ?? "-"}</div>
        <div class="meta">IP: ${board.ip || "-"}</div>
        <div class="meta">Age: ${ageCell(board.age)}</div>
      </article>
    `;
  }).join("");
}

function renderLinks(links) {
  linkEl.innerHTML = links.map((link) => `
    <tr>
      <td>${link.link}</td>
      <td>${numberCell(link.range, " m")}</td>
      <td>${numberCell(link.rx_power, " dBm")}</td>
      <td>${numberCell(link.fp_power, " dBm")}</td>
      <td>${ageCell(link.age)}</td>
    </tr>
  `).join("");
}

async function refresh() {
  const response = await fetch("/api/state", { cache: "no-store" });
  const state = await response.json();
  badgeEl.textContent = state.recording ? "Recording On" : "Recording Off";
  badgeEl.classList.toggle("stopped", !state.recording);
  renderBoards(state.boards);
  renderLinks(state.links);
}

startBtn.addEventListener("click", () => postJson("/api/record/start"));
stopBtn.addEventListener("click", () => postJson("/api/record/stop"));
refresh();
setInterval(refresh, 1000);

