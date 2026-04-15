/* ── Config ──────────────────────────────────────────────────────────────── */
const API = "/api";
const ZONES = {
  "Olaya": { lat: 24.6900, lng: 46.6850, baseVehicles: 280, speed: 60, road: "arterial" },
  "Al-Malaz": { lat: 24.6750, lng: 46.7250, baseVehicles: 240, speed: 50, road: "arterial" },
  "Sulaimaniyah": { lat: 24.7000, lng: 46.6700, baseVehicles: 200, speed: 45, road: "collector" },
  "Al-Rawdah": { lat: 24.7350, lng: 46.7150, baseVehicles: 220, speed: 50, road: "arterial" },
  "Al-Naseem": { lat: 24.6550, lng: 46.7400, baseVehicles: 260, speed: 55, road: "arterial" },
  "Al-Shemaysi": { lat: 24.6350, lng: 46.7100, baseVehicles: 190, speed: 40, road: "residential" },
  "Diriyah": { lat: 24.7320, lng: 46.5740, baseVehicles: 150, speed: 45, road: "collector" },
  "Al-Batha": { lat: 24.6450, lng: 46.7050, baseVehicles: 300, speed: 35, road: "arterial" },
  "King Abdullah Financial Dist": { lat: 24.7680, lng: 46.6400, baseVehicles: 310, speed: 60, road: "highway" },
  "Diplomatic Quarter": { lat: 24.7050, lng: 46.5850, baseVehicles: 160, speed: 55, road: "arterial" }
};

// Road connections with waypoints for smooth curves
const ROADS = [
  { from: "Olaya", to: "Sulaimaniyah", type: "arterial", waypoints: [[24.6900,46.6850],[24.6920,46.6820],[24.6940,46.6780],[24.6960,46.6750],[24.6980,46.6720],[24.7000,46.6700]] },
  { from: "Olaya", to: "Al-Malaz", type: "highway", waypoints: [[24.6900,46.6850],[24.6880,46.6900],[24.6860,46.6960],[24.6840,46.7020],[24.6820,46.7080],[24.6800,46.7140],[24.6780,46.7190],[24.6760,46.7230],[24.6750,46.7250]] },
  { from: "Olaya", to: "King Abdullah Financial Dist", type: "highway", waypoints: [[24.6900,46.6850],[24.6940,46.6820],[24.6980,46.6780],[24.7040,46.6740],[24.7100,46.6700],[24.7180,46.6650],[24.7260,46.6600],[24.7340,46.6550],[24.7420,46.6500],[24.7500,46.6470],[24.7580,46.6440],[24.7630,46.6420],[24.7680,46.6400]] },
  { from: "Al-Malaz", to: "Al-Rawdah", type: "arterial", waypoints: [[24.6750,46.7250],[24.6800,46.7240],[24.6860,46.7230],[24.6930,46.7220],[24.7000,46.7210],[24.7080,46.7200],[24.7160,46.7190],[24.7240,46.7180],[24.7300,46.7160],[24.7350,46.7150]] },
  { from: "Al-Malaz", to: "Al-Naseem", type: "arterial", waypoints: [[24.6750,46.7250],[24.6720,46.7280],[24.6690,46.7310],[24.6660,46.7340],[24.6620,46.7370],[24.6580,46.7390],[24.6550,46.7400]] },
  { from: "Al-Malaz", to: "Al-Batha", type: "collector", waypoints: [[24.6750,46.7250],[24.6720,46.7220],[24.6680,46.7190],[24.6640,46.7160],[24.6600,46.7130],[24.6560,46.7100],[24.6510,46.7070],[24.6450,46.7050]] },
  { from: "Al-Rawdah", to: "King Abdullah Financial Dist", type: "highway", waypoints: [[24.7350,46.7150],[24.7380,46.7100],[24.7420,46.7040],[24.7460,46.6970],[24.7500,46.6900],[24.7540,46.6820],[24.7570,46.6720],[24.7600,46.6620],[24.7630,46.6520],[24.7660,46.6460],[24.7680,46.6400]] },
  { from: "Al-Naseem", to: "Al-Shemaysi", type: "residential", waypoints: [[24.6550,46.7400],[24.6520,46.7360],[24.6480,46.7320],[24.6440,46.7260],[24.6400,46.7200],[24.6370,46.7150],[24.6350,46.7100]] },
  { from: "Al-Naseem", to: "Al-Batha", type: "collector", waypoints: [[24.6550,46.7400],[24.6530,46.7360],[24.6510,46.7320],[24.6490,46.7270],[24.6470,46.7210],[24.6460,46.7150],[24.6450,46.7100],[24.6450,46.7050]] },
  { from: "Al-Batha", to: "Al-Shemaysi", type: "residential", waypoints: [[24.6450,46.7050],[24.6430,46.7070],[24.6400,46.7080],[24.6380,46.7090],[24.6350,46.7100]] },
  { from: "Sulaimaniyah", to: "Diplomatic Quarter", type: "arterial", waypoints: [[24.7000,46.6700],[24.7010,46.6650],[24.7020,46.6600],[24.7030,46.6540],[24.7035,46.6480],[24.7040,46.6400],[24.7042,46.6320],[24.7045,46.6240],[24.7048,46.6160],[24.7050,46.6080],[24.7050,46.6000],[24.7050,46.5920],[24.7050,46.5850]] },
  { from: "King Abdullah Financial Dist", to: "Diplomatic Quarter", type: "highway", waypoints: [[24.7680,46.6400],[24.7620,46.6360],[24.7550,46.6320],[24.7480,46.6280],[24.7400,46.6240],[24.7320,46.6200],[24.7240,46.6160],[24.7160,46.6120],[24.7100,46.6040],[24.7070,46.5950],[24.7050,46.5850]] },
  { from: "King Abdullah Financial Dist", to: "Al-Rawdah", type: "arterial", waypoints: [[24.7680,46.6400],[24.7620,46.6480],[24.7560,46.6560],[24.7500,46.6640],[24.7440,46.6720],[24.7400,46.6820],[24.7370,46.6920],[24.7360,46.7020],[24.7350,46.7150]] },
  { from: "Diriyah", to: "Diplomatic Quarter", type: "collector", waypoints: [[24.7320,46.5740],[24.7280,46.5760],[24.7240,46.5780],[24.7200,46.5800],[24.7160,46.5820],[24.7120,46.5830],[24.7080,46.5840],[24.7050,46.5850]] },
  { from: "Diriyah", to: "Sulaimaniyah", type: "highway", waypoints: [[24.7320,46.5740],[24.7310,46.5820],[24.7300,46.5920],[24.7280,46.6020],[24.7250,46.6120],[24.7220,46.6220],[24.7180,46.6320],[24.7140,46.6420],[24.7100,46.6500],[24.7060,46.6580],[24.7020,46.6640],[24.7000,46.6700]] }
];

const HM = {
  0:0.15,1:0.10,2:0.08,3:0.07,4:0.08,5:0.15,6:0.45,7:1.00,8:1.40,9:1.20,
  10:0.90,11:0.85,12:0.60,13:0.95,14:1.00,15:1.10,16:1.30,17:1.50,
  18:1.35,19:1.10,20:0.85,21:0.70,22:0.50,23:0.30
};

/* ── State ───────────────────────────────────────────────────────────────── */
let map, batchMap;
let districtMarkers = {};
let roadLines = [];
let activeCars = [];
let simulationInterval = null;
let currentDetailDistrict = null;

/* ── Helpers ─────────────────────────────────────────────────────────────── */
const qs = s => document.querySelector(s);
const qsa = s => document.querySelectorAll(s);

function levelColor(level) {
  const colors = {
    Low: "#00ff88",
    Moderate: "#ffcc00", 
    High: "#ff8844",
    Critical: "#ff4444"
  };
  return colors[level] || "#00d4ff";
}

function levelBg(level) {
  const bgs = {
    Low: "rgba(0,255,136,0.15)",
    Moderate: "rgba(255,204,0,0.15)",
    High: "rgba(255,136,68,0.15)",
    Critical: "rgba(255,68,68,0.15)"
  };
  return bgs[level] || "rgba(0,212,255,0.15)";
}

function weatherIcon(weather) {
  const icons = {
    clear: "☀️",
    rain: "🌧️",
    fog: "🌫️",
    sandstorm: "🌪️"
  };
  return icons[weather] || "☀️";
}

function roadTypeLabel(type) {
  const labels = {
    highway: "Highway",
    arterial: "Arterial",
    collector: "Collector",
    residential: "Residential"
  };
  return labels[type] || type;
}

/* ── Car SVG ─────────────────────────────────────────────────────────────── */
function getCarSVG(color, isTruck = false) {
  if (isTruck) {
    return `<svg viewBox="0 0 28 12" style="filter:drop-shadow(0 2px 4px rgba(0,0,0,0.6))">
      <rect x="0" y="2" width="16" height="7" rx="1.5" fill="${color}"/>
      <rect x="16" y="3" width="10" height="6" rx="2" fill="${color}"/>
      <rect x="18" y="4" width="6" height="3" rx="1" fill="rgba(200,230,255,0.4)"/>
      <circle cx="5" cy="9.5" r="1.5" fill="#333"/>
      <circle cx="12" cy="9.5" r="1.5" fill="#333"/>
      <circle cx="22" cy="9.5" r="1.5" fill="#333"/>
      <rect x="-2" y="3" width="3" height="2" rx="0.5" fill="rgba(255,200,100,0.9)"/>
      <rect x="26" y="4" width="2" height="3" rx="0.5" fill="rgba(255,50,50,0.9)"/>
    </svg>`;
  }
  return `<svg viewBox="0 0 20 10" style="filter:drop-shadow(0 2px 4px rgba(0,0,0,0.6))">
    <rect x="1" y="3" width="18" height="5" rx="2.5" fill="${color}"/>
    <rect x="4" y="1" width="12" height="5" rx="2" fill="${color}" opacity="0.9"/>
    <rect x="5" y="2" width="4" height="2.5" rx="0.8" fill="rgba(200,230,255,0.4)"/>
    <rect x="11" y="2" width="4" height="2.5" rx="0.8" fill="rgba(200,230,255,0.4)"/>
    <circle cx="5" cy="8.5" r="1.5" fill="#333"/>
    <circle cx="15" cy="8.5" r="1.5" fill="#333"/>
    <rect x="-1" y="4" width="2" height="1.5" rx="0.3" fill="rgba(255,200,100,0.9)"/>
    <rect x="18" y="4" width="2" height="1.5" rx="0.3" fill="rgba(255,50,50,0.9)"/>
  </svg>`;
}

/* ── Initialize Maps ─────────────────────────────────────────────────────── */
function initMap() {
  map = L.map('map', {
    center: [24.6950, 46.6750],
    zoom: 12,
    zoomControl: false,
    attributionControl: false
  });

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    subdomains: 'abcd'
  }).addTo(map);

  L.control.zoom({ position: 'bottomright' }).addTo(map);

  // Add districts
  Object.entries(ZONES).forEach(([name, data]) => {
    const marker = L.circleMarker([data.lat, data.lng], {
      radius: 12,
      fillColor: "#00d4ff",
      fillOpacity: 0.6,
      color: "#fff",
      weight: 2,
      className: "district-marker"
    }).addTo(map);

    marker.bindTooltip(name, {
      permanent: true,
      direction: "top",
      offset: [0, -10],
      className: "district-label"
    });

    marker.on('click', () => openDistrictDetail(name));
    districtMarkers[name] = marker;
  });

  // Add roads
  ROADS.forEach(road => {
    const line = L.polyline(road.waypoints, {
      color: "#40404a",
      weight: road.type === 'highway' ? 4 : road.type === 'arterial' ? 3 : 2,
      opacity: 0.6,
      dashArray: road.type === 'residential' ? '5,10' : null,
      className: "road-line"
    }).addTo(map);
    
    line.roadData = road;
    roadLines.push(line);
  });

  // Batch map
  batchMap = L.map('batchMap', {
    center: [24.6950, 46.6750],
    zoom: 11,
    attributionControl: false
  });
  
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    subdomains: 'abcd'
  }).addTo(batchMap);
}

/* ── District Detail View ────────────────────────────────────────────────── */
async function openDistrictDetail(districtName) {
  currentDetailDistrict = districtName;
  const zone = ZONES[districtName];
  
  // Zoom map
  map.flyTo([zone.lat, zone.lng], 16, { duration: 1.5 });
  
  // Show panel
  const panel = qs('#detailPanel');
  const main = qs('.main');
  panel.classList.add('active');
  main.classList.add('detail-open');
  
  // Update basic info
  qs('#detailTitle').textContent = districtName;
  qs('#detailRoadType').textContent = roadTypeLabel(zone.road);
  qs('#speedLimit').textContent = zone.speed;
  
  // Simulate API call for demo (replace with real API)
  const mockData = await fetchDistrictData(districtName);
  
  // Update metrics
  updateDetailMetrics(mockData);
  
  // Start car simulation
  startCarSimulation(districtName, mockData.congestion_level);
  
  // Generate forecast
  generateForecast(districtName);
}

function closeDistrictDetail() {
  const panel = qs('#detailPanel');
  const main = qs('.main');
  panel.classList.remove('active');
  main.classList.remove('detail-open');
  
  // Reset view
  map.flyTo([24.6950, 46.6750], 12, { duration: 1 });
  stopCarSimulation();
  currentDetailDistrict = null;
}

async function fetchDistrictData(district) {
  // Replace with actual API call
  const hour = parseInt(qs('#pHour').value) || 8;
  const weather = qs('#pWeather').value || 'clear';
  
  // Simulate response
  const baseScore = Math.random() * 0.6 + 0.2;
  const level = baseScore < 0.3 ? "Low" : baseScore < 0.55 ? "Moderate" : baseScore < 0.75 ? "High" : "Critical";
  
  return {
    congestion_score: baseScore,
    congestion_level: level,
    vehicle_count: Math.floor(ZONES[district].baseVehicles * (0.8 + Math.random() * 0.4)),
    avg_speed: Math.floor(ZONES[district].speed * (0.6 + Math.random() * 0.4)),
    weather: weather,
    recommendation: getRecommendation(level, weather)
  };
}

function getRecommendation(level, weather) {
  const recs = {
    Low: "Traffic flowing smoothly. Optimal conditions for travel.",
    Moderate: "Expect minor delays. Consider alternative routes during peak hours.",
    High: "Heavy congestion detected. Use public transport if possible.",
    Critical: "Severe traffic jam. Avoid area. Use ring roads."
  };
  let rec = recs[level];
  if (weather === 'rain') rec += " Reduce speed due to wet conditions.";
  if (weather === 'sandstorm') rec += " Visibility severely limited. Drive with caution.";
  return rec;
}

function updateDetailMetrics(data) {
  const color = levelColor(data.congestion_level);
  const score = Math.round(data.congestion_score * 100);
  
  // Update gauge
  const fill = qs('#detailGaugeFill');
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (data.congestion_score * circumference);
  
  fill.style.strokeDashoffset = offset;
  fill.style.stroke = color;
  qs('#detailScore').textContent = score + '%';
  qs('#detailScore').style.color = color;
  
  // Level badge
  const levelBadge = qs('#detailLevel');
  levelBadge.textContent = data.congestion_level;
  levelBadge.style.background = levelBg(data.congestion_level);
  levelBadge.style.color = color;
  
  // Metrics
  qs('#detailVehicles').textContent = data.vehicle_count;
  qs('#detailSpeed').innerHTML = `${data.avg_speed} <span>km/h</span>`;
  qs('#detailWeather').textContent = data.weather.charAt(0).toUpperCase() + data.weather.slice(1);
  qs('#weatherIcon').textContent = weatherIcon(data.weather);
  qs('#detailRecText').textContent = data.recommendation;
  
  // Trends
  const normalSpeed = ZONES[currentDetailDistrict].speed;
  const speedDiff = Math.round(((data.avg_speed - normalSpeed) / normalSpeed) * 100);
  qs('#speedTrend').textContent = speedDiff > 0 ? `↑ ${speedDiff}% above normal` : `↓ ${Math.abs(speedDiff)}% below limit`;
  qs('#speedTrend').style.color = speedDiff < -20 ? 'var(--red)' : speedDiff < 0 ? 'var(--yellow)' : 'var(--green)';
  
  const vehicleTrend = Math.round((Math.random() - 0.5) * 30);
  qs('#vehicleTrend').textContent = vehicleTrend > 0 ? `↑ ${vehicleTrend}% vs normal` : `↓ ${Math.abs(vehicleTrend)}% vs normal`;
}

function generateForecast(district) {
  const container = qs('#forecastChart');
  container.innerHTML = '';
  const currentHour = parseInt(qs('#pHour').value) || 8;
  
  for (let i = 0; i < 24; i++) {
    const hour = (currentHour + i) % 24;
    const multiplier = HM[hour];
    const height = Math.max(10, multiplier * 60);
    const isCurrent = i === 0;
    
    const bar = document.createElement('div');
    bar.className = `forecast-bar ${isCurrent ? 'current' : ''}`;
    bar.style.height = height + '%';
    bar.innerHTML = `<div class="forecast-tooltip">${hour}:00 - ${Math.round(multiplier * 100)}%</div>`;
    container.appendChild(bar);
  }
}

/* ── Car Animation System ────────────────────────────────────────────────── */
function startCarSimulation(district, level) {
  stopCarSimulation();
  activeCars = [];
  
  const color = levelColor(level);
  const connectedRoads = roadLines.filter(r => 
    r.roadData.from === district || r.roadData.to === district
  );
  
  const carCount = level === 'Critical' ? 20 : level === 'High' ? 15 : level === 'Moderate' ? 10 : 5;
  qs('#liveCarCount').textContent = `${carCount * connectedRoads.length} vehicles on connected roads`;
  
  connectedRoads.forEach(road => {
    for (let i = 0; i < carCount; i++) {
      spawnCarOnRoad(road, color, i / carCount);
    }
  });
  
  // Animate
  simulationInterval = setInterval(() => {
    activeCars.forEach(car => {
      car.progress += car.speed;
      if (car.progress >= 1) car.progress = 0;
      
      const pos = getPointOnRoad(car.road, car.progress);
      const nextPos = getPointOnRoad(car.road, car.progress + 0.01);
      const angle = Math.atan2(nextPos[1] - pos[1], nextPos[0] - pos[0]) * 180 / Math.PI;
      
      car.marker.setLatLng(pos);
      car.marker.getElement().style.transform = `rotate(${angle}deg)`;
    });
  }, 50);
}

function spawnCarOnRoad(road, color, startProgress) {
  const isTruck = road.roadData.type === 'highway' && Math.random() > 0.7;
  const icon = L.divIcon({
    className: 'car-marker',
    html: `<div class="car-icon" style="width:${isTruck?28:20}px">${getCarSVG(color, isTruck)}</div>`,
    iconSize: isTruck ? [28, 12] : [20, 10],
    iconAnchor: isTruck ? [14, 6] : [10, 5]
  });
  
  const startPos = getPointOnRoad(road, startProgress);
  const marker = L.marker(startPos, { icon, zIndexOffset: 100 }).addTo(map);
  
  activeCars.push({
    marker,
    road: road.roadData,
    progress: startProgress,
    speed: (0.002 + Math.random() * 0.003) * (road.roadData.type === 'highway' ? 2 : 1)
  });
}

function getPointOnRoad(road, progress) {
  const waypoints = road.waypoints;
  const totalSegments = waypoints.length - 1;
  const segment = Math.floor(progress * totalSegments);
  const segmentProgress = (progress * totalSegments) - segment;
  
  const start = waypoints[Math.min(segment, totalSegments)];
  const end = waypoints[Math.min(segment + 1, totalSegments)];
  
  return [
    start[0] + (end[0] - start[0]) * segmentProgress,
    start[1] + (end[1] - start[1]) * segmentProgress
  ];
}

function stopCarSimulation() {
  if (simulationInterval) {
    clearInterval(simulationInterval);
    simulationInterval = null;
  }
  activeCars.forEach(car => map.removeLayer(car.marker));
  activeCars = [];
}

/* ── Event Listeners ─────────────────────────────────────────────────────── */
qs('#detailClose').addEventListener('click', closeDistrictDetail);
qs('#resetView').addEventListener('click', () => {
  map.flyTo([24.6950, 46.6750], 12);
  closeDistrictDetail();
});

qs('#pHour').addEventListener('input', (e) => {
  qs('#hourBadge').textContent = e.target.value.padStart(2, '0') + ':00';
});

qs('#predictForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const district = qs('#pZone').value;
  await openDistrictDetail(district);
});

// Navigation
qsa('.nav-item').forEach(item => {
  item.addEventListener('click', (e) => {
    e.preventDefault();
    qsa('.nav-item').forEach(n => n.classList.remove('active'));
    item.classList.add('active');
    qsa('.section').forEach(s => s.classList.remove('active'));
    qs(`#section-${item.dataset.section}`).classList.add('active');
    
    if (item.dataset.section === 'batch') {
      setTimeout(() => batchMap.invalidateSize(), 100);
    }
  });
});

qs('#mobileToggle').addEventListener('click', () => {
  qs('#sidebar').classList.toggle('open');
});

// Toggle simulation
qs('#simToggle').addEventListener('change', (e) => {
  if (e.target.checked && currentDetailDistrict) {
    fetchDistrictData(currentDetailDistrict).then(data => {
      startCarSimulation(currentDetailDistrict, data.congestion_level);
    });
  } else {
    stopCarSimulation();
  }
});

/* ── Init ────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initMap();
  
  // Check API health
  fetch(API + '/health')
    .then(r => r.json())
    .then(() => {
      qs('#statusDot').classList.add('ok');
      qs('#statusText').textContent = 'System Online';
      qs('#loadingOverlay').hidden = true;
    })
    .catch(() => {
      qs('#statusText').textContent = 'Offline Mode';
      qs('#loadingOverlay').hidden = true;
    });
});