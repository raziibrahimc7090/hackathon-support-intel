// frontend/app.js — Ultra-Premium "Ela" Support Intelligence & Phishing Dashboard

const API_BASE = "http://localhost:8000";

// Chart instances
let sentimentChartInstance = null;
let categoryChartInstance = null;

// Application State
let dbConversations = [];
let filteredConversations = [];
let historyStats = { total: [], critical: [], threatRate: [], resolvedRate: [], sentimentScore: [] };
const HISTORY_CAP = 30;

// Preset Messages for Live Analyzer
const PRESETS = {
  phishing: "URGENT: Your account will be suspended in 24 hours. Verify your password immediately at http://paypa1-secure.com/verify or contact support at billing@paypa1-support.net",
  "ip-shortener": "Please confirm your card number at http://192.168.1.5/login or use this link bit.ly/3xJk9Q immediately.",
  billing: "Hi, I was charged twice for my subscription this month ($49 x 2). Could you please check order #8821 and refund the duplicate charge?",
  login: "I'm having trouble logging in after resetting my password. It keeps saying 'invalid credentials'. Can someone reset it from your side?"
};

// Category Colors & Styling
const CATEGORY_MAP = {
  Billing:    { color: "#7C5CFC", bg: "rgba(124, 92, 252, 0.15)", icon: "💳" },
  Login:      { color: "#3B82F6", bg: "rgba(59, 130, 246, 0.15)", icon: "🔑" },
  Delivery:   { color: "#F97316", bg: "rgba(249, 115, 22, 0.15)", icon: "📦" },
  Refund:     { color: "#10B981", bg: "rgba(16, 185, 129, 0.15)", icon: "💰" },
  Technical:  { color: "#06B6D4", bg: "rgba(6, 182, 212, 0.15)", icon: "🛠" },
  Security:   { color: "#EF4444", bg: "rgba(239, 68, 68, 0.15)", icon: "🛡" },
  Other:      { color: "#64748B", bg: "rgba(100, 116, 139, 0.15)", icon: "📝" },
};

// ---------- Utility Helpers ----------

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function timeShort(tsStr) {
  if (!tsStr) return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  try {
    return new Date(tsStr).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return tsStr;
  }
}

function riskToScore(level) {
  const map = { Low: 15, Medium: 45, High: 75, Critical: 95 };
  return map[level] ?? 10;
}

function severityChip(value) {
  const v = (value || "").toLowerCase();
  if (v === "critical") return `<span class="chip chip-critical">Critical</span>`;
  if (v === "high") return `<span class="chip chip-high">High</span>`;
  if (v === "medium") return `<span class="chip chip-medium">Medium</span>`;
  return `<span class="chip chip-low">Low</span>`;
}

function sentimentChip(value) {
  const v = (value || "").toLowerCase();
  if (v === "positive") return `<span class="chip chip-positive">Positive</span>`;
  if (v === "negative") return `<span class="chip chip-negative">Negative</span>`;
  return `<span class="chip chip-neutral">Neutral</span>`;
}

function categoryBadge(category) {
  const meta = CATEGORY_MAP[category] || CATEGORY_MAP.Other;
  return `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold" style="background:${meta.bg}; color:${meta.color}; border: 1px solid ${meta.color}40">${meta.icon} ${escapeHtml(category)}</span>`;
}

// ---------- Sparkline Generator ----------

function sparklineSvg(values, color) {
  if (!values || values.length < 2) {
    return `<svg class="w-full h-7" viewBox="0 0 100 28" preserveAspectRatio="none"></svg>`;
  }
  const w = 100, h = 28, pad = 2;
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || 1;
  const step = (w - pad * 2) / (values.length - 1);
  const pts = values.map((v, i) => {
    const x = pad + i * step;
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const [lastX, lastY] = pts[pts.length - 1].split(",");
  return `
    <svg class="w-full h-7" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
      <polyline points="${pts.join(" ")}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" opacity="0.9" />
      <circle cx="${lastX}" cy="${lastY}" r="2.5" fill="${color}" />
    </svg>`;
}

// ---------- Semicircle Gauge SVG ----------

function renderGaugeSvg(score) {
  const v = Math.max(0, Math.min(100, score ?? 0));
  const R = 85, CX = 100, CY = 95;
  const pt = (t) => [
    (CX - R * Math.cos(t * Math.PI / 180)).toFixed(1),
    (CY - R * Math.sin(t * Math.PI / 180)).toFixed(1),
  ];
  const [x0, y0] = pt(0);
  const [x40, y40] = pt(72);   // 0-40 -> Green
  const [x70, y70] = pt(126);  // 40-70 -> Orange
  const [x100, y100] = pt(180); // 70-100 -> Red

  const needleT = (v / 100) * 180;
  const nx = CX - 65 * Math.cos((needleT * Math.PI) / 180);
  const ny = CY - 65 * Math.sin((needleT * Math.PI) / 180);

  return `
    <svg viewBox="0 0 200 110" width="100%">
      <path d="M ${x0} ${y0} A ${R} ${R} 0 0 1 ${x40} ${y40}" stroke="#10B981" stroke-width="14" fill="none" stroke-linecap="round" />
      <path d="M ${x40} ${y40} A ${R} ${R} 0 0 1 ${x70} ${y70}" stroke="#F59E0B" stroke-width="14" fill="none" stroke-linecap="round" />
      <path d="M ${x70} ${y70} A ${R} ${R} 0 0 1 ${x100} ${y100}" stroke="#EF4444" stroke-width="14" fill="none" stroke-linecap="round" />
      <line x1="${CX}" y1="${CY}" x2="${nx.toFixed(1)}" y2="${ny.toFixed(1)}" stroke="#F1F5F9" stroke-width="3.5" stroke-linecap="round" />
      <circle cx="${CX}" cy="${CY}" r="6" fill="#F1F5F9" />
    </svg>`;
}

// ---------- Render Functions ----------

function renderStatCards(data) {
  const total = data.total_conversations ?? 0;
  const critical = data.critical_count ?? 0;
  const unresolved = data.unresolved_count ?? 0;
  const threats = data.threats_detected ?? 0;
  
  const threatRate = total > 0 ? +((threats / total) * 100).toFixed(1) : 0;
  const resolvedRate = total > 0 ? +(((total - unresolved) / total) * 100).toFixed(1) : 0;

  historyStats.total.push(total);
  historyStats.critical.push(critical);
  historyStats.threatRate.push(threatRate);
  historyStats.resolvedRate.push(resolvedRate);

  Object.values(historyStats).forEach(arr => { if (arr.length > HISTORY_CAP) arr.shift(); });

  document.getElementById("statTotalValue").textContent = total.toLocaleString();
  document.getElementById("statTotalSpark").innerHTML = sparklineSvg(historyStats.total, "#7C5CFC");

  document.getElementById("statThreatRateValue").textContent = threatRate + "%";
  document.getElementById("statThreatRateSpark").innerHTML = sparklineSvg(historyStats.threatRate, "#EF4444");

  document.getElementById("statCriticalValue").textContent = critical;
  document.getElementById("statCriticalSpark").innerHTML = sparklineSvg(historyStats.critical, "#F97316");

  document.getElementById("statResolvedRateValue").textContent = resolvedRate + "%";
  document.getElementById("statResolvedRateSpark").innerHTML = sparklineSvg(historyStats.resolvedRate, "#10B981");

  // Dominant sentiment calculation
  const sentimentDist = data.sentiment_distribution || { Positive: 0, Neutral: 0, Negative: 0 };
  const pos = sentimentDist.Positive || 0;
  const neg = sentimentDist.Negative || 0;
  const neu = sentimentDist.Neutral || 0;
  const score = total > 0 ? Math.round(50 + ((pos - neg) / total) * 50) : 50;

  let dominantLabel = "Neutral";
  let dominantColor = "#94A3B8";
  if (pos >= neg && pos >= neu) { dominantLabel = "Positive"; dominantColor = "#10B981"; }
  else if (neg >= pos && neg >= neu) { dominantLabel = "Negative"; dominantColor = "#EF4444"; }

  const sentEl = document.getElementById("heroSentimentValue");
  sentEl.textContent = dominantLabel;
  sentEl.style.color = dominantColor;
  document.getElementById("heroSentimentScore").textContent = `${score}/100`;

  historyStats.sentimentScore.push(score);
  if (historyStats.sentimentScore.length > HISTORY_CAP) historyStats.sentimentScore.shift();
  document.getElementById("heroSpark").innerHTML = sparklineSvg(historyStats.sentimentScore, "#3B82F6");

  // Nav alert badge
  const navBadge = document.getElementById("navAlertBadge");
  const threatCountBadge = document.getElementById("threatCountBadge");
  if (threats > 0) {
    navBadge.textContent = threats > 99 ? "99+" : threats;
    navBadge.classList.remove("hidden");
    if (threatCountBadge) threatCountBadge.textContent = `${threats} Threats Flagged`;
  } else {
    navBadge.classList.add("hidden");
  }
}

function renderGaugeAndRiskMetrics(data) {
  const total = data.total_conversations || 1;
  const threats = data.threats_detected || 0;
  const threatPct = Math.round((threats / total) * 100);

  // Compute average risk score from loaded database records
  let avgRiskScore = 15;
  if (dbConversations.length > 0) {
    const sum = dbConversations.reduce((acc, item) => acc + riskToScore(item.security?.risk_level), 0);
    avgRiskScore = Math.round(sum / dbConversations.length);
  }

  document.getElementById("riskGauge").innerHTML = renderGaugeSvg(avgRiskScore);
  
  const valEl = document.getElementById("gaugeValue");
  const capEl = document.getElementById("gaugeCaption");
  valEl.textContent = `${avgRiskScore}/100`;

  if (avgRiskScore < 35) {
    capEl.textContent = "Low Security Risk";
    capEl.style.color = "#10B981";
  } else if (avgRiskScore < 65) {
    capEl.textContent = "Elevated Risk Level";
    capEl.style.color = "#F59E0B";
  } else {
    capEl.textContent = "Critical Threat Risk";
    capEl.style.color = "#EF4444";
  }

  // Risk sub-metrics
  const phishingCount = dbConversations.filter(c => c.security?.threat_type === "Phishing").length;
  const socialEngCount = dbConversations.filter(c => c.security?.threat_type === "Social Engineering").length;
  const sampleTotal = dbConversations.length || 1;

  const metrics = [
    { label: "Phishing Vector Rate", value: Math.round((phishingCount / sampleTotal) * 100), color: "#EF4444", icon: "⚠️" },
    { label: "Social Engineering Rate", value: Math.round((socialEngCount / sampleTotal) * 100), color: "#F97316", icon: "🗣" },
    { label: "Critical Priority Rate", value: Math.round(((data.critical_count || 0) / total) * 100), color: "#7C5CFC", icon: "🚨" },
  ];

  document.getElementById("riskMetrics").innerHTML = metrics.map(m => `
    <div class="metric-bar-row">
      <div class="metric-bar-icon" style="background:${m.color}20">${m.icon}</div>
      <div class="metric-bar-body">
        <div class="metric-bar-header">
          <span style="color: var(--text-muted)">${m.label}</span>
          <span style="font-weight:700; color: var(--text-main);">${m.value}%</span>
        </div>
        <div class="metric-bar-track">
          <div class="metric-bar-fill" style="width:${m.value}%; background:${m.color}"></div>
        </div>
      </div>
    </div>
  `).join("");
}

function renderCharts(data) {
  // 1. Sentiment Donut Chart
  const sentimentCtx = document.getElementById("sentimentChart");
  if (sentimentChartInstance) sentimentChartInstance.destroy();

  const dist = data.sentiment_distribution || { Positive: 0, Neutral: 0, Negative: 0 };
  const total = Object.values(dist).reduce((a, b) => a + b, 0) || 1;

  sentimentChartInstance = new Chart(sentimentCtx, {
    type: "doughnut",
    data: {
      labels: Object.keys(dist),
      datasets: [{
        data: Object.values(dist),
        backgroundColor: ["#10B981", "#64748B", "#EF4444"],
        borderWidth: 0,
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "75%",
      plugins: { legend: { display: false } }
    }
  });

  document.getElementById("sentimentLegend").innerHTML = Object.entries(dist).map(([key, count]) => {
    const pct = Math.round((count / total) * 100);
    const colorMap = { Positive: "#10B981", Neutral: "#64748B", Negative: "#EF4444" };
    return `
      <div class="legend-item">
        <div class="legend-item-title">
          <span style="width:8px;height:8px;border-radius:999px;background:${colorMap[key]}"></span>
          ${key}
        </div>
        <div class="legend-item-val">${pct}%</div>
      </div>
    `;
  }).join("");

  // 2. Category Bar Chart
  const categoryCtx = document.getElementById("categoryChart");
  if (categoryChartInstance) categoryChartInstance.destroy();

  const catDist = data.category_distribution || {};
  const catKeys = Object.keys(catDist);
  const catVals = Object.values(catDist);

  categoryChartInstance = new Chart(categoryCtx, {
    type: "bar",
    data: {
      labels: catKeys,
      datasets: [{
        label: "Tickets",
        data: catVals,
        backgroundColor: catKeys.map(k => (CATEGORY_MAP[k] ? CATEGORY_MAP[k].color : "#7C5CFC")),
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#64748B", font: { size: 10 } } },
        y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#64748B", font: { size: 10 } } }
      }
    }
  });
}

function renderSecurityAlertsStream() {
  const container = document.getElementById("securityAlerts");
  const threats = dbConversations.filter(c => c.security?.threat_detected);

  if (threats.length === 0) {
    container.innerHTML = `<div class="empty-state">No security threats detected in current database snapshot.</div>`;
    return;
  }

  container.innerHTML = threats.slice(0, 15).map(item => {
    const riskClass = `alert-${(item.security.risk_level || "low").toLowerCase()}`;
    const suspiciousUrls = item.security.suspicious_urls || [];
    const suspiciousEmails = item.security.suspicious_emails || [];
    const seFlags = item.security.social_engineering_flags || [];

    return `
      <div class="alert-row ${riskClass}" onclick="openInspectorModal('${escapeHtml(item.conversation_id)}')">
        <div class="alert-icon icon-red">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap mb-1">
            <span class="font-bold text-xs text-red-400">${escapeHtml(item.security.threat_type)}</span>
            ${severityChip(item.security.risk_level)}
            <span class="font-mono-data text-xs text-slate-400">${escapeHtml(item.conversation_id)}</span>
          </div>
          <p class="text-xs text-slate-300 line-clamp-1">${escapeHtml(item.summary || item.text)}</p>
          
          ${suspiciousUrls.length ? `
            <div class="font-mono-data text-xs text-red-400 mt-1 flex items-center gap-1">
              <span>↳ Suspicious URL:</span>
              <span class="bg-red-950/60 px-1.5 py-0.5 rounded border border-red-800/40">${escapeHtml(suspiciousUrls[0])}</span>
            </div>
          ` : ""}

          ${seFlags.length ? `
            <div class="text-xs text-amber-400 mt-1">
              <span>↳ Flag: ${escapeHtml(seFlags[0])}</span>
            </div>
          ` : ""}
        </div>
        <button class="btn-xs">Inspect</button>
      </div>
    `;
  }).join("");
}

function renderInsights(data) {
  const container = document.getElementById("insightsList");
  const total = data.total_conversations || 0;
  const threats = data.threats_detected || 0;
  const unresolved = data.unresolved_count || 0;

  const insights = [];

  if (threats > 0) {
    insights.push({
      title: "Security Threat Active",
      text: `${threats} support conversations flagged as Phishing or Social Engineering vectors.`,
      tag: "Critical",
      tagClass: "badge-tag-red"
    });
  }

  if (unresolved > 0) {
    const unresPct = Math.round((unresolved / (total || 1)) * 100);
    insights.push({
      title: "Unresolved Ticket Queue",
      text: `${unresPct}% of tickets remain in Unresolved status needing triage.`,
      tag: "Attention",
      tagClass: "badge-tag-purple"
    });
  }

  insights.push({
    title: "VADER Sentiment Engine",
    text: "Offline sentiment scoring operational with 0ms network latency overhead.",
    tag: "Optimal",
    tagClass: "badge-tag-green"
  });

  container.innerHTML = insights.map(i => `
    <div class="p-4 space-y-1">
      <div class="flex items-center justify-between">
        <span class="font-bold text-xs text-slate-200">${escapeHtml(i.title)}</span>
        <span class="badge-tag ${i.tagClass}">${escapeHtml(i.tag)}</span>
      </div>
      <p class="text-xs text-slate-400">${escapeHtml(i.text)}</p>
    </div>
  `).join("");
}

function renderMasterTable() {
  const container = document.getElementById("topConversationsBody");

  if (filteredConversations.length === 0) {
    container.innerHTML = `<tr><td colspan="9"><div class="empty-state">No matching conversations found.</div></td></tr>`;
    return;
  }

  container.innerHTML = filteredConversations.map((item, index) => {
    const isThreat = item.security?.threat_detected;
    return `
      <tr onclick="openInspectorModal('${escapeHtml(item.conversation_id)}')">
        <td class="text-slate-500 font-mono-data">${index + 1}</td>
        <td class="font-mono-data font-semibold text-indigo-300">${escapeHtml(item.conversation_id)}</td>
        <td>${categoryBadge(item.category)}</td>
        <td class="max-w-xs truncate text-slate-300">${escapeHtml(item.summary || item.text)}</td>
        <td>${sentimentChip(item.sentiment)}</td>
        <td>${severityChip(item.priority)}</td>
        <td>
          ${isThreat ? `
            <span class="chip chip-critical">
              ⚠ ${escapeHtml(item.security.threat_type)} (${escapeHtml(item.security.risk_level)})
            </span>
          ` : `
            <span class="chip chip-low">✓ Clean</span>
          `}
        </td>
        <td>
          <span class="chip ${item.status === "Resolved" ? "chip-positive" : "chip-neutral"}">
            ${escapeHtml(item.status)}
          </span>
        </td>
        <td class="text-right">
          <button class="btn-xs" onclick="event.stopPropagation(); openInspectorModal('${escapeHtml(item.conversation_id)}')">Inspect</button>
        </td>
      </tr>
    `;
  }).join("");
}

// ---------- Filter & Search Logic ----------

function applyFilters() {
  const searchTerm = (document.getElementById("globalSearchInput").value || "").toLowerCase().trim();
  const categoryVal = document.getElementById("categoryFilter").value;
  const priorityVal = document.getElementById("priorityFilter").value;
  const threatVal = document.getElementById("threatFilter").value;

  filteredConversations = dbConversations.filter(item => {
    // Search match
    if (searchTerm) {
      const matchText = (item.text || "").toLowerCase();
      const matchId = (item.conversation_id || "").toLowerCase();
      const matchSummary = (item.summary || "").toLowerCase();
      if (!matchText.includes(searchTerm) && !matchId.includes(searchTerm) && !matchSummary.includes(searchTerm)) {
        return false;
      }
    }

    // Category match
    if (categoryVal !== "ALL" && item.category !== categoryVal) {
      return false;
    }

    // Priority match
    if (priorityVal !== "ALL" && item.priority !== priorityVal) {
      return false;
    }

    // Threat status match
    if (threatVal === "THREAT_ONLY" && !item.security?.threat_detected) return false;
    if (threatVal === "CLEAN_ONLY" && item.security?.threat_detected) return false;

    return true;
  });

  renderMasterTable();
}

// ---------- Inspector Modal Handler ----------

function openInspectorModal(conversationId) {
  const item = dbConversations.find(c => c.conversation_id === conversationId);
  if (!item) return;

  document.getElementById("modalTicketId").textContent = `Ticket #${item.conversation_id}`;
  document.getElementById("modalFullText").textContent = item.text || "—";
  
  document.getElementById("modalCategory").innerHTML = categoryBadge(item.category);
  document.getElementById("modalSentiment").innerHTML = sentimentChip(item.sentiment);
  document.getElementById("modalPriority").innerHTML = severityChip(item.priority);
  document.getElementById("modalStatus").innerHTML = `<span class="chip ${item.status === 'Resolved' ? 'chip-positive' : 'chip-neutral'}">${escapeHtml(item.status)}</span>`;

  document.getElementById("modalSummary").textContent = item.summary || "No summary generated.";

  const security = item.security || {};
  const modalRiskBadge = document.getElementById("modalRiskBadge");
  modalRiskBadge.className = security.threat_detected ? "chip chip-critical" : "chip chip-low";
  modalRiskBadge.textContent = security.threat_detected ? `THREAT: ${security.threat_type} (${security.risk_level})` : "✓ Clean — No Threat";

  const secContent = document.getElementById("modalSecurityContent");
  if (security.threat_detected) {
    secContent.innerHTML = `
      <div class="text-xs space-y-2">
        <div class="flex items-center gap-2">
          <span class="font-bold text-red-400">Threat Type:</span>
          <span>${escapeHtml(security.threat_type)}</span>
          <span class="font-bold text-red-400 ml-4">Risk Level:</span>
          <span>${escapeHtml(security.risk_level)}</span>
        </div>

        ${security.suspicious_urls?.length ? `
          <div>
            <span class="font-bold text-red-400">Suspicious URLs Found:</span>
            <ul class="list-disc list-inside font-mono-data text-slate-300 mt-1">
              ${security.suspicious_urls.map(u => `<li>${escapeHtml(u)}</li>`).join("")}
            </ul>
          </div>
        ` : ""}

        ${security.suspicious_emails?.length ? `
          <div>
            <span class="font-bold text-red-400">Suspicious Sender Emails:</span>
            <ul class="list-disc list-inside font-mono-data text-slate-300 mt-1">
              ${security.suspicious_emails.map(e => `<li>${escapeHtml(e)}</li>`).join("")}
            </ul>
          </div>
        ` : ""}

        ${security.social_engineering_flags?.length ? `
          <div>
            <span class="font-bold text-amber-400">Social Engineering Phrases Flagged:</span>
            <ul class="list-disc list-inside text-amber-300 mt-1">
              ${security.social_engineering_flags.map(f => `<li>${escapeHtml(f)}</li>`).join("")}
            </ul>
          </div>
        ` : ""}
      </div>
    `;
  } else {
    secContent.innerHTML = `<p class="text-xs text-emerald-400">✓ Deterministic rule check cleared. No suspicious URLs, shorteners, IP links, or social engineering phrases detected.</p>`;
  }

  // Raw JSON
  document.getElementById("modalRawJson").textContent = JSON.stringify(item, null, 2);

  document.getElementById("inspectorModal").classList.remove("hidden");
}

function closeInspectorModal() {
  document.getElementById("inspectorModal").classList.add("hidden");
}

// ---------- Live Playground Analyzer ----------

async function runLiveAnalysis() {
  const textarea = document.getElementById("analyzeInput");
  const text = textarea.value.trim();
  if (!text) return;

  const btn = document.getElementById("analyzeBtn");
  const resultBox = document.getElementById("analyzeResult");
  
  btn.disabled = true;
  btn.innerHTML = `<span class="animate-spin">⏳</span> Analyzing…`;
  
  resultBox.classList.remove("hidden");
  resultBox.innerHTML = `<div class="p-4 text-center text-xs text-slate-400">Passing message payload to Gemini 1.5 + Security Regex Engine…</div>`;

  const conversationId = "live_" + Date.now().toString().slice(-6);

  try {
    const res = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, text })
    });

    if (!res.ok) throw new Error(`HTTP error ${res.status}`);

    const result = await res.json();
    result.text = text;
    
    // Add to local loaded list
    dbConversations.unshift(result);
    applyFilters();
    renderSecurityAlertsStream();

    const isThreat = result.security?.threat_detected;

    resultBox.innerHTML = `
      <div class="p-4 rounded-xl border ${isThreat ? 'border-red-500/40 bg-red-950/20' : 'border-emerald-500/40 bg-emerald-950/20'} space-y-3">
        <div class="flex items-center justify-between flex-wrap gap-2">
          <div class="flex items-center gap-2">
            ${categoryBadge(result.category)}
            ${sentimentChip(result.sentiment)}
            ${severityChip(result.priority)}
            <span class="chip ${result.status === 'Resolved' ? 'chip-positive' : 'chip-neutral'}">${escapeHtml(result.status)}</span>
          </div>
          <span class="font-mono-data text-xs text-slate-400">ID: ${escapeHtml(conversationId)}</span>
        </div>

        <p class="text-xs text-slate-200"><strong>Summary:</strong> ${escapeHtml(result.summary)}</p>

        <div class="text-xs font-semibold ${isThreat ? 'text-red-400' : 'text-emerald-400'}">
          ${isThreat ? `⚠️ THREAT DETECTED: ${result.security.threat_type} (Risk: ${result.security.risk_level})` : `✓ CLEAN: No phishing threat detected.`}
        </div>
      </div>
    `;

    // Refresh dashboard stats
    loadDashboard();
  } catch (err) {
    console.error(err);
    resultBox.innerHTML = `<div class="p-4 text-center text-xs text-red-400">Failed to communicate with backend API at ${API_BASE}. Make sure uvicorn main:app is running.</div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="5 3 19 12 5 21 5 3"/>
      </svg> Run Live Inspection`;
  }
}

// ---------- Batch Ingestion Dropzone ----------

async function handleBatchUpload(file) {
  const statusBox = document.getElementById("batchStatusBox");
  statusBox.classList.remove("hidden");
  statusBox.innerHTML = `<span class="text-indigo-400">Uploading and ingesting ${escapeHtml(file.name)}…</span>`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/analyze-batch`, {
      method: "POST",
      body: formData
    });

    if (!res.ok) throw new Error(`Upload failed: HTTP ${res.status}`);

    const results = await res.json();
    statusBox.innerHTML = `<span class="text-emerald-400">✓ Ingestion complete! Processed ${results.length} tickets into PostgreSQL.</span>`;

    setTimeout(() => {
      document.getElementById("batchModal").classList.add("hidden");
      loadDashboard();
    }, 1500);

  } catch (err) {
    console.error(err);
    statusBox.innerHTML = `<span class="text-red-400">Batch upload error: ${escapeHtml(err.message)}</span>`;
  }
}

// ---------- Data Fetching & Core Dashboard Initialization ----------

async function loadDashboard() {
  const dot = document.getElementById("liveDot");
  const label = document.getElementById("liveLabel");

  try {
    const res = await fetch(`${API_BASE}/dashboard-data`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();

    dot.classList.add("live");
    dot.style.background = "#10B981";
    label.textContent = "Engine Connected";
    label.style.color = "#10B981";

    document.getElementById("lastUpdated").textContent = `Updated ${new Date().toLocaleTimeString()}`;

    // Populate database rows array
    if (Array.isArray(data.recent_conversations)) {
      dbConversations = data.recent_conversations;
      applyFilters();
      renderSecurityAlertsStream();
    }

    renderStatCards(data);
    renderGaugeAndRiskMetrics(data);
    renderCharts(data);
    renderInsights(data);

  } catch (err) {
    console.error("Dashboard fetch error:", err);
    dot.classList.remove("live");
    dot.style.background = "#EF4444";
    label.textContent = "API Unreachable";
    label.style.color = "#EF4444";
  }
}

// ---------- Event Listeners Setup ----------

function setupEventListeners() {
  // Global Search & Filters
  document.getElementById("globalSearchInput").addEventListener("input", applyFilters);
  document.getElementById("categoryFilter").addEventListener("change", applyFilters);
  document.getElementById("priorityFilter").addEventListener("change", applyFilters);
  document.getElementById("threatFilter").addEventListener("change", applyFilters);

  // Live Analyzer Playground
  document.getElementById("analyzeBtn").addEventListener("click", runLiveAnalysis);
  document.getElementById("analyzeInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey || !e.shiftKey)) {
      e.preventDefault();
      runLiveAnalysis();
    }
  });

  // Presets
  document.querySelectorAll(".preset-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const key = chip.getAttribute("data-preset");
      if (PRESETS[key]) {
        document.getElementById("analyzeInput").value = PRESETS[key];
        runLiveAnalysis();
      }
    });
  });

  // Modal Controllers
  document.getElementById("closeModalBtn").addEventListener("click", closeInspectorModal);
  document.getElementById("inspectorModal").addEventListener("click", (e) => {
    if (e.target.id === "inspectorModal") closeInspectorModal();
  });

  document.getElementById("copyJsonBtn").addEventListener("click", () => {
    const jsonText = document.getElementById("modalRawJson").textContent;
    navigator.clipboard.writeText(jsonText);
    const btn = document.getElementById("copyJsonBtn");
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = "Copy JSON"; }, 1500);
  });

  // Batch Upload Modal
  const openBatch = () => document.getElementById("batchModal").classList.remove("hidden");
  const closeBatch = () => document.getElementById("batchModal").classList.add("hidden");

  document.getElementById("openBatchBtn").addEventListener("click", openBatch);
  document.getElementById("batchHeaderBtn").addEventListener("click", openBatch);
  document.getElementById("closeBatchModalBtn").addEventListener("click", closeBatch);

  // File Dropzone
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("batchFileInput");

  document.getElementById("selectFileBtn").addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length) handleBatchUpload(e.target.files[0]);
  });

  dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) handleBatchUpload(e.dataTransfer.files[0]);
  });

  // Refresh Button
  document.getElementById("refreshBtn").addEventListener("click", loadDashboard);

  // Smooth Navigation Scrollspy
  const navItems = document.querySelectorAll(".nav-item[data-nav-target]");
  navItems.forEach(item => {
    item.addEventListener("click", () => {
      navItems.forEach(n => n.classList.remove("active"));
      item.classList.add("active");

      const targetSection = document.querySelector(`[data-nav-section="${item.getAttribute("data-nav-target")}"]`);
      targetSection?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

// Initialize application
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  loadDashboard();
});