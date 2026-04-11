/* ── Config ──────────────────────────────────────────────────────────────── */

const API = "/api";

/* ── Hourly multipliers (mirrors backend) ────────────────────────────────── */

const HM = {
  0:.15,1:.10,2:.08,3:.07,4:.08,5:.15,6:.45,7:1.00,8:1.40,9:1.20,
  10:.90,11:.85,12:.60,13:.95,14:1.00,15:1.10,16:1.30,17:1.50,
  18:1.35,19:1.10,20:.85,21:.70,22:.50,23:.30,
};

/* ── Helpers ─────────────────────────────────────────────────────────────── */

const qs = (s) => document.querySelector(s);
const qsAll = (s) => document.querySelectorAll(s);

async function apiPost(path, body) {
  const r = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(e.detail || "HTTP " + r.status);
  }
  return r.json();
}

function setLoading(btn, on) {
  btn.disabled = on;
  btn.querySelector(".btn__text").hidden = on;
  btn.querySelector(".btn__loader").hidden = !on;
}

function levelColor(l) {
  var colors = {
    Low: "var(--green)",
    Moderate: "var(--yellow)",
    High: "var(--orange)",
    Critical: "var(--red)"
  };
  return colors[l] || "var(--cyan)";
}

/* ── Navigation ──────────────────────────────────────────────────────────── */

var navItems = qsAll(".nav-item");
navItems.forEach(function(el) {
  el.addEventListener("click", function(e) {
    e.preventDefault();
    navItems.forEach(function(n) { n.classList.remove("active"); });
    el.classList.add("active");
    var sec = el.dataset.section;
    var sections = qsAll(".section");
    sections.forEach(function(s) { s.classList.remove("active"); });
    qs("#section-" + sec).classList.add("active");
    qs("#sidebar").classList.remove("open");
  });
});

qs("#mobileToggle").addEventListener("click", function() {
  qs("#sidebar").classList.toggle("open");
});

/* ── Hour slider ─────────────────────────────────────────────────────────── */

var userMultiplier = false;

qs("#pHour").addEventListener("input", function(e) {
  var h = Number(e.target.value);
  qs("#hourBadge").textContent = String(h).padStart(2, "0") + ":00";
  if (!userMultiplier) qs("#pMultiplier").value = HM[h].toFixed(2);
});

qs("#pMultiplier").addEventListener("input", function() {
  userMultiplier = true;
});

/* ── Single prediction ───────────────────────────────────────────────────── */

qs("#predictForm").addEventListener("submit", async function(e) {
  e.preventDefault();
  var btn = qs("#predictBtn");
  setLoading(btn, true);

    var body = {
    city: qs("#pCity").value,
    zone: qs("#pZone").value,
    hour: Number(qs("#pHour").value),
    vehicle_count: Number(qs("#pVehicles").value),
    avg_speed: Number(qs("#pSpeed").value),
    weather: qs("#pWeather").value,
    road_type: qs("#pRoad").value,
    rush_hour: qs("#pRush").checked ? 1 : 0,
    is_weekend: qs("#pWeekend").checked ? 1 : 0,
    is_late_night: qs("#pLateNight").checked ? 1 : 0,
    event: qs("#pEvent").checked ? 1 : 0,
    hour_multiplier: Number(qs("#pMultiplier").value),
    friday_prayer_drop: qs("#pFridayPrayer").checked ? 1 : 0,
  };


  try {
    var d = await apiPost("/predict", body);
    renderResult(d);
  } catch (err) {
    renderError(err.message);
  } finally {
    setLoading(btn, false);
  }
});

function renderResult(d) {
  qs("#resultEmpty").hidden = true;
  var el = qs("#resultContent");
  el.hidden = false;

  var pct = Math.round(d.congestion_score * 100);
  var col = levelColor(d.congestion_level);
  var circ = 2 * Math.PI * 66;
  var off = circ * (1 - d.congestion_score);

  el.innerHTML =
    '<div class="score-ring-wrap">' +
      '<div class="score-ring">' +
        '<svg viewBox="0 0 160 160">' +
          '<circle class="track" cx="80" cy="80" r="66"/>' +
          '<circle class="fill" cx="80" cy="80" r="66" ' +
            'stroke="' + col + '" ' +
            'stroke-dasharray="' + circ + '" ' +
            'stroke-dashoffset="' + circ + '" ' +
            'style="transition:stroke-dashoffset 1.2s cubic-bezier(.4,0,.2,1)"/>' +
        '</svg>' +
        '<div class="score-val">' +
          '<span class="score-val__num" style="color:' + col + '">0</span>' +
          '<span class="score-val__lbl">Congestion</span>' +
        '</div>' +
      '</div>' +
    '</div>' +
    '<div style="text-align:center">' +
      '<span class="level-badge ' + d.congestion_level + '">' + d.congestion_level + '</span>' +
    '</div>' +
    '<div class="result-meta">' +
      '<span class="meta-chip">' + d.city + '</span>' +
      '<span class="meta-chip">' + d.zone + '</span>' +
      '<span class="meta-chip">' + String(d.hour).padStart(2, "0") + ':00</span>' +
      '<span class="meta-chip">' + d.weather + '</span>' +
    '</div>' +
    '<div class="rec-card">' +
      '<h3>Recommendation</h3>' +
      '<p>' + d.recommendation + '</p>' +
    '</div>';

  requestAnimationFrame(function() {
    el.querySelector(".fill").style.strokeDashoffset = off;
    animateNum(el.querySelector(".score-val__num"), pct);
  });
}

function renderError(msg) {
  qs("#resultEmpty").hidden = true;
  var el = qs("#resultContent");
  el.hidden = false;
  el.innerHTML =
    '<div class="rec-card" style="border-color:var(--red);background:var(--red-bg)">' +
      '<h3 style="color:var(--red)">Error</h3>' +
      '<p>' + msg + '</p>' +
    '</div>';
}

function animateNum(node, target) {
  var cur = 0;
  var step = Math.max(1, Math.ceil(target / 40));
  var iv = setInterval(function() {
    cur = Math.min(cur + step, target);
    node.textContent = cur;
    if (cur >= target) clearInterval(iv);
  }, 25);
}

/* ── Batch prediction ────────────────────────────────────────────────────── */

qs("#batchBtn").addEventListener("click", async function() {
  var btn = qs("#batchBtn");
  setLoading(btn, true);

  var city = qs("#bCity").value;
  var hour = Number(qs("#bHour").value);
  var weather = qs("#bWeather").value;
  var hm = HM[hour];
  var rush = (hour >= 7 && hour <= 9) || (hour >= 16 && hour <= 18) ? 1 : 0;

  var profiles = [
    { zone: "Zone_1", vc: 320, sp: 35, road: "highway" },
    { zone: "Zone_2", vc: 200, sp: 50, road: "arterial" },
    { zone: "Zone_3", vc: 120, sp: 60, road: "residential" },
    { zone: "Zone_4", vc: 180, sp: 45, road: "collector" },
    { zone: "Zone_5", vc: 260, sp: 40, road: "arterial" },
  ];

  var predictions = profiles.map(function(p) {
    return {
      city: city, zone: p.zone, hour: hour,
      vehicle_count: p.vc, avg_speed: p.sp,
      weather: weather, road_type: p.road, rush_hour: rush,
      is_weekend: 0, is_late_night: 0, event: 0,
      hour_multiplier: hm,
    };
  });

  try {
    var data = await apiPost("/predict/batch", { predictions: predictions });
    renderBatch(data.results);
  } catch (err) {
    qs("#batchResults").innerHTML =
      '<div class="rec-card" style="border-color:var(--red);background:var(--red-bg)">' +
        '<h3 style="color:var(--red)">Error</h3>' +
        '<p>' + err.message + '</p>' +
      '</div>';
  } finally {
    setLoading(btn, false);
  }
});

function renderBatch(results) {
  var rows = results.map(function(r) {
    return '<tr>' +
      '<td>' + r.zone + '</td>' +
      '<td class="batch-score" style="color:' + levelColor(r.congestion_level) + '">' +
        (r.congestion_score * 100).toFixed(1) + '%' +
      '</td>' +
      '<td><span class="level-badge ' + r.congestion_level + '" style="font-size:.72rem;padding:3px 10px">' +
        r.congestion_level +
      '</span></td>' +
      '<td style="color:var(--text2);font-size:.82rem">' + r.recommendation + '</td>' +
    '</tr>';
  }).join("");

  qs("#batchResults").innerHTML =
    '<table class="batch-table">' +
      '<thead><tr><th>Zone</th><th>Score</th><th>Level</th><th>Recommendation</th></tr></thead>' +
      '<tbody>' + rows + '</tbody>' +
    '</table>';
}

/* ── System status ───────────────────────────────────────────────────────── */

async function loadStatus() {
  try {
    var r = await fetch(API + "/health");
    var d = await r.json();
    var m = d.model_metrics || {};

    qs("#statusDot").classList.add("ok");
    qs("#statusText").textContent = "API Connected";

    var r2val = m.r2 != null ? m.r2.toFixed(4) : "—";
    var r2sub = m.r2 > 0.85 ? "Production ready" : "Acceptable";
    var rmseval = m.rmse != null ? m.rmse.toFixed(4) : "—";

    qs("#statusGrid").innerHTML =
      '<div class="card glass-card status-card">' +
        '<div class="status-card__icon" style="background:var(--green-bg);color:var(--green)">●</div>' +
        '<div class="status-card__label">API Status</div>' +
        '<div class="status-card__value" style="color:var(--green)">Online</div>' +
        '<div class="status-card__sub">FastAPI + XGBoost</div>' +
      '</div>' +
      '<div class="card glass-card status-card">' +
        '<div class="status-card__icon" style="background:var(--cyan-glow);color:var(--cyan)">◈</div>' +
        '<div class="status-card__label">Model R² Score</div>' +
        '<div class="status-card__value">' + r2val + '</div>' +
        '<div class="status-card__sub">' + r2sub + '</div>' +
      '</div>' +
      '<div class="card glass-card status-card">' +
        '<div class="status-card__icon" style="background:var(--yellow-bg);color:var(--yellow)">△</div>' +
        '<div class="status-card__label">RMSE</div>' +
        '<div class="status-card__value">' + rmseval + '</div>' +
        '<div class="status-card__sub">Root Mean Square Error</div>' +
      '</div>' +
      '<div class="card glass-card status-card">' +
        '<div class="status-card__icon" style="background:var(--cyan-glow);color:var(--cyan)">⊞</div>' +
        '<div class="status-card__label">Model</div>' +
        '<div class="status-card__value">XGBoost</div>' +
        '<div class="status-card__sub">500 estimators, depth 6</div>' +
      '</div>';
  } catch (err) {
    qs("#statusDot").classList.add("err");
    qs("#statusText").textContent = "API Offline";
    qs("#statusGrid").innerHTML =
      '<div class="card glass-card">' +
        '<p style="color:var(--red)">Cannot reach API at <code>' + API + '</code>. Make sure the backend is running.</p>' +
      '</div>';
  }
}

/* ── Init ────────────────────────────────────────────────────────────────── */

(function init() {
  var overlay = qs("#loadingOverlay");
  var attempts = 0;
  var maxAttempts = 60;

  var poll = setInterval(async function() {
    attempts++;
    try {
      var r = await fetch(API + "/health");
      if (r.ok) {
        var data = await r.json();
        if (data.model_loaded) {
          overlay.hidden = true;
          clearInterval(poll);
          loadStatus();
        }
      }
    } catch (err) {
      /* backend not ready yet */
    }

    if (attempts >= maxAttempts) {
      clearInterval(poll);
      overlay.innerHTML =
        '<div class="loading-card">' +
          '<h3 style="color:var(--red)">Connection Timeout</h3>' +
          '<p>Could not reach the API at ' + API + '. Make sure the backend is running.</p>' +
        '</div>';
    }
  }, 1000);
})();
