var API = "/api";

var ZONES = {
  "Olaya":                        { lat: 24.6900, lng: 46.6850, baseVehicles: 280, speed: 60,  road: "arterial" },
  "Al-Malaz":                     { lat: 24.6750, lng: 46.7250, baseVehicles: 240, speed: 50,  road: "arterial" },
  "Sulaimaniyah":                 { lat: 24.7000, lng: 46.6700, baseVehicles: 200, speed: 45,  road: "collector" },
  "Al-Rawdah":                    { lat: 24.7350, lng: 46.7150, baseVehicles: 220, speed: 50,  road: "arterial" },
  "Al-Naseem":                    { lat: 24.6550, lng: 46.7400, baseVehicles: 260, speed: 55,  road: "arterial" },
  "Al-Shemaysi":                  { lat: 24.6350, lng: 46.7100, baseVehicles: 190, speed: 40,  road: "residential" },
  "Diriyah":                      { lat: 24.7320, lng: 46.5740, baseVehicles: 150, speed: 45,  road: "collector" },
  "Al-Batha":                     { lat: 24.6450, lng: 46.7050, baseVehicles: 300, speed: 35,  road: "arterial" },
  "King Abdullah Financial Dist": { lat: 24.7680, lng: 46.6400, baseVehicles: 310, speed: 60,  road: "highway" },
  "Diplomatic Quarter":           { lat: 24.7050, lng: 46.5850, baseVehicles: 160, speed: 55,  road: "arterial" }
};

var ROADS = [
  { from: "Olaya", to: "Sulaimaniyah", type: "arterial", path: [[24.6900,46.6850],[24.6920,46.6820],[24.6940,46.6780],[24.6960,46.6750],[24.6980,46.6720],[24.7000,46.6700]] },
  { from: "Olaya", to: "Al-Malaz", type: "highway", path: [[24.6900,46.6850],[24.6880,46.6900],[24.6860,46.6960],[24.6840,46.7020],[24.6820,46.7080],[24.6800,46.7140],[24.6780,46.7190],[24.6760,46.7230],[24.6750,46.7250]] },
  { from: "Olaya", to: "King Abdullah Financial Dist", type: "highway", path: [[24.6900,46.6850],[24.6940,46.6820],[24.6980,46.6780],[24.7040,46.6740],[24.7100,46.6700],[24.7180,46.6650],[24.7260,46.6600],[24.7340,46.6550],[24.7420,46.6500],[24.7500,46.6470],[24.7580,46.6440],[24.7630,46.6420],[24.7680,46.6400]] },
  { from: "Al-Malaz", to: "Al-Rawdah", type: "arterial", path: [[24.6750,46.7250],[24.6800,46.7240],[24.6860,46.7230],[24.6930,46.7220],[24.7000,46.7210],[24.7080,46.7200],[24.7160,46.7190],[24.7240,46.7180],[24.7300,46.7160],[24.7350,46.7150]] },
  { from: "Al-Malaz", to: "Al-Naseem", type: "arterial", path: [[24.6750,46.7250],[24.6720,46.7280],[24.6690,46.7310],[24.6660,46.7340],[24.6620,46.7370],[24.6580,46.7390],[24.6550,46.7400]] },
  { from: "Al-Malaz", to: "Al-Batha", type: "collector", path: [[24.6750,46.7250],[24.6720,46.7220],[24.6680,46.7190],[24.6640,46.7160],[24.6600,46.7130],[24.6560,46.7100],[24.6510,46.7070],[24.6450,46.7050]] },
  { from: "Al-Rawdah", to: "King Abdullah Financial Dist", type: "highway", path: [[24.7350,46.7150],[24.7380,46.7100],[24.7420,46.7040],[24.7460,46.6970],[24.7500,46.6900],[24.7540,46.6820],[24.7570,46.6720],[24.7600,46.6620],[24.7630,46.6520],[24.7660,46.6460],[24.7680,46.6400]] },
  { from: "Al-Naseem", to: "Al-Shemaysi", type: "residential", path: [[24.6550,46.7400],[24.6520,46.7360],[24.6480,46.7320],[24.6440,46.7260],[24.6400,46.7200],[24.6370,46.7150],[24.6350,46.7100]] },
  { from: "Al-Naseem", to: "Al-Batha", type: "collector", path: [[24.6550,46.7400],[24.6530,46.7360],[24.6510,46.7320],[24.6490,46.7270],[24.6470,46.7210],[24.6460,46.7150],[24.6450,46.7100],[24.6450,46.7050]] },
  { from: "Al-Batha", to: "Al-Shemaysi", type: "residential", path: [[24.6450,46.7050],[24.6430,46.7070],[24.6400,46.7080],[24.6380,46.7090],[24.6350,46.7100]] },
  { from: "Sulaimaniyah", to: "Diplomatic Quarter", type: "arterial", path: [[24.7000,46.6700],[24.7010,46.6650],[24.7020,46.6600],[24.7030,46.6540],[24.7035,46.6480],[24.7040,46.6400],[24.7042,46.6320],[24.7045,46.6240],[24.7048,46.6160],[24.7050,46.6080],[24.7050,46.6000],[24.7050,46.5920],[24.7050,46.5850]] },
  { from: "King Abdullah Financial Dist", to: "Diplomatic Quarter", type: "highway", path: [[24.7680,46.6400],[24.7620,46.6360],[24.7550,46.6320],[24.7480,46.6280],[24.7400,46.6240],[24.7320,46.6200],[24.7240,46.6160],[24.7160,46.6120],[24.7100,46.6040],[24.7070,46.5950],[24.7050,46.5850]] },
  { from: "King Abdullah Financial Dist", to: "Al-Rawdah", type: "arterial", path: [[24.7680,46.6400],[24.7620,46.6480],[24.7560,46.6560],[24.7500,46.6640],[24.7440,46.6720],[24.7400,46.6820],[24.7370,46.6920],[24.7360,46.7020],[24.7350,46.7150]] },
  { from: "Diriyah", to: "Diplomatic Quarter", type: "collector", path: [[24.7320,46.5740],[24.7280,46.5760],[24.7240,46.5780],[24.7200,46.5800],[24.7160,46.5820],[24.7120,46.5830],[24.7080,46.5840],[24.7050,46.5850]] },
  { from: "Diriyah", to: "Sulaimaniyah", type: "highway", path: [[24.7320,46.5740],[24.7310,46.5820],[24.7300,46.5920],[24.7280,46.6020],[24.7250,46.6120],[24.7220,46.6220],[24.7180,46.6320],[24.7140,46.6420],[24.7100,46.6500],[24.7060,46.6580],[24.7020,46.6640],[24.7000,46.6700]] }
];

var ROAD_STYLE = {
  highway:     { weight: 5, opacity: 0.30, dash: null },
  arterial:    { weight: 4, opacity: 0.25, dash: null },
  collector:   { weight: 3, opacity: 0.20, dash: null },
  residential: { weight: 2, opacity: 0.15, dash: "6,8" }
};

var ROAD_STYLE_ACTIVE = {
  highway:     { weight: 10, opacity: 0.85 },
  arterial:    { weight: 8,  opacity: 0.80 },
  collector:   { weight: 6,  opacity: 0.75 },
  residential: { weight: 5,  opacity: 0.70 }
};

var HM = {
  0:.15,1:.10,2:.08,3:.07,4:.08,5:.15,6:.45,7:1.00,8:1.40,9:1.20,
  10:.90,11:.85,12:.60,13:.95,14:1.00,15:1.10,16:1.30,17:1.50,
  18:1.35,19:1.10,20:.85,21:.70,22:.50,23:.30
};

var qs = function(s) { return document.querySelector(s); };
var qsAll = function(s) { return document.querySelectorAll(s); };

var mapObj = null;
var batchMapObj = null;
var districtMarkers = {};
var batchDistrictMarkers = {};
var roadLines = [];
var batchRoadLines = [];
var carLayers = [];
var batchCarLayers = [];
var animList = [];
var batchAnimList = [];
var animFrameId = null;
var lastResult = null;

function levelColor(l) {
  var c = { Low: "#00ff88", Moderate: "#ffcc00", High: "#ff8844", Critical: "#ff4444" };
  return c[l] || "#00d4ff";
}

function levelVar(l) {
  var c = { Low: "var(--cong-low)", Moderate: "var(--cong-moderate)", High: "var(--cong-high)", Critical: "var(--cong-critical)" };
  return c[l] || "var(--accent)";
}

function setLoading(btn, on) {
  btn.disabled = on;
  btn.querySelector(".btn__text").hidden = on;
  btn.querySelector(".btn__loader").style.display = on ? "block" : "none";
}

async function apiPost(path, body) {
  var r = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!r.ok) {
    var e = await r.json().catch(function() { return {}; });
    throw new Error(e.detail || "HTTP " + r.status);
  }
  return r.json();
}

function carSVG(color) {
  return '<svg width="20" height="10" viewBox="0 0 20 10" xmlns="http://www.w3.org/2000/svg">'
    + '<rect x="1" y="4" width="18" height="5" rx="2.5" fill="' + color + '"/>'
    + '<rect x="4" y="1" width="12" height="5" rx="2" fill="' + color + '" opacity="0.85"/>'
    + '<rect x="5.5" y="2" width="3.5" height="2.5" rx="0.8" fill="rgba(180,220,255,0.35)"/>'
    + '<rect x="11" y="2" width="3.5" height="2.5" rx="0.8" fill="rgba(180,220,255,0.35)"/>'
    + '<circle cx="5" cy="9" r="1.8" fill="#222"/>'
    + '<circle cx="15" cy="9" r="1.8" fill="#222"/>'
    + '<circle cx="5" cy="9" r="0.8" fill="#555"/>'
    + '<circle cx="15" cy="9" r="0.8" fill="#555"/>'
    + '<rect x="0" y="5" width="1.5" height="1.5" rx="0.5" fill="rgba(255,200,50,0.7)"/>'
    + '<rect x="18.5" y="5" width="1.5" height="1.5" rx="0.5" fill="rgba(255,50,50,0.7)"/>'
    + '</svg>';
}

function truckSVG(color) {
  return '<svg width="28" height="11" viewBox="0 0 28 11" xmlns="http://www.w3.org/2000/svg">'
    + '<rect x="0" y="2" width="16" height="7" rx="1.5" fill="' + color + '" opacity="0.85"/>'
    + '<rect x="16" y="3" width="10" height="6" rx="2" fill="' + color + '"/>'
    + '<rect x="18" y="4" width="6" height="3" rx="1" fill="rgba(180,220,255,0.3)"/>'
    + '<circle cx="5" cy="9.5" r="1.8" fill="#222"/>'
    + '<circle cx="12" cy="9.5" r="1.8" fill="#222"/>'
    + '<circle cx="22" cy="9.5" r="1.8" fill="#222"/>'
    + '<rect x="0" y="4" width="1.5" height="1.5" rx="0.5" fill="rgba(255,200,50,0.7)"/>'
    + '</svg>';
}

function calcBearing(lat1, lng1, lat2, lng2) {
  var dLng = (lng2 - lng1) * Math.PI / 180;
  var lat1R = lat1 * Math.PI / 180;
  var lat2R = lat2 * Math.PI / 180;
  var y = Math.sin(dLng) * Math.cos(lat2R);
  var x = Math.cos(lat1R) * Math.sin(lat2R) - Math.sin(lat1R) * Math.cos(lat2R) * Math.cos(dLng);
  return Math.atan2(y, x) * 180 / Math.PI;
}

function buildSegLens(path) {
  var segLens = [];
  var total = 0;
  for (var i = 1; i < path.length; i++) {
    var d = Math.sqrt(Math.pow(path[i][0] - path[i - 1][0], 2) + Math.pow(path[i][1] - path[i - 1][1], 2));
    segLens.push(d);
    total += d;
  }
  return { segLens: segLens, total: total };
}

function pointOnPath(path, segLens, totalDist, progress) {
  if (progress > 1) progress -= 1;
  if (progress < 0) progress += 1;
  var target = progress * totalDist;
  var acc = 0;
  for (var i = 0; i < segLens.length; i++) {
    if (acc + segLens[i] >= target) {
      var t = (target - acc) / segLens[i];
      return [
        path[i][0] + (path[i + 1][0] - path[i][0]) * t,
        path[i][1] + (path[i + 1][1] - path[i][1]) * t
      ];
    }
    acc += segLens[i];
  }
  return [path[path.length - 1][0], path[path.length - 1][1]];
}

function initMapEl(id) {
  var m = L.map(id, {
    center: [24.6900, 46.6700],
    zoom: 12,
    zoomControl: true,
    attributionControl: false
  });
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19, subdomains: "abcd"
  }).addTo(m);
  return m;
}

function addMarker(m, name, data) {
  var icon = L.divIcon({
    className: "district-marker-wrapper",
    html: '<div class="district-marker"></div><div class="district-label-static">' + name + '</div>',
    iconSize: [24, 24],
    iconAnchor: [12, 12]
  });
  var mk = L.marker([data.lat, data.lng], { icon: icon }).addTo(m);
  mk.zoneName = name;
  mk.on("click", function() {
    runPrediction(name);
  });
  return mk;
}

function drawRoads(m, arr) {
  for (var i = 0; i < ROADS.length; i++) {
    var rd = ROADS[i];
    var cfg = ROAD_STYLE[rd.type] || ROAD_STYLE.collector;
    var line = L.polyline(rd.path, {
      color: "#ffffff", weight: cfg.weight, opacity: cfg.opacity,
      dashArray: cfg.dash, lineCap: "round", lineJoin: "round"
    }).addTo(m);
    line.roadFrom = rd.from;
    line.roadTo = rd.to;
    line.roadType = rd.type;
    line._glow = null;
    arr.push(line);
  }
}

function activateRoad(line, score, level) {
  var color = levelColor(level);
  var cfg = ROAD_STYLE_ACTIVE[line.roadType] || ROAD_STYLE_ACTIVE.collector;
  line.setStyle({ color: color, weight: cfg.weight, opacity: cfg.opacity, dashArray: null });
  if (!line._glow) {
    line._glow = L.polyline(line.getLatLngs(), {
      color: color, weight: cfg.weight + 10, opacity: 0.15, lineCap: "round", lineJoin: "round"
    });
  }
  line._glow.setStyle({ color: color, opacity: 0.15, weight: cfg.weight + 10 });
  line._glow.addTo(line._map);
}

function deactivateRoad(line) {
  var cfg = ROAD_STYLE[line.roadType] || ROAD_STYLE.collector;
  line.setStyle({ color: "#ffffff", weight: cfg.weight, opacity: cfg.opacity, dashArray: cfg.dash });
  if (line._glow && line._map) line._map.removeLayer(line._glow);
}

function resetRoads(arr) {
  for (var i = 0; i < arr.length; i++) deactivateRoad(arr[i]);
}

function updateMarkerStyle(mk, score, level) {
  var color = levelColor(level);
  var el = mk.getElement();
  if (el) {
    var dot = el.querySelector(".district-marker");
    if (dot) {
      dot.style.background = color;
      dot.style.boxShadow = "0 0 25px " + color;
      dot.style.width = (18 + score * 14) + "px";
      dot.style.height = (18 + score * 14) + "px";
    }
  }
}

function spawnCars(m, line, score, level, carArr, animArr) {
  var path = line.getLatLngs();
  if (!path || path.length < 2) return;
  var info = buildSegLens(path);
  if (info.total === 0) return;
  var color = levelColor(level);
  var isHW = line.roadType === "highway";
  var count = isHW ? Math.max(5, Math.floor(score * 16)) : Math.max(3, Math.floor(score * 12));
  var speed = (0.3 + (1 - score) * 0.7) * (isHW ? 1.4 : 1.0);

  for (var i = 0; i < count; i++) {
    var startProg = (i / count) + (Math.random() * 0.05);
    if (startProg > 1) startProg -= 1;
    var pos = pointOnPath(path, info.segLens, info.total, startProg);
    var nxt = pointOnPath(path, info.segLens, info.total, startProg + 0.001);
    var angle = calcBearing(pos[0], pos[1], nxt[0], nxt[1]);

    var icon = L.divIcon({
      className: "car-marker",
      html: '<div style="transform:rotate(' + angle + 'deg)">' + (isHW ? truckSVG(color) : carSVG(color)) + '</div>',
      iconSize: isHW ? [28, 11] : [20, 10],
      iconAnchor: isHW ? [14, 5] : [10, 5]
    });

    var car = L.marker([pos[0], pos[1]], { icon: icon, interactive: false }).addTo(m);
    carArr.push(car);
    animArr.push({
      marker: car, path: path, segLens: info.segLens, total: info.total,
      progress: startProg, speed: speed * (0.0008 + Math.random() * 0.0004),
      isTruck: isHW, color: color
    });
  }
}

function clearCars(carArr, animArr, m) {
  for (var i = 0; i < carArr.length; i++) {
    if (m) m.removeLayer(carArr[i]);
  }
  carArr.length = 0;
  animArr.length = 0;
}

function animLoop() {
  var all = animList.concat(batchAnimList);
  for (var i = 0; i < all.length; i++) {
    var a = all[i];
    a.progress += a.speed;
    if (a.progress > 1) a.progress -= 1;
    var pos = pointOnPath(a.path, a.segLens, a.total, a.progress);
    var nxt = pointOnPath(a.path, a.segLens, a.total, a.progress + 0.002);
    var angle = calcBearing(pos[0], pos[1], nxt[0], nxt[1]);
    a.marker.setLatLng([pos[0], pos[1]]);
    var icon = L.divIcon({
      className: "car-marker",
      html: '<div style="transform:rotate(' + angle + 'deg)">' + (a.isTruck ? truckSVG(a.color) : carSVG(a.color)) + '</div>',
      iconSize: a.isTruck ? [28, 11] : [20, 10],
      iconAnchor: a.isTruck ? [14, 5] : [10, 5]
    });
    a.marker.setIcon(icon);
  }
  animFrameId = requestAnimationFrame(animLoop);
}

function initAll() {
  mapObj = initMapEl("map");
  batchMapObj = initMapEl("batchMap");
  drawRoads(mapObj, roadLines);
  drawRoads(batchMapObj, batchRoadLines);
  var names = Object.keys(ZONES);
  for (var i = 0; i < names.length; i++) {
    var n = names[i];
    districtMarkers[n] = addMarker(mapObj, n, ZONES[n]);
    batchDistrictMarkers[n] = addMarker(batchMapObj, n, ZONES[n]);
  }
  animFrameId = requestAnimationFrame(animLoop);
}

function openDetail(zoneName, data) {
  lastResult = data;
  var panel = qs("#detailPanel");
  var main = qs("#mainContent");
  panel.classList.add("active");
  main.classList.add("detail-open");
  qs("#detailTitle").textContent = zoneName;

  var pct = Math.round(data.congestion_score * 100);
  var hex = levelColor(data.congestion_level);
  var circ = 2 * Math.PI * 62;
  var off = circ * (1 - data.congestion_score);

  var fill = qs("#gaugeFill");
  fill.style.strokeDasharray = circ;
  fill.style.strokeDashoffset = circ;
  fill.style.stroke = hex;

  requestAnimationFrame(function() {
    fill.style.strokeDashoffset = off;
  });

  var numEl = qs("#gaugeNumber");
  numEl.style.color = hex;
  var cur = 0;
  var step = Math.max(1, Math.ceil(pct / 40));
  var iv = setInterval(function() {
    cur = Math.min(cur + step, pct);
    numEl.textContent = cur;
    if (cur >= pct) clearInterval(iv);
  }, 25);

  var badge = qs("#congestionBadge");
  badge.textContent = data.congestion_level;
  badge.style.background = hex;
  badge.style.color = "#0a0a0f";

  var z = ZONES[zoneName];
  qs("#detailMetrics").innerHTML =
    '<div class="metric-card"><div class="metric-card__icon">🚗</div><div class="metric-card__value">' + (z.baseVehicles + Math.floor(Math.random() * 40)) + ' <span>vehicles</span></div><div class="metric-card__label">Active Vehicles</div></div>'
    + '<div class="metric-card"><div class="metric-card__icon">⚡</div><div class="metric-card__value">' + Math.floor(z.speed * (1 - data.congestion_score * 0.5)) + ' <span>km/h</span></div><div class="metric-card__label">Avg Speed</div></div>'
    + '<div class="metric-card"><div class="metric-card__icon">🌤️</div><div class="metric-card__value">' + data.weather + '</div><div class="metric-card__label">Weather</div></div>'
    + '<div class="metric-card"><div class="metric-card__icon">🛣️</div><div class="metric-card__value">' + z.road + '</div><div class="metric-card__label">Road Type</div></div>';

  var tags = "";
  var features = ["Hour " + String(data.hour).padStart(2, "0") + ":00", z.road, data.weather];
  if (data.congestion_level === "Critical") features.push("sandstorm");
  for (var fi = 0; fi < features.length; fi++) {
    tags += '<span class="feature-tag active">' + features[fi] + '</span>';
  }
  tags += '<span class="feature-tag">XGBoost</span>';
  tags += '<span class="feature-tag">R² 0.89</span>';
  qs("#featureTags").innerHTML = tags;

  var bars = "";
  for (var h = 0; h < 24; h++) {
    var hm = HM[h];
    var hScore = Math.min(1, hm * data.congestion_score * 1.2 + Math.random() * 0.1);
    var hColor = hScore > 0.75 ? "var(--cong-critical)" : hScore > 0.55 ? "var(--cong-high)" : hScore > 0.30 ? "var(--cong-moderate)" : "var(--cong-low)";
    var isCurrent = h === data.hour ? " current" : "";
    bars += '<div class="forecast-bar' + isCurrent + '" style="height:' + Math.max(6, hScore * 80) + 'px;background:' + hColor + '"></div>';
  }
  qs("#forecastChart").innerHTML = bars;

  qs("#recCard").style.display = "block";
  qs("#recText").textContent = data.recommendation;
}

function closeDetail() {
  qs("#detailPanel").classList.remove("active");
  qs("#mainContent").classList.remove("detail-open");
  setTimeout(function() {
    if (mapObj) mapObj.invalidateSize();
  }, 400);
}

async function runPrediction(zoneName) {
  var z = ZONES[zoneName];
  if (!z) return;

  var hour = Number(qs("#pHour").value);
  var body = {
    city: "Riyadh", zone: zoneName, hour: hour,
    vehicle_count: z.baseVehicles + Math.floor(Math.random() * 60),
    avg_speed: z.speed * (0.5 + Math.random() * 0.3),
    weather: qs("#pWeather").value,
    road_type: z.road,
    rush_hour: (hour >= 7 && hour <= 9) || (hour >= 16 && hour <= 18) ? 1 : 0,
    is_weekend: qs("#pWeekend").checked ? 1 : 0,
    is_late_night: qs("#pLateNight").checked ? 1 : 0,
    event: qs("#pEvent").checked ? 1 : 0,
    hour_multiplier: HM[hour],
    friday_prayer_drop: qs("#pFridayPrayer").checked ? 1 : 0
  };

  try {
    var d = await apiPost("/predict", body);
    qs("#pZone").value = zoneName;
    mapObj.flyTo([z.lat, z.lng], 14, { duration: 0.8 });

    clearCars(carLayers, animList, mapObj);
    resetRoads(roadLines);
    updateMarkerStyle(districtMarkers[zoneName], d.congestion_score, d.congestion_level);

    for (var i = 0; i < roadLines.length; i++) {
      var ln = roadLines[i];
      if (ln.roadFrom === zoneName || ln.roadTo === zoneName) {
        activateRoad(ln, d.congestion_score, d.congestion_level);
        spawnCars(mapObj, ln, d.congestion_score, d.congestion_level, carLayers, animList);
      }
    }

    openDetail(zoneName, d);
  } catch (err) {
    openDetail(zoneName, {
      zone: zoneName, hour: body.hour, weather: body.weather,
      congestion_score: 0, congestion_level: "Low",
      recommendation: "Error: " + err.message
    });
  }
}

async function loadStatus() {
  try {
    var r = await fetch(API + "/health");
    var d = await r.json();
    var m = d.model_metrics || {};
    qs("#statusDot").classList.add("ok");
    qs("#statusText").textContent = "Connected";
    var r2v = m.r2 != null ? m.r2.toFixed(4) : "-";
    var rmv = m.rmse != null ? m.rmse.toFixed(4) : "-";
    qs("#modelInfo").innerHTML = "Model: XGBoost<br>R²: " + r2v + "<br>RMSE: " + rmv;
    qs("#statusGrid").innerHTML =
      '<div class="metric-card"><div class="metric-card__icon">🟢</div><div class="metric-card__value">Online</div><div class="metric-card__label">API Status</div></div>'
      + '<div class="metric-card"><div class="metric-card__icon">📈</div><div class="metric-card__value">' + r2v + '</div><div class="metric-card__label">R² Score</div></div>'
      + '<div class="metric-card"><div class="metric-card__icon">📉</div><div class="metric-card__value">' + rmv + '</div><div class="metric-card__label">RMSE</div></div>'
      + '<div class="metric-card"><div class="metric-card__icon">🧠</div><div class="metric-card__value">XGBoost</div><div class="metric-card__label">Model</div></div>';
  } catch (err) {
    qs("#statusDot").classList.add("error");
    qs("#statusText").textContent = "Offline";
    qs("#statusGrid").innerHTML = '<div class="panel-card"><p style="color:var(--error)">Cannot reach API at ' + API + '</p></div>';
  }
}

var navItems = qsAll(".nav-item");
for (var ni = 0; ni < navItems.length; ni++) {
  navItems[ni].addEventListener("click", function(e) {
    e.preventDefault();
    for (var x = 0; x < navItems.length; x++) navItems[x].classList.remove("active");
    this.classList.add("active");
    var sec = this.dataset.section;
    var secs = qsAll(".section");
    for (var y = 0; y < secs.length; y++) secs[y].classList.remove("active");
    qs("#section-" + sec).classList.add("active");
    qs("#sidebar").classList.remove("open");
    closeDetail();
    setTimeout(function() {
      if (mapObj) mapObj.invalidateSize();
      if (batchMapObj) batchMapObj.invalidateSize();
    }, 100);
  });
}

qs("#mobileToggle").addEventListener("click", function() {
  qs("#sidebar").classList.toggle("open");
});

qs("#detailClose").addEventListener("click", closeDetail);

qs("#resetViewBtn").addEventListener("click", function() {
  closeDetail();
  clearCars(carLayers, animList, mapObj);
  resetRoads(roadLines);
  mapObj.flyTo([24.6900, 46.6700], 12, { duration: 0.8 });
});

qs("#pHour").addEventListener("input", function(e) {
  var h = Number(e.target.value);
  qs("#hourBadge").textContent = String(h).padStart(2, "0") + ":00";
});

qs("#pZone").addEventListener("change", function() {
  var name = this.value;
  var z = ZONES[name];
  if (z && mapObj) mapObj.flyTo([z.lat, z.lng], 14, { duration: 0.8 });
});

qs("#predictBtn").addEventListener("click", function() {
  runPrediction(qs("#pZone").value);
});

qs("#batchBtn").addEventListener("click", async function() {
  var btn = qs("#batchBtn");
  setLoading(btn, true);
  var hour = Number(qs("#bHour").value);
  var weather = qs("#bWeather").value;
  var hm = HM[hour];
  var rush = (hour >= 7 && hour <= 9) || (hour >= 16 && hour <= 18) ? 1 : 0;
  var names = Object.keys(ZONES);
  var preds = [];
  for (var i = 0; i < names.length; i++) {
    var n = names[i];
    var z = ZONES[n];
    preds.push({
      city: "Riyadh", zone: n, hour: hour,
      vehicle_count: z.baseVehicles, avg_speed: z.speed * 0.7,
      weather: weather, road_type: z.road, rush_hour: rush,
      is_weekend: 0, is_late_night: 0, event: 0,
      hour_multiplier: hm, friday_prayer_drop: 0
    });
  }
  try {
    var data = await apiPost("/predict/batch", { predictions: preds });
    var rows = "";
    for (var j = 0; j < data.results.length; j++) {
      var r = data.results[j];
      rows += '<tr><td>' + r.zone + '</td><td style="color:' + levelColor(r.congestion_level) + ';font-family:var(--font-mono);font-weight:600">' + (r.congestion_score * 100).toFixed(1) + '%</td><td><span style="color:' + levelColor(r.congestion_level) + '">' + r.congestion_level + '</span></td><td style="color:var(--text-secondary);font-size:.85rem">' + r.recommendation + '</td></tr>';
    }
    qs("#batchResults").innerHTML = '<table style="width:100%;border-collapse:collapse;font-size:.85rem"><thead><tr style="text-align:left;border-bottom:1px solid var(--border-default)"><th style="padding:10px;color:var(--text-tertiary);font-size:.75rem;text-transform:uppercase">District</th><th style="padding:10px;color:var(--text-tertiary);font-size:.75rem;text-transform:uppercase">Score</th><th style="padding:10px;color:var(--text-tertiary);font-size:.75rem;text-transform:uppercase">Level</th><th style="padding:10px;color:var(--text-tertiary);font-size:.75rem;text-transform:uppercase">Recommendation</th></tr></thead><tbody>' + rows + '</tbody></table>';

    var scores = {};
    for (var k = 0; k < data.results.length; k++) scores[data.results[k].zone] = data.results[k];
    for (var l = 0; l < data.results.length; l++) {
      var rd = data.results[l];
      if (batchDistrictMarkers[rd.zone]) updateMarkerStyle(batchDistrictMarkers[rd.zone], rd.congestion_score, rd.congestion_level);
    }
    clearCars(batchCarLayers, batchAnimList, batchMapObj);
    for (var m = 0; m < batchRoadLines.length; m++) {
      var ln = batchRoadLines[m];
      var fd = scores[ln.roadFrom];
      var td = scores[ln.roadTo];
      if (fd && td) {
        var avg = (fd.congestion_score + td.congestion_score) / 2;
        var lvl = avg > 0.75 ? "Critical" : avg > 0.55 ? "High" : avg > 0.30 ? "Moderate" : "Low";
        activateRoad(ln, avg, lvl);
        spawnCars(batchMapObj, ln, avg, lvl, batchCarLayers, batchAnimList);
      }
    }
  } catch (err) {
    qs("#batchResults").innerHTML = '<p style="color:var(--error)">' + err.message + '</p>';
  } finally {
    setLoading(btn, false);
  }
});

(function() {
  var overlay = qs("#loadingOverlay");
  var bar = qs("#loadBar");
  var attempts = 0;
  var maxAttempts = 60;
  initAll();

  var poll = setInterval(async function() {
    attempts++;
    bar.style.width = Math.min(90, attempts * 1.5) + "%";
    try {
      var r = await fetch(API + "/health");
      if (r.ok) {
        var data = await r.json();
        if (data.model_loaded) {
          bar.style.width = "100%";
          var m = data.model_metrics || {};
          qs("#loadMetrics").innerHTML = '<span>R²: ' + (m.r2 ? m.r2.toFixed(4) : '-') + '</span><span>RMSE: ' + (m.rmse ? m.rmse.toFixed(4) : '-') + '</span>';
          setTimeout(function() {
            overlay.hidden = true;
            clearInterval(poll);
            loadStatus();
          }, 500);
        }
      }
    } catch (err) { }
    if (attempts >= maxAttempts) {
      clearInterval(poll);
      overlay.innerHTML = '<div class="loading-card"><h3 style="color:var(--error)">Connection Timeout</h3><p>Could not reach the API at ' + API + '</p></div>';
    }
  }, 1000);
})();
