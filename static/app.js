// app.js
// Talks to the Flask API (/api/universe, /api/generate) and renders the
// stock picker, weighting controls, and the resulting index chart.

let universeData = [];
let availableRange = null;
let chart = null;

const el = (id) => document.getElementById(id);

async function loadUniverse() {
  const res = await fetch("/api/universe");
  const data = await res.json();
  universeData = data.stocks;
  availableRange = data.date_range;

  el("startDate").min = availableRange.start;
  el("startDate").max = availableRange.end;
  el("endDate").min = availableRange.start;
  el("endDate").max = availableRange.end;
  el("startDate").value = availableRange.start;
  el("endDate").value = availableRange.end;
  el("availableRange").textContent =
    `Data available from ${availableRange.start} to ${availableRange.end}.`;

  renderUniverseList(universeData);
}

function renderUniverseList(stocks) {
  const container = el("universeList");
  container.innerHTML = "";
  stocks.forEach((s) => {
    const row = document.createElement("label");
    row.className = "universe-row";
    row.innerHTML = `
      <input type="checkbox" value="${s.ticker}" class="stock-checkbox" />
      <span class="ticker">${s.ticker}</span>
      <span class="name">${s.company_name}</span>
      <span class="sector">${s.sector}</span>
    `;
    container.appendChild(row);
  });
  container.querySelectorAll(".stock-checkbox").forEach((cb) => {
    cb.addEventListener("change", onSelectionChange);
  });
}

function selectedTickers() {
  return Array.from(document.querySelectorAll(".stock-checkbox:checked")).map((cb) => cb.value);
}

function onSelectionChange() {
  const method = document.querySelector('input[name="weighting"]:checked').value;
  if (method === "custom") renderCustomWeightInputs();
}

function renderCustomWeightInputs() {
  const wrap = el("customWeights");
  const tickers = selectedTickers();
  if (tickers.length === 0) {
    wrap.innerHTML = `<p class="hint">Select stocks above to set custom weights.</p>`;
    return;
  }
  const even = (1 / tickers.length).toFixed(3);
  wrap.innerHTML = tickers
    .map(
      (t) => `
      <div class="custom-weight-row">
        <span>${t}</span>
        <input type="number" step="0.01" min="0" class="custom-weight-input" data-ticker="${t}" value="${even}" />
      </div>`
    )
    .join("");
}

function customWeightsFromInputs() {
  const inputs = document.querySelectorAll(".custom-weight-input");
  const weights = {};
  inputs.forEach((i) => (weights[i.dataset.ticker] = parseFloat(i.value) || 0));
  return weights;
}

document.querySelectorAll('input[name="weighting"]').forEach((radio) => {
  radio.addEventListener("change", (e) => {
    const custom = e.target.value === "custom";
    el("customWeights").classList.toggle("hidden", !custom);
    if (custom) renderCustomWeightInputs();
  });
});

el("search").addEventListener("input", (e) => {
  const q = e.target.value.trim().toLowerCase();
  const checked = new Set(selectedTickers());
  const filtered = universeData.filter(
    (s) =>
      s.ticker.toLowerCase().includes(q) ||
      s.company_name.toLowerCase().includes(q) ||
      s.sector.toLowerCase().includes(q)
  );
  renderUniverseList(filtered);
  // Re-apply previously checked boxes that are still visible.
  document.querySelectorAll(".stock-checkbox").forEach((cb) => {
    if (checked.has(cb.value)) cb.checked = true;
  });
});

el("selectAllBtn").addEventListener("click", () => {
  document.querySelectorAll(".stock-checkbox").forEach((cb) => (cb.checked = true));
  onSelectionChange();
});
el("clearAllBtn").addEventListener("click", () => {
  document.querySelectorAll(".stock-checkbox").forEach((cb) => (cb.checked = false));
  onSelectionChange();
});

function showError(msg) {
  const box = el("errorBox");
  box.textContent = msg;
  box.classList.remove("hidden");
}
function hideError() {
  el("errorBox").classList.add("hidden");
}
function showWarnings(warnings) {
  const box = el("warningBox");
  if (!warnings || warnings.length === 0) {
    box.classList.add("hidden");
    return;
  }
  box.textContent = warnings.join("\n");
  box.classList.remove("hidden");
}

async function generateIndex() {
  hideError();
  const tickers = selectedTickers();
  const method = document.querySelector('input[name="weighting"]:checked').value;
  const payload = {
    tickers,
    weighting_method: method,
    start_date: el("startDate").value,
    end_date: el("endDate").value,
  };
  if (method === "custom") payload.custom_weights = customWeightsFromInputs();

  el("generateBtn").disabled = true;
  el("generateBtn").textContent = "Generating...";
  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      showError(data.error || "Something went wrong.");
      return;
    }
    showWarnings(data.warnings);
    renderChart(data.dates, data.levels);
    renderSummary(data.summary);
    renderWeightsTable(data.weights);
  } catch (err) {
    showError("Failed to reach the server: " + err.message);
  } finally {
    el("generateBtn").disabled = false;
    el("generateBtn").textContent = "Generate";
  }
}

function renderChart(dates, levels) {
  const ctx = document.getElementById("indexChart").getContext("2d");
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: dates,
      datasets: [
        {
          label: "Custom Price Return Index (base 100)",
          data: levels,
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56, 189, 248, 0.15)",
          fill: true,
          pointRadius: 0,
          tension: 0.1,
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: { ticks: { maxTicksLimit: 10, color: "#94a3b8" }, grid: { color: "#334155" } },
        y: { ticks: { color: "#94a3b8" }, grid: { color: "#334155" } },
      },
      plugins: { legend: { labels: { color: "#e2e8f0" } } },
    },
  });
}

function renderSummary(summary) {
  el("summaryCards").classList.remove("hidden");
  el("cumReturn").textContent = (summary.cumulative_return * 100).toFixed(2) + "%";
  el("annReturn").textContent = (summary.annualized_return * 100).toFixed(2) + "%";
  el("annVol").textContent = (summary.annualized_volatility * 100).toFixed(2) + "%";
}

function renderWeightsTable(weights) {
  const wrap = el("weightsTableWrap");
  wrap.classList.remove("hidden");
  const tbody = document.querySelector("#weightsTable tbody");
  tbody.innerHTML = Object.entries(weights)
    .sort((a, b) => b[1] - a[1])
    .map(([ticker, w]) => `<tr><td>${ticker}</td><td>${(w * 100).toFixed(2)}%</td></tr>`)
    .join("");
}

el("generateBtn").addEventListener("click", generateIndex);

loadUniverse();
