/**
 * FraudShield — Real-time Dashboard App
 * WebSocket consumer + Chart.js live charts + metrics loader
 */
"use strict";

// ── Config ────────────────────────────────────────────────────────────
const API_BASE = "http://127.0.0.1:8001";
const WS_URL   = "ws://127.0.0.1:8001/ws";
const MAX_CHART_POINTS = 60;
const MAX_TABLE_ROWS   = 100;

// ── State ─────────────────────────────────────────────────────────────
let ws = null;
let fraudOnly = false;
let processedCount   = 0;
let fraudCount       = 0;
let latencySum       = 0;
let processedPerMin  = 0;
let lastMinuteCount  = 0;
let lastMinuteCheck  = Date.now();
let riskCounts = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 };
const txnBuffer = [];

// ── DOM refs ──────────────────────────────────────────────────────────
const statusPill  = document.getElementById("status-pill");
const statusText  = document.getElementById("status-text");
const valProcessed  = document.getElementById("val-processed");
const valFraud      = document.getElementById("val-fraud");
const valLatency    = document.getElementById("val-latency");
const valPrecision  = document.getElementById("val-precision");
const deltaProcessed = document.getElementById("delta-processed");
const deltaFraud    = document.getElementById("delta-fraud");
const deltaFP       = document.getElementById("delta-fp");
const txnTbody      = document.getElementById("txn-tbody");
const toastContainer = document.getElementById("toast-container");
const fraudOnlyToggle = document.getElementById("fraud-only-toggle");
const tpsSlider      = document.getElementById("tps-slider");
const tpsLabel       = document.getElementById("tps-label");
const btnClear       = document.getElementById("btn-clear");

// ════════════════════════════════════════════════════════════════════
// CHARTS
// ════════════════════════════════════════════════════════════════════

const chartDefaults = {
  animation: { duration: 300 },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: "rgba(12,16,34,0.95)",
      borderColor: "rgba(255,255,255,0.08)",
      borderWidth: 1,
      titleColor: "#94a3b8",
      bodyColor: "#f1f5f9",
      padding: 10,
    },
  },
  scales: {
    x: {
      grid: { color: "rgba(255,255,255,0.04)", drawBorder: false },
      ticks: { color: "#475569", maxTicksLimit: 8, font: { size: 10 } },
    },
    y: {
      grid: { color: "rgba(255,255,255,0.04)", drawBorder: false },
      ticks: { color: "#475569", font: { size: 10 } },
      beginAtZero: true,
    },
  },
};

// Fraud Rate Chart
const fraudRateCtx = document.getElementById("chart-fraud-rate").getContext("2d");
const fraudRateChart = new Chart(fraudRateCtx, {
  type: "line",
  data: {
    labels: [],
    datasets: [{
      label: "Fraud Rate %",
      data: [],
      borderColor: "#ef4444",
      backgroundColor: "rgba(239,68,68,0.08)",
      borderWidth: 2,
      pointRadius: 0,
      fill: true,
      tension: 0.4,
    }],
  },
  options: {
    ...chartDefaults,
    scales: {
      ...chartDefaults.scales,
      y: { ...chartDefaults.scales.y, max: 20, ticks: { ...chartDefaults.scales.y.ticks, callback: v => v + "%" } },
    },
    plugins: { ...chartDefaults.plugins, legend: { display: true, labels: { color: "#94a3b8", boxWidth: 10 } } },
  },
});

// Volume Chart
const volumeCtx = document.getElementById("chart-volume").getContext("2d");
const volumeChart = new Chart(volumeCtx, {
  type: "bar",
  data: {
    labels: [],
    datasets: [
      {
        label: "Legitimate",
        data: [],
        backgroundColor: "rgba(59,130,246,0.5)",
        borderColor: "#3b82f6",
        borderWidth: 1,
        borderRadius: 3,
      },
      {
        label: "Fraud",
        data: [],
        backgroundColor: "rgba(239,68,68,0.6)",
        borderColor: "#ef4444",
        borderWidth: 1,
        borderRadius: 3,
      },
    ],
  },
  options: {
    ...chartDefaults,
    scales: {
      ...chartDefaults.scales,
      x: { ...chartDefaults.scales.x, stacked: true },
      y: { ...chartDefaults.scales.y, stacked: true },
    },
    plugins: {
      ...chartDefaults.plugins,
      legend: { display: true, labels: { color: "#94a3b8", boxWidth: 10, font: { size: 11 } } },
    },
  },
});

// Donut Chart
const riskCtx = document.getElementById("chart-risk").getContext("2d");
const riskChart = new Chart(riskCtx, {
  type: "doughnut",
  data: {
    labels: ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    datasets: [{
      data: [1, 0, 0, 0],
      backgroundColor: ["rgba(16,185,129,0.8)", "rgba(245,158,11,0.8)", "rgba(239,68,68,0.7)", "rgba(239,68,68,1)"],
      borderColor: ["#10b981", "#f59e0b", "#ef4444", "#dc2626"],
      borderWidth: 1.5,
      hoverOffset: 6,
    }],
  },
  options: {
    cutout: "72%",
    plugins: {
      legend: { display: false },
      tooltip: chartDefaults.plugins.tooltip,
    },
    animation: { duration: 500 },
  },
});

// Render legend
const legendContainer = document.getElementById("risk-legend");
const RISK_COLORS = { LOW: "#10b981", MEDIUM: "#f59e0b", HIGH: "#ef4444", CRITICAL: "#dc2626" };
Object.entries(RISK_COLORS).forEach(([label, color]) => {
  const el = document.createElement("div");
  el.className = "legend-item";
  el.id = `legend-${label}`;
  el.innerHTML = `
    <span><span class="legend-dot" style="background:${color}"></span>${label}</span>
    <span id="legend-count-${label}" style="font-family:var(--font-mono);font-size:0.72rem;color:var(--text-muted)">0</span>
  `;
  legendContainer.appendChild(el);
});

// Rolling chart data buckets (5-second windows)
const chartBuckets = [];
let currentBucket = { ts: Date.now(), legit: 0, fraud: 0 };
const BUCKET_MS = 5000;

function flushBucket() {
  const label = new Date(currentBucket.ts).toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const total = currentBucket.legit + currentBucket.fraud;
  const fraudRate = total > 0 ? (currentBucket.fraud / total * 100).toFixed(1) : 0;

  chartBuckets.push({ label, legit: currentBucket.legit, fraud: currentBucket.fraud, fraudRate });
  if (chartBuckets.length > MAX_CHART_POINTS) chartBuckets.shift();

  fraudRateChart.data.labels = chartBuckets.map(b => b.label);
  fraudRateChart.data.datasets[0].data = chartBuckets.map(b => b.fraudRate);
  fraudRateChart.update("none");

  volumeChart.data.labels = chartBuckets.map(b => b.label);
  volumeChart.data.datasets[0].data = chartBuckets.map(b => b.legit);
  volumeChart.data.datasets[1].data = chartBuckets.map(b => b.fraud);
  volumeChart.update("none");

  currentBucket = { ts: Date.now(), legit: 0, fraud: 0 };
}

setInterval(flushBucket, BUCKET_MS);

// ════════════════════════════════════════════════════════════════════
// WEBSOCKET
// ════════════════════════════════════════════════════════════════════
function connect() {
  try {
    ws = new WebSocket(WS_URL);
  } catch (e) {
    setStatus("error", "Cannot connect");
    setTimeout(connect, 5000);
    return;
  }

  ws.onopen = () => {
    setStatus("connected", "Live Stream Active");
    loadMetrics();
    loadFeatureImportance();
  };

  ws.onmessage = (ev) => {
    try {
      const txn = JSON.parse(ev.data);
      handleTransaction(txn);
    } catch (_) {}
  };

  ws.onclose = () => {
    setStatus("error", "Reconnecting...");
    setTimeout(connect, 3000);
  };

  ws.onerror = () => {
    setStatus("error", "Connection error");
  };
}

function setStatus(cls, text) {
  statusPill.className = "status-pill " + cls;
  statusText.textContent = text;
}

// ════════════════════════════════════════════════════════════════════
// TRANSACTION HANDLER
// ════════════════════════════════════════════════════════════════════
function handleTransaction(txn) {
  processedCount++;
  const isFraud = txn.is_fraud === 1 || txn.is_fraud === true;
  if (isFraud) fraudCount++;

  const lat = txn.detection_latency_ms || 0;
  latencySum += lat;

  // Update bucket
  if (isFraud) currentBucket.fraud++;
  else currentBucket.legit++;

  // Risk distribution
  const risk = (txn.risk_level || "LOW").toUpperCase();
  riskCounts[risk] = (riskCounts[risk] || 0) + 1;
  updateDonut();

  // KPI values
  valProcessed.textContent = processedCount.toLocaleString();
  valFraud.textContent = fraudCount.toLocaleString();
  const fraudRate = (fraudCount / processedCount * 100).toFixed(2);
  deltaFraud.textContent = `${fraudRate}% fraud rate`;
  valLatency.textContent = `${(latencySum / processedCount).toFixed(1)} ms`;

  // Per-minute rate
  const now = Date.now();
  if (now - lastMinuteCheck >= 60000) {
    processedPerMin = processedCount - lastMinuteCount;
    lastMinuteCount = processedCount;
    lastMinuteCheck = now;
  }
  deltaProcessed.textContent = `~${processedPerMin} /min`;

  // Table
  if (!fraudOnly || isFraud) {
    prependTableRow(txn, isFraud, risk);
  }

  // Toast on critical fraud
  if (isFraud && (risk === "CRITICAL" || risk === "HIGH")) {
    showFraudToast(txn);
  }
}

function updateDonut() {
  riskChart.data.datasets[0].data = [
    riskCounts.LOW || 0,
    riskCounts.MEDIUM || 0,
    riskCounts.HIGH || 0,
    riskCounts.CRITICAL || 0,
  ];
  riskChart.update("none");
  Object.keys(riskCounts).forEach(k => {
    const el = document.getElementById(`legend-count-${k}`);
    if (el) el.textContent = (riskCounts[k] || 0).toLocaleString();
  });
}

// ── Table ──────────────────────────────────────────────────────────
function prependTableRow(txn, isFraud, risk) {
  const prob = txn.fraud_probability ?? 0;
  const probPct = (prob * 100).toFixed(1);
  const fillClass = prob >= 0.7 ? "critical" : prob >= 0.45 ? "high" : "";
  const probStyle = `width:${probPct}%`;

  const tr = document.createElement("tr");
  tr.className = isFraud ? "row--fraud" : "";
  tr.innerHTML = `
    <td><span class="risk-badge risk--${risk.toLowerCase()}">${risk}</span></td>
    <td style="font-family:var(--font-mono);font-size:0.7rem;color:var(--text-muted)">${(txn.transaction_id || "").slice(0, 13)}…</td>
    <td style="font-family:var(--font-mono);color:var(--text-primary)">$${Number(txn.amount || 0).toFixed(2)}</td>
    <td>${txn.merchant_category || "—"}</td>
    <td><span style="font-family:var(--font-mono);font-size:0.7rem">${txn.country || "US"}</span></td>
    <td>
      <div class="prob-bar">
        <div class="prob-track"><div class="prob-fill ${fillClass}" style="${probStyle}"></div></div>
        <span style="font-family:var(--font-mono);font-size:0.68rem">${probPct}%</span>
      </div>
    </td>
    <td style="font-family:var(--font-mono);font-size:0.7rem;color:var(--accent-cyan)">${txn.detection_latency_ms != null ? txn.detection_latency_ms + "ms" : "—"}</td>
    <td style="font-size:0.68rem;color:var(--text-muted)">${new Date(txn.processed_at || Date.now()).toLocaleTimeString()}</td>
  `;

  txnTbody.insertBefore(tr, txnTbody.firstChild);
  while (txnTbody.children.length > MAX_TABLE_ROWS) {
    txnTbody.removeChild(txnTbody.lastChild);
  }
}

// ── Toast ──────────────────────────────────────────────────────────
const activeToasts = [];
function showFraudToast(txn) {
  if (activeToasts.length >= 4) {
    const old = activeToasts.shift();
    old.classList.add("removing");
    setTimeout(() => old.remove(), 300);
  }

  const t = document.createElement("div");
  t.className = "toast";
  t.innerHTML = `
    <div class="toast-header">
      <span class="toast-title">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="14"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        FRAUD ALERT — ${(txn.risk_level || "HIGH").toUpperCase()}
      </span>
    </div>
    <div class="toast-body">
      <div class="toast-amount">$${Number(txn.amount || 0).toFixed(2)}</div>
      <div>${txn.merchant_category || "Unknown"} · ${txn.country || "US"}</div>
      <div>Prob: ${((txn.fraud_probability || 0) * 100).toFixed(1)}% · ${txn.detection_latency_ms}ms</div>
    </div>
  `;
  toastContainer.appendChild(t);
  activeToasts.push(t);

  setTimeout(() => {
    t.classList.add("removing");
    setTimeout(() => { t.remove(); activeToasts.splice(activeToasts.indexOf(t), 1); }, 300);
  }, 5000);
}

// ════════════════════════════════════════════════════════════════════
// METRICS & FEATURE IMPORTANCE (from REST API)
// ════════════════════════════════════════════════════════════════════
async function loadMetrics() {
  try {
    const res = await fetch(`${API_BASE}/api/metrics`);
    if (!res.ok) return;
    const m = await res.json();
    if (m.error) return;

    document.getElementById("m-f1").textContent   = m.f1_score ?? "—";
    document.getElementById("m-auc").textContent  = m.roc_auc ?? "—";
    document.getElementById("m-prec").textContent = m.precision ?? "—";
    document.getElementById("m-rec").textContent  = m.recall ?? "—";
    document.getElementById("m-spec").textContent = m.specificity ?? "—";
    document.getElementById("m-fpr").textContent  = m.fp_reduction_vs_baseline_pct ? m.fp_reduction_vs_baseline_pct + "%" : "—";
    document.getElementById("m-tp").textContent   = (m.true_positives ?? "—").toLocaleString?.() ?? m.true_positives;
    document.getElementById("m-fp").textContent   = (m.false_positives ?? "—").toLocaleString?.() ?? m.false_positives;

    valPrecision.textContent = m.precision ? (m.precision * 100).toFixed(1) + "%" : "—";
    deltaFP.textContent      = m.roc_auc ? `ROC-AUC: ${m.roc_auc}` : "ROC-AUC: —";
  } catch (_) {}
}

async function loadFeatureImportance() {
  try {
    const res = await fetch(`${API_BASE}/api/feature_importance`);
    if (!res.ok) return;
    const data = await res.json();
    const entries = Object.entries(data).slice(0, 10);
    if (!entries.length) return;

    const container = document.getElementById("feature-bars");
    container.innerHTML = "";
    const max = entries[0][1];

    entries.forEach(([feat, imp]) => {
      const pct = ((imp / max) * 100).toFixed(1);
      const div = document.createElement("div");
      div.className = "feature-bar-item";
      div.innerHTML = `
        <div class="feature-bar-label">
          <span>${feat.replace(/_/g, " ")}</span>
          <span>${(imp * 100).toFixed(2)}%</span>
        </div>
        <div class="feature-bar-track">
          <div class="feature-bar-fill" style="width:${pct}%"></div>
        </div>
      `;
      container.appendChild(div);
    });
  } catch (_) {}
}

// ════════════════════════════════════════════════════════════════════
// UI CONTROLS
// ════════════════════════════════════════════════════════════════════
fraudOnlyToggle.addEventListener("change", () => {
  fraudOnly = fraudOnlyToggle.checked;
});

btnClear.addEventListener("click", () => {
  txnTbody.innerHTML = "";
});

tpsSlider.addEventListener("input", () => {
  const val = parseFloat(tpsSlider.value);
  tpsLabel.textContent = `${val} TPS`;
});

tpsSlider.addEventListener("change", async () => {
  const val = parseFloat(tpsSlider.value);
  try {
    await fetch(`${API_BASE}/api/pipeline/speed?tps=${val}`, { method: "POST" });
  } catch (_) {}
});

// ════════════════════════════════════════════════════════════════════
// BOOT
// ════════════════════════════════════════════════════════════════════
connect();

// Reload metrics every 30s (in case training completes mid-session)
setInterval(loadMetrics, 30_000);
setInterval(loadFeatureImportance, 60_000);
