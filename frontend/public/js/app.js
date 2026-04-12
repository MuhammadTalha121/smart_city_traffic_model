/* ── Config ──────────────────────────────────────────────────────────────── */

var API = "/api";

/* ── Riyadh districts ────────────────────────────────────────────────────── */

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

/* ── Road paths with real waypoints ──────────────────────────────────────── */

var ROADS = [
  {
    name: "Olaya → Sulaimaniyah", type: "arterial", from: "Olaya", to: "Sulaimaniyah",
    path: [
      [24.6900, 46.6850], [24.6920, 46.6820], [24.6940, 46.6780],
      [24.6960, 46.6750], [24.6980, 46.6720], [24.7000, 46.6700]
    ]
  },
  {
    name: "Olaya → Al-Malaz", type: "highway", from: "Olaya", to: "Al-Malaz",
    path: [
      [24.6900, 46.6850], [24.6880, 46.6900], [24.6860, 46.6960],
      [24.6840, 46.7020], [24.6820, 46.7080], [24.6800, 46.7140],
      [24.6780, 46.7190], [24.6760, 46.7230], [24.6750, 46.7250]
    ]
  },
  {
    name: "Olaya → KAFD", type: "highway", from: "Olaya", to: "King Abdullah Financial Dist",
    path: [
      [24.6900, 46.6850], [24.6940, 46.6820], [24.6980, 46.6780],
      [24.7040, 46.6740], [24.7100, 46.6700], [24.7180, 46.6650],
      [24.7260, 46.6600], [24.7340, 46.6550], [24.7420, 46.6500],
      [24.7500, 46.6470], [24.7580, 46.6440], [24.7630, 46.6420],
      [24.7680, 46.6400]
    ]
  },
  {
    name: "Al-Malaz → Al-Rawdah", type: "arterial", from: "Al-Malaz", to: "Al-Rawdah",
    path: [
      [24.6750, 46.7250], [24.6800, 46.7240], [24.6860, 46.7230],
      [24.6930, 46.7220], [24.7000, 46.7210], [24.7080, 46.7200],
      [24.7160, 46.7190], [24.7240, 46.7180], [24.7300, 46.7160],
      [24.7350, 46.7150]
    ]
  },
  {
    name: "Al-Malaz → Al-Naseem", type: "arterial", from: "Al-Malaz", to: "Al-Naseem",
    path: [
      [24.6750, 46.7250], [24.6720, 46.7280], [24.6690, 46.7310],
      [24.6660, 46.7340], [24.6620, 46.7370], [24.6580, 46.7390],
      [24.6550, 46.7400]
    ]
  },
  {
    name: "Al-Malaz → Al-Batha", type: "collector", from: "Al-Malaz", to: "Al-Batha",
    path: [
      [24.6750, 46.7250], [24.6720, 46.7220], [24.6680, 46.7190],
      [24.6640, 46.7160], [24.6600, 46.7130], [24.6560, 46.7100],
      [24.6510, 46.7070], [24.6450, 46.7050]
    ]
  },
  {
    name: "Al-Rawdah → KAFD", type: "highway", from: "Al-Rawdah", to: "King Abdullah Financial Dist",
    path: [
      [24.7350, 46.7150], [24.7380, 46.7100], [24.7420, 46.7040],
      [24.7460, 46.6970], [24.7500, 46.6900], [24.7540, 46.6820],
      [24.7570, 46.6720], [24.7600, 46.6620], [24.7630, 46.6520],
      [24.7660, 46.6460], [24.7680, 46.6400]
    ]
  },
  {
    name: "Al-Naseem → Al-Shemaysi", type: "residential", from: "Al-Naseem", to: "Al-Shemaysi",
    path: [
      [24.6550, 46.7400], [24.6520, 46.7360], [24.6480, 46.7320],
      [24.6440, 46.7260], [24.6400, 46.7200], [24.6370, 46.7150],
      [24.6350, 46.7100]
    ]
  },
  {
    name: "Al-Naseem → Al-Batha", type: "collector", from: "Al-Naseem", to: "Al-Batha",
    path: [
      [24.6550, 46.7400], [24.6530, 46.7360], [24.6510, 46.7320],
      [24.6490, 46.7270], [24.6470, 46.7210], [24.6460, 46.7150],
      [24.6450, 46.7100], [24.6450, 46.7050]
    ]
  },
  {
    name: "Al-Batha → Al-Shemaysi", type: "residential", from: "Al-Batha", to: "Al-Shemaysi",
    path: [
      [24.6450, 46.7050], [24.6430, 46.7070], [24.6400, 46.7080],
      [24.6380, 46.7090], [24.6350, 46.7100]
    ]
  },
  {
    name: "Sulaimaniyah → Diplomatic Quarter", type: "arterial", from: "Sulaimaniyah", to: "Diplomatic Quarter",
    path: [
      [24.7000, 46.6700], [24.7010, 46.6650], [24.7020, 46.6600],
      [24.7030, 46.6540], [24.7035, 46.6480], [24.7040, 46.6400],
      [24.7042, 46.6320], [24.7045, 46.6240], [24.7048, 46.6160],
      [24.7050, 46.6080], [24.7050, 46.6000], [24.7050, 46.5920],
      [24.7050, 46.5850]
    ]
  },
  {
    name: "KAFD → Diplomatic Quarter", type: "highway", from: "King Abdullah Financial Dist", to: "Diplomatic Quarter",
    path: [
      [24.7680, 46.6400], [24.7620, 46.6360], [24.7550, 46.6320],
      [24.7480, 46.6280], [24.7400, 46.6240], [24.7320, 46.6200],
      [24.7240, 46.6160], [24.7160, 46.6120], [24.7100, 46.6040],
      [24.7070, 46.5950], [24.7050, 46.5850]
    ]
  },
  {
    name: "KAFD → Al-Rawdah", type: "arterial", from: "King Abdullah Financial Dist", to: "Al-Rawdah",
    path: [
      [24.7680, 46.6400], [24.7620, 46.6480], [24.7560, 46.6560],
      [24.7500, 46.6640], [24.7440, 46.6720], [24.7400, 46.6820],
      [24.7370, 46.6920], [24.7360, 46.7020], [24.7350, 46.7150]
    ]
  },
  {
    name: "Diriyah → Diplomatic Quarter", type: "collector", from: "Diriyah", to: "Diplomatic Quarter",
    path: [
      [24.7320, 46.5740], [24.7280, 46.5760], [24.7240, 46.5780],
      [24.7200, 46.5800], [24.7160, 46.5820], [24.7120, 46.5830],
      [24.7080, 46.5840], [24.7050, 46.5850]
    ]
  },
  {
    name: "Diriyah → Sulaimaniyah", type: "highway", from: "Diriyah", to: "Sulaimaniyah",
    path: [
      [24.7320, 46.5740], [24.7310, 46.5820], [24.7300, 46.5920],
      [24.7280, 46.6020], [24.7250, 46.6120], [24.7220, 46.6220],
      [24.7180, 46.6320], [24.7140, 46.6420], [24.7100, 46.6500],
      [24.7060, 46.6580], [24.7020, 46.6640], [24.7000, 46.6700]
    ]
  }
];

/* ── Road type styling ───────────────────────────────────────────────────── */

var ROAD_STYLE = {
  highway:     { weight: 5, opacity: 0.45, dash: null },
  arterial:    { weight: 4, opacity: 0.40, dash: null },
  collector:   { weight: 3, opacity: 0.35, dash: null },
  residential: { weight: 2, opacity: 0.30, dash: "6,8" }
};

var ROAD_STYLE_ACTIVE = {
  highway:     { weight: 10, opacity: 0.85 },
  arterial:    { weight: 8,  opacity: 0.80 },
  collector:   { weight: 6,  opacity: 0.75 },
  residential: { weight: 5,  opacity: 0.70 }
};

/* ── Hourly multipliers ──────────────────────────────────────────────────── */

var HM = {
  0:.15, 1:.10, 2:.08, 3:.07, 4:.08, 5:.15, 6:.45, 7:1.00, 8:1.40, 9:1.20,
  10:.90, 11:.85, 12:.60, 13:.95, 14:1.00, 15:1.10, 16:1.30, 17:1.50,
  18:1.35, 19:1.10, 20:.85, 21:.70, 22:.50, 23:.30
};

/* ── Helpers ─────────────────────────────────────────────────────────────── */

var qs = function(s) { return document.querySelector(s); };
var qsAll = function(s) { return document.querySelectorAll(s); };

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

function setLoading(btn, on) {
  btn.disabled = on;
  btn.querySelector(".btn__text").hidden = on;
  btn.querySelector(".btn__loader").hidden = !on;
}

function levelColor(l) {
  var c = { Low: "#4ade80", Moderate: "#facc15", High: "#fb923c", Critical: "#f87171" };
  return c[l] || "#d4a574";
}

/* ── SVG car icon ────────────────────────────────────────────────────────── */

function carSVG(color) {
  return '<svg width="20" height="10" viewBox="0 0 20 10" xmlns="http://www.w3.org/2000/svg">' +
    '<rect x="1" y="4" width="18" height="5" rx="2.5" fill="' + color + '"/>' +
    '<rect x="4" y="1" width="12" height="5" rx="2" fill="' + color + '" opacity="0.85"/>' +
    '<rect x="5.5" y="2" width="3.5" height="2.5" rx="0.8" fill="rgba(180,220,255,0.35)"/>' +
    '<rect x="11" y="2" width="3.5" height="2.5" rx="0.8" fill="rgba(180,220,255,0.35)"/>' +
    '<circle cx="5" cy="9" r="1.8" fill="#222"/>' +
    '<circle cx="15" cy="9" r="1.8" fill="#222"/>' +
    '<circle cx="5" cy="9" r="0.8" fill="#555"/>' +
    '<circle cx="15" cy="9" r="0.8" fill="#555"/>' +
    '<rect x="0" y="5" width="1.5" height="1.5" rx="0.5" fill="rgba(255,200,50,0.7)"/>' +
    '<rect x="18.5" y="5" width="1.5" height="1.5" rx="0.5" fill="rgba(255,50,50,0.7)"/>' +
    '</svg>';
}

function truckSVG(color) {
  return '<svg width="28" height="11" viewBox="0 0 28 11" xmlns="http://www.w3.org/2000/svg">' +
    '<rect x="0" y="2" width="16" height="7" rx="1.5" fill="' + color + '" opacity="0.85"/>' +
    '<rect x="16" y="3" width="10" height="6" rx="2" fill="' + color + '"/>' +
    '<rect x="18" y="4" width="6" height="3" rx="1" fill="rgba(180,220,255,0.3)"/>' +
    '<circle cx="5" cy="9.5" r="1.8" fill="#222"/>' +
    '<circle cx="12" cy="9.5" r="1.8" fill="#222"/>' +
    '<circle cx="22" cy="9.5" r="1.8" fill="#222"/>' +
    '<rect x="0" y="4" width="1.5" height="1.5" rx="0.5" fill="rgba(255,200,50,0.7)"/>' +
    '</svg>';
}

/* ── Map state ───────────────────────────────────────────────────────────── */

var map = null;
var batchMap = null;
var districtMarkers = {};
var batchDistrictMarkers = {};
var roadPolylines = [];
var batchRoadPolylines = [];
var carLayers = [];
var batchCarLayers = [];
var labelOverlays = {};
var activeAnimations = [];
var batchActiveAnimations = [];

/* ── Create district marker ──────────────────────────────────────────────── */

function createDistrictMarker(targetMap, name, data) {
  var marker = L.circleMarker([data.lat, data.lng], {
    radius: 14,
    fillColor: "#3a3a42",
    fillOpacity: 0.8,
    color: "#5a5a64",
    weight: 2
  }).addTo(targetMap);

  marker.bindPopup(
    '<div class="zone-popup">' +
      '<h3>' + name + '</h3>' +
      '<div class="popup-score" style="color:#6b6560">—</div>' +
      '<div class="popup-level" style="color:#6b6560">No data</div>' +
      '<div class="popup-meta">' + data.road + ' · ' + data.speed + ' km/h</div>' +
    '</div>',
    { closeButton: true, offset: [0, -10] }
  );

  marker.zoneName = name;
  return marker;
}

/* ── Add district labels ─────────────────────────────────────────────────── */

function addDistrictLabels(targetMap) {
  var mapId = targetMap._container.id;
  labelOverlays[mapId] = {};
  var names = Object.keys(ZONES);
  for (var i = 0; i < names.length; i++) {
    var name = names[i];
    var z = ZONES[name];
    var icon = L.divIcon({
      className: "district-label",
      html: name,
      iconSize: [140, 16],
      iconAnchor: [70, -14]
    });
    var label = L.marker([z.lat, z.lng], { icon: icon, interactive: false }).addTo(targetMap);
    labelOverlays[mapId][name] = label;
  }
}

/* ── Draw roads ──────────────────────────────────────────────────────────── */

function drawRoads(targetMap, roadArray) {
  for (var i = 0; i < ROADS.length; i++) {
    var road = ROADS[i];
    var cfg = ROAD_STYLE[road.type] || ROAD_STYLE.collector;

    var line = L.polyline(road.path, {
      color: "#4a4a54",
      weight: cfg.weight,
      opacity: cfg.opacity,
      dashArray: cfg.dash,
      lineCap: "round",
      lineJoin: "round"
    }).addTo(targetMap);

    line.roadIndex = i;
    line.roadFrom = road.from;
    line.roadTo = road.to;
    line.roadType = road.type;
    line.roadName = road.name;
    line.isActive = false;
    roadArray.push(line);
  }
}

/* ── Activate a road (widen + glow) ──────────────────────────────────────── */

function activateRoad(line, score, level) {
  var color = levelColor(level);
  var cfg = ROAD_STYLE_ACTIVE[line.roadType] || ROAD_STYLE_ACTIVE.collector;

  line.isActive = true;
  line.setStyle({
    color: color,
    weight: cfg.weight,
    opacity: cfg.opacity,
    dashArray: null
  });

  // Add glow layer behind
  if (!line._glowLine) {
    var glow = L.polyline(line.getLatLngs(), {
      color: color,
      weight: cfg.weight + 8,
      opacity: 0.15,
      lineCap: "round",
      lineJoin: "round"
    });
    line._glowLine = glow;
  }
  line._glowLine.setStyle({ color: color, opacity: 0.15, weight: cfg.weight + 8 });
  line._glowLine.addTo(line._map);
}

/* ── Deactivate a road ───────────────────────────────────────────────────── */

function deactivateRoad(line) {
  var cfg = ROAD_STYLE[line.roadType] || ROAD_STYLE.collector;
  line.isActive = false;
  line.setStyle({
    color: "#4a4a54",
    weight: cfg.weight,
    opacity: cfg.opacity,
    dashArray: cfg.dash
  });
  if (line._glowLine && line._map) {
    line._map.removeLayer(line._glowLine);
  }
}

/* ── Calculate bearing between two points ────────────────────────────────── */

function bearing(lat1, lng1, lat2, lng2) {
  var dLng = (lng2 - lng1) * Math.PI / 180;
  var lat1R = lat1 * Math.PI / 180;
  var lat2R = lat2 * Math.PI / 180;
  var y = Math.sin(dLng) * Math.cos(lat2R);
  var x = Math.cos(lat1R) * Math.sin(lat2R) - Math.sin(lat1R) * Math.cos(lat2R) * Math.cos(dLng);
  return Math.atan2(y, x) * 180 / Math.PI;
}

/* ── Spawn cars on road with requestAnimationFrame ───────────────────────── */

function spawnCars(targetMap, roadLine, score, level, carArray, animArray) {
  var path = roadLine.getLatLngs();
  if (!path || path.length < 2) return;

  var color = levelColor(level);
  var isHighway = roadLine.roadType === "highway";
  var count = isHighway ? Math.max(5, Math.floor(score * 16)) : Math.max(3, Math.floor(score * 12));
  var speed = (0.3 + (1 - score) * 0.7) * (isHighway ? 1.4 : 1.0);

  // Calculate total path length
  var totalDist = 0;
  var segLengths = [];
  for (var s = 1; s < path.length; s++) {
    var d = Math.sqrt(Math.pow(path[s][0] - path[s-1][0], 2) + Math.pow(path[s][1] - path[s-1][1], 2));
    segLengths.push(d);
    totalDist += d;
  }

  for (var i = 0; i < count; i++) {
    var startProgress = (i / count) + (Math.random() * 0.05);
    if (startProgress > 1) startProgress -= 1;

    // Calculate initial position
    var pos = getPointOnPath(path, segLengths, totalDist, startProgress);
    var nextPos = getPointOnPath(path, segLengths, totalDist, startProgress + 0.001);
    var angle = bearing(pos[0], pos[1], nextPos[0], nextPos[1]);

    var icon = L.divIcon({
      className: "",
      html: '<div style="transform:rotate(' + angle + 'deg)">' +
        (isHighway ? truckSVG(color) : carSVG(color)) + '</div>',
      iconSize: isHighway ? [28, 11] : [20, 10],
      iconAnchor: isHighway ? [14, 5] : [10, 5]
    });

    var car = L.marker([pos[0], pos[1]], { icon: icon, interactive: false }).addTo(targetMap);
    carArray.push(car);

    // Start animation
    var anim = {
      marker: car,
      path: path,
      segLengths: segLengths,
      totalDist: totalDist,
      progress: startProgress,
      speed: speed * (0.0008 + Math.random() * 0.0004),
      isTruck: isHighway,
      color: color,
      direction: 1
    };
    animArray.push(anim);
  }
}

/* ── Get point at specific progress along path ───────────────────────────── */

function getPointOnPath(path, segLengths, totalDist, progress) {
  if (progress > 1) progress -= 1;
  if (progress < 0) progress += 1;

  var targetDist = progress * totalDist;
  var accDist = 0;

  for (var i = 0; i < segLengths.length; i++) {
    if (accDist + segLengths[i] >= targetDist) {
      var t = (targetDist - accDist) / segLengths[i];
      return [
        path[i][0] + (path[i+1][0] - path[i][0]) * t,
        path[i][1] + (path[i+1][1] - path[i][1]) * t
      ];
    }
    accDist += segLengths[i];
  }

  return [path[path.length - 1][0], path[path.length - 1][1]];
}

/* ── Animation loop ──────────────────────────────────────────────────────── */

var animFrameId = null;

function animationLoop() {
  // Process all active animations
  var allAnims = activeAnimations.concat(batchActiveAnimations);

  for (var i = 0; i < allAnims.length; i++) {
    var a = allAnims[i];
    a.progress += a.speed * a.direction;
    if (a.progress > 1) a.progress -= 1;
    if (a.progress < 0) a.progress += 1;

    var pos = getPointOnPath(a.path, a.segLengths, a.totalDist, a.progress);
    var nextPos = getPointOnPath(a.path, a.segLengths, a.totalDist, a.progress + 0.002 * a.direction);
    var angle = bearing(pos[0], pos[1], nextPos[0], nextPos[1]);

    a.marker.setLatLng([pos[0], pos[1]]);

    // Update rotation
    var icon = L.divIcon({
      className: "",
      html: '<div style="transform:rotate(' + angle + 'deg)">' +
        (a.isTruck ? truckSVG(a.color) : carSVG(a.color)) + '</div>',
      iconSize: a.isTruck ? [28, 11] : [20, 10],
      iconAnchor: a.isTruck ? [14, 5] : [10, 5]
    });
    a.marker.setIcon(icon);
  }

  animFrameId = requestAnimationFrame(animationLoop);
}

function startAnimationLoop() {
  if (!animFrameId) {
    animFrameId = requestAnimationFrame(animationLoop);
  }
}

function stopAnimationLoop() {
  if (animFrameId) {
    cancelAnimationFrame(animFrameId);
    animFrameId = null;
  }
}

/* ── Clear cars ──────────────────────────────────────────────────────────── */

function clearCars(carArray, animArray, targetMap) {
  for (var i = 0; i < carArray.length; i++) {
    if (targetMap) targetMap.removeLayer(carArray[i]);
  }
  carArray.length = 0;
  animArray.length = 0;
}

/* ── Reset all roads to default ──────────────────────────────────────────── */

function resetRoads(roadArray) {
  for (var i = 0; i < roadArray.length; i++) {
    deactivateRoad(roadArray[i]);
  }
}

/* ── Update district marker ──────────────────────────────────────────────── */

function updateDistrictMarker(marker, score, level) {
  var color = levelColor(level);
  var radius = 10 + score * 14;

  marker.setStyle({
    radius: radius,
    fillColor: color,
    fillOpacity: 0.5 + score * 0.3,
    color: color,
    weight: 2.5,
    opacity: 0.9
  });

  marker.setPopupContent(
    '<div class="zone-popup">' +
      '<h3>' + marker.zoneName + '</h3>' +
      '<div class="popup-score" style="color:' + color + '">' + Math.round(score * 100) + '%</div>' +
      '<div class="popup-level" style="color:' + color + '">' + level + '</div>' +
      '<div class="popup-meta">' + ZONES[marker.zoneName].road + ' · ' + ZONES[marker.zoneName].speed + ' km/h</div>' +
    '</div>'
  );
}

/* ── Highlight label ─────────────────────────────────────────────────────── */

function highlightLabel(mapId, zoneName) {
  var labels = labelOverlays[mapId];
  if (!labels) return;
  var names = Object.keys(labels);
  for (var i = 0; i < names.length; i++) {
    var el = labels[names[i]].getElement();
    if (el) {
      var span = el.querySelector(".district-label");
      if (span) span.className = "district-label";
    }
  }
  if (labels[zoneName]) {
    var activeEl = labels[zoneName].getElement();
    if (activeEl) {
      var activeSpan = activeEl.querySelector(".district-label");
      if (activeSpan) activeSpan.className = "district-label district-label-active";
    }
  }
}

/* ── Init map ────────────────────────────────────────────────────────────── */

function initMapInstance(mapId) {
  var m = L.map(mapId, {
    center: [24.6900, 46.6700],
    zoom: 12,
    zoomControl: true,
    attributionControl: false
  });

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    subdomains: "abcd"
  }).addTo(m);

  return m;
}

/* ── Init all ────────────────────────────────────────────────────────────── */

function initAllMaps() {
  map = initMapInstance("map");
  batchMap = initMapInstance("batchMap");

  drawRoads(map, roadPolylines);
  drawRoads(batchMap, batchRoadPolylines);

  var names = Object.keys(ZONES);
  for (var i = 0; i < names.length; i++) {
    var name = names[i];
    districtMarkers[name] = createDistrictMarker(map, name, ZONES[name]);
    batchDistrictMarkers[name] = createDistrictMarker(batchMap, name, ZONES[name]);
  }

  addDistrictLabels(map);
  addDistrictLabels(batchMap);

  startAnimationLoop();
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

    setTimeout(function() {
      if (map) map.invalidateSize();
      if (batchMap) batchMap.invalidateSize();
    }, 100);
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

/* ── Zone selector ───────────────────────────────────────────────────────── */

qs("#pZone").addEventListener("change", function() {
  var name = this.value;
  var z = ZONES[name];
  if (z && map) {
    map.flyTo([z.lat, z.lng], 14, { duration: 0.8 });
    highlightLabel("map", name);
  }
});

/* ── Single prediction ───────────────────────────────────────────────────── */

qs("#predictForm").addEventListener("submit", async function(e) {
  e.preventDefault();
  var btn = qs("#predictBtn");
  setLoading(btn, true);

  var zoneName = qs("#pZone").value;
  var zone = ZONES[zoneName];

  var body = {
    city: "Riyadh",
    zone: zoneName,
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
    friday_prayer_drop: qs("#pFridayPrayer").checked ? 1 : 0
  };

  try {
    var d = await apiPost("/predict", body);
    renderResult(d);

    // Clear previous
    clearCars(carLayers, activeAnimations, map);
    resetRoads(roadPolylines);

    // Update selected district
    updateDistrictMarker(districtMarkers[zoneName], d.congestion_score, d.congestion_level);
    highlightLabel("map", zoneName);

    // Activate connected roads and spawn cars
    for (var i = 0; i < roadPolylines.length; i++) {
      var line = roadPolylines[i];
      if (line.roadFrom === zoneName || line.roadTo === zoneName) {
        activateRoad(line, d.congestion_score, d.congestion_level);
        spawnCars(map, line, d.congestion_score, d.congestion_level, carLayers, activeAnimations);
      }
    }

    map.flyTo([zone.lat, zone.lng], 14, { duration: 0.8 });
  } catch (err) {
    renderError(err.message);
  } finally {
    setLoading(btn, false);
  }
});

/* ── Render result ───────────────────────────────────────────────────────── */

function renderResult(d) {
  qs("#resultEmpty").hidden = true;
  var el = qs("#resultContent");
  el.hidden = false;

  var pct = Math.round(d.congestion_score * 100);
  var hex = levelColor(d.congestion_level);
  var circ = 2 * Math.PI * 55;
  var off = circ * (1 - d.congestion_score);

  el.innerHTML =
    '<div class="score-ring-wrap">' +
      '<div class="score-ring">' +
        '<svg viewBox="0 0 160 160">' +
          '<circle class="track" cx="80" cy="80" r="55"/>' +
          '<circle class="fill" cx="80" cy="80" r="55" ' +
            'stroke="' + hex + '" ' +
            'stroke-dasharray="' + circ + '" ' +
            'stroke-dashoffset="' + circ + '" ' +
            'style="transition:stroke-dashoffset 1.2s cubic-bezier(.4,0,.2,1)"/>' +
        '</svg>' +
        '<div class="score-val">' +
          '<span class="score-val__num" style="color:' + hex + '">0</span>' +
          '<span class="score-val__lbl">Congestion</span>' +
        '</div>' +
      '</div>' +
    '</div>' +
    '<div style="text-align:center">' +
      '<span class="level-badge ' + d.congestion_level + '">' + d.congestion_level + '</span>' +
    '</div>' +
    '<div class="result-meta">' +
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
      '<h3 style="color:var(--red)">Error</h3><p>' + msg + '</p>' +
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

  var hour = Number(qs("#bHour").value);
  var weather = qs("#bWeather").value;
  var hm = HM[hour];
  var rush = (hour >= 7 && hour <= 9) || (hour >= 16 && hour <= 18) ? 1 : 0;

  var zoneNames = Object.keys(ZONES);
  var predictions = zoneNames.map(function(name) {
    var z = ZONES[name];
    return {
      city: "Riyadh", zone: name, hour: hour,
      vehicle_count: z.baseVehicles, avg_speed: z.speed * 0.7,
      weather: weather, road_type: z.road, rush_hour: rush,
      is_weekend: 0, is_late_night: 0, event: 0,
      hour_multiplier: hm, friday_prayer_drop: 0
    };
  });

  try {
    var data = await apiPost("/predict/batch", { predictions: predictions });
    renderBatch(data.results);
    updateBatchMap(data.results);
  } catch (err) {
    qs("#batchResults").innerHTML =
      '<div class="rec-card" style="border-color:var(--red);background:var(--red-bg)">' +
        '<h3 style="color:var(--red)">Error</h3><p>' + err.message + '</p>' +
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
      '<td><span class="level-badge ' + r.congestion_level + '" style="font-size:.66rem;padding:3px 10px">' +
        r.congestion_level +
      '</span></td>' +
      '<td style="color:var(--text2);font-size:.76rem">' + r.recommendation + '</td>' +
    '</tr>';
  }).join("");

  qs("#batchResults").innerHTML =
    '<table class="batch-table">' +
      '<thead><tr><th>District</th><th>Score</th><th>Level</th><th>Recommendation</th></tr></thead>' +
      '<tbody>' + rows + '</tbody>' +
    '</table>';
}

function updateBatchMap(results) {
  var scores = {};
  for (var i = 0; i < results.length; i++) {
    scores[results[i].zone] = results[i];
  }

  for (var j = 0; j < results.length; j++) {
    var r = results[j];
    if (batchDistrictMarkers[r.zone]) {
      updateDistrictMarker(batchDistrictMarkers[r.zone], r.congestion_score, r.congestion_level);
    }
  }

  clearCars(batchCarLayers, batchActiveAnimations, batchMap);

  for (var k = 0; k < batchRoadPolylines.length; k++) {
    var line = batchRoadPolylines[k];
    var fromData = scores[line.roadFrom];
    var toData = scores[line.roadTo];
    if (fromData && toData) {
      var avgScore = (fromData.congestion_score + toData.congestion_score) / 2;
      var avgLevel = avgScore > 0.75 ? "Critical" : avgScore > 0.55 ? "High" : avgScore > 0.30 ? "Moderate" : "Low";
      activateRoad(line, avgScore, avgLevel);
      spawnCars(batchMap, line, avgScore, avgLevel, batchCarLayers, batchActiveAnimations);
    }
  }
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
        '<div class="status-card__icon" style="background:var(--accent-glow);color:var(--accent)">◈</div>' +
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
        '<div class="status-card__icon" style="background:var(--accent-glow);color:var(--accent)">⊞</div>' +
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

  initAllMaps();

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
      /* not ready */
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
