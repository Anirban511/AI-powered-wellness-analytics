/* Aura dashboard — talks to the FastAPI backend and renders both views. */
const $ = (id) => document.getElementById(id);
let currentUser = null;
let ribbon = null;

/* ---------- view switching ---------- */
function setView(v) {
  $("view-me").classList.toggle("active", v === "me");
  $("view-biz").classList.toggle("active", v === "biz");
  $("tab-me").classList.toggle("active", v === "me");
  $("tab-biz").classList.toggle("active", v === "biz");
  if (v === "biz") loadBusiness();
}

/* ---------- init ---------- */
async function init() {
  const users = await fetch("/api/users").then((r) => r.json());
  const sel = $("userSelect");
  sel.innerHTML = users
    .map((u) => `<option value="${u.id}" data-persona="${u.persona}">${u.username}</option>`)
    .join("");
  if (users.length) {
    currentUser = users[0].id;
    loadUser();
  }
}

/* ---------- personal view ---------- */
async function loadUser() {
  const sel = $("userSelect");
  currentUser = parseInt(sel.value);
  const persona = sel.options[sel.selectedIndex]?.dataset.persona || "";
  $("personaTag").textContent = persona ? `demo persona: ${persona}` : "";
  $("reportLink").href = `/report/${currentUser}`;
  $("analysis").classList.remove("show");
  $("entryText").value = "";
  await Promise.all([loadTrend(), loadStandingRecs()]);
}

async function loadTrend() {
  const t = await fetch(`/api/users/${currentUser}/trends`).then((r) => r.json());
  $("trendSummary").textContent = t.summary || "—";
  $("mState").textContent = t.state ?? "—";
  $("mTrend").textContent = t.trend ?? "—";
  $("mForecast").textContent = t.forecast_next_week != null ? Math.round(t.forecast_next_week) : "—";
  $("mVol").textContent = t.volatility != null ? Math.round(t.volatility) : "—";
  drawRibbon(t);
}

function drawRibbon(t) {
  const labels = t.series.map((p) => p.date.slice(5));
  const stress = t.series.map((p) => p.stress);
  const ewma = t.series.map((p) => p.ewma);
  const anomSet = new Set((t.anomalies || []).map((a) => a.date.slice(5)));
  const pointColors = labels.map((d) => (anomSet.has(d) ? "#d96a5b" : "transparent"));

  const ctx = $("ribbonChart").getContext("2d");
  const grad = ctx.createLinearGradient(0, 0, 0, 240);
  grad.addColorStop(0, "rgba(217,106,91,.28)");
  grad.addColorStop(1, "rgba(47,143,125,.06)");

  if (ribbon) ribbon.destroy();
  ribbon = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "daily stress", data: stress, borderColor: "rgba(107,125,131,.5)",
          backgroundColor: grad, fill: true, tension: 0.35, pointRadius: 0, borderWidth: 1.2 },
        { label: "trend (EWMA)", data: ewma, borderColor: "#20303a", borderWidth: 2.4,
          fill: false, tension: 0.35, pointRadius: 0 },
        { label: "spike day", data: stress, showLine: false,
          pointBackgroundColor: pointColors, pointBorderColor: pointColors, pointRadius: 5 },
      ],
    },
    options: {
      responsive: true,
      scales: { y: { min: 0, max: 100, grid: { color: "#eef1ef" } }, x: { grid: { display: false } } },
      plugins: { legend: { labels: { boxWidth: 12, font: { size: 11 } } } },
    },
  });
}

async function loadStandingRecs() {
  const recs = await fetch(`/api/users/${currentUser}/recommendations`).then((r) => r.json());
  const box = $("standingRecs");
  if (!recs.length) { box.innerHTML = '<div class="empty">No recommendations yet — add an entry.</div>'; return; }
  box.innerHTML = recs.map(renderRec).join("");
}

function renderRec(r) {
  const cls = r.category === "support" ? "rec support" : "rec" + (r.accepted ? " done" : "");
  const action = r.category === "support" || r.accepted
    ? (r.accepted ? '<span class="persona-tag">✓ acted on</span>' : "")
    : `<button class="btn ghost small" onclick="acceptRec(${r.id}, this)">I'll try this</button>`;
  return `<div class="${cls}">
    <h4>${r.title}</h4><p>${r.body}</p>
    <div class="why">Why: ${r.rationale}</div>
    <div class="actions">${action}</div></div>`;
}

async function acceptRec(id, btn) {
  await fetch(`/api/recommendations/${id}/accept`, { method: "POST" });
  btn.outerHTML = '<span class="persona-tag">✓ acted on</span>';
}

async function analyzeEntry() {
  const text = $("entryText").value.trim();
  if (!text) return;
  const res = await fetch("/api/entries", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: currentUser, text }),
  }).then((r) => r.json());

  // chips
  const s = res.sentiment;
  const labelClass = s.label === "positive" ? "pos" : s.label === "negative" ? "neg" : "neu";
  const themeChips = (res.themes || []).map((t) => `<span class="chip neu">${t}</span>`).join("");
  $("analysisChips").innerHTML =
    `<span class="chip ${labelClass}">${s.label} · ${s.compound}</span>` +
    (res.safety_flag ? '<span class="chip neg">support shown</span>' : "") + themeChips;

  // gauge
  $("stressVal").textContent = `stress ${res.stress_score}/100`;
  $("stressNeedle").style.left = `${res.stress_score}%`;

  // live recs
  $("liveRecs").innerHTML = res.recommendations.map(renderRec).join("");
  $("analysis").classList.add("show");

  // refresh trend + standing recs to reflect the new entry
  loadTrend();
  loadStandingRecs();
}

/* ---------- business view ---------- */
let bizLoaded = false;
async function loadBusiness() {
  if (bizLoaded) return;
  bizLoaded = true;
  const [ov, fn, ret] = await Promise.all([
    fetch("/api/analytics/overview").then((r) => r.json()),
    fetch("/api/analytics/funnel").then((r) => r.json()),
    fetch("/api/analytics/retention").then((r) => r.json()),
  ]);
  renderKpis(ov);
  renderFunnel(fn);
  renderRetention(ret);
  loadRoi();
}

function renderKpis(ov) {
  $("asOf").textContent = `as of ${ov.as_of}`;
  $("kUsers").textContent = ov.total_users;
  $("kWau").textContent = ov.wau;
  $("kStick").textContent = ov.stickiness_dau_wau;
  $("kStress").textContent = ov.avg_stress_score;
  $("kImprove").textContent = ov.pct_users_improving + "%";
  $("kFlags").textContent = ov.safety_flags;
  const ch = $("kChange");
  if (ov.avg_stress_change != null) {
    const better = ov.avg_stress_change < 0;
    ch.textContent = `  ${better ? "▼" : "▲"} ${Math.abs(ov.avg_stress_change)} avg stress`;
    ch.className = "delta " + (better ? "good" : "bad");
  }
}

function renderFunnel(fn) {
  const max = fn.steps[0]?.users || 1;
  $("funnel").innerHTML = fn.steps.map((s) => {
    const w = Math.max(6, (100 * s.users) / max);
    return `<div class="funnel-step">
      <div class="lab"><span>${s.name}</span><span>${s.users} · ${s.pct}%</span></div>
      <div class="funnel-bar" style="width:${w}%">${s.users}</div></div>`;
  }).join("");
}

function retColor(p) {
  // sage(low stress=good retention) green scale
  const a = Math.max(0.06, Math.min(1, p / 100));
  return `background: rgba(47,143,125,${a}); color:${a > 0.55 ? "#fff" : "#20303a"}`;
}

function renderRetention(ret) {
  if (!ret.cohorts.length) { $("retention").innerHTML = '<div class="empty">No cohort data.</div>'; return; }
  const head = `<tr><th class="label">Cohort</th><th>n</th>${ret.week_labels.map((w) => `<th>${w}</th>`).join("")}</tr>`;
  const rows = ret.cohorts.map((c) => {
    const cells = c.retention.map((p) => `<td style="${retColor(p)}">${p}%</td>`).join("");
    return `<tr><td class="label">${c.cohort}</td><td>${c.size}</td>${cells}</tr>`;
  }).join("");
  $("retention").innerHTML = `<table class="cohort">${head}${rows}</table>`;
}

async function loadRoi() {
  const seats = parseInt($("roiSeats").value) || 1;
  const price = parseFloat($("roiPrice").value) || 0;
  const roi = await fetch(`/api/analytics/roi?seats=${seats}&price=${price}`).then((r) => r.json());
  const fmt = (n) => "$" + Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
  $("roiGrid").innerHTML = `
    <div class="roi-cell"><div class="v">${fmt(roi.mrr)}</div><div class="k">MRR (${roi.seats} seats × $${roi.price_per_seat_month})</div></div>
    <div class="roi-cell"><div class="v">${fmt(roi.arr)}</div><div class="k">ARR</div></div>
    <div class="roi-cell"><div class="v">${fmt(roi.estimated_annual_value_delivered)}</div><div class="k">est. annual value delivered</div></div>
    <div class="roi-cell hi"><div class="v">${roi.roi_multiple}×</div><div class="k">value-to-revenue ratio</div></div>`;
  $("roiNote").textContent =
    `Assumes ${roi.engaged_pct}% engage and ${roi.pct_improving}% of engaged users improve, saving `
    + `${roi.assumptions.absence_days_saved_per_improved_user} day(s)/yr at $${roi.assumptions.avg_loaded_cost_per_day}/day. `
    + roi.assumptions.note;
}

init();
