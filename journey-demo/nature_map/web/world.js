import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { feature, mesh } from 'topojson-client';
import { geoEquirectangular, geoPath } from 'd3-geo';

const $ = (selector) => document.querySelector(selector);
const worldEl = $('#world');
const canvas = $('#globe');
const pinsEl = $('#pins');
const loader = $('#w-loader');
const loadText = $('#w-load-text');
const statsEl = $('#w-stats');
const journeysEl = $('#journeys');
const journeyListEl = $('#journey-list');
const journeyCountEl = $('#j-count');
const backButton = $('#w-back');
const card = $('#card');
const curtain = $('#curtain');

let trips = [];
let regions = [];
let renderer = null;
let scene = null;
let camera = null;
let controls = null;
let ready = false;
let error = null;
let view = 'world';
let currentRegion = null;
let selectedId = null;
let globalDistance = 4.2;
let flightActive = false;
let flightToken = 0;
let animationStopped = false;

const tripPins = new Map();
const regionPins = new Map();
const journeyButtons = new Map();
const tripById = new Map();
const regionById = new Map();
const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

window.worldState = () => ({
  ready,
  error,
  view,
  region: currentRegion || null,
  selected: selectedId || null,
  cameraDistance: camera ? camera.position.length() : null,
  visiblePins: [
    ...[...tripPins.entries()].filter(([, el]) => !el.classList.contains('is-hidden')).map(([id]) => id),
    ...[...regionPins.entries()].filter(([, el]) => !el.classList.contains('is-hidden')).map(([id]) => `region:${id}`),
  ],
  cardOpen: !card.hidden,
});

function fail(err) {
  error = err instanceof Error ? err.message : String(err);
  ready = false;
  animationStopped = true;
  if (loadText) loadText.textContent = 'The map could not load. Check your connection and refresh.';
  if (loader) loader.hidden = false;
  console.error('World map failed to load:', err);
}

function latLngToVector(lat, lng, radius = 1) {
  const phi = (90 - lat) * D2R;
  const theta = (lng + 180) * D2R;
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
}

function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function slerpDirection(from, to, amount) {
  const dot = THREE.MathUtils.clamp(from.dot(to), -1, 1);
  if (dot > 0.9995) return from.clone().lerp(to, amount).normalize();
  if (dot < -0.9995) {
    const helper = Math.abs(from.x) < 0.9
      ? new THREE.Vector3(1, 0, 0)
      : new THREE.Vector3(0, 1, 0);
    const axis = new THREE.Vector3().crossVectors(from, helper).normalize();
    return from.clone().applyAxisAngle(axis, Math.PI * amount).normalize();
  }
  const angle = Math.acos(dot);
  const sinAngle = Math.sin(angle);
  const fromWeight = Math.sin((1 - amount) * angle) / sinAngle;
  const toWeight = Math.sin(amount * angle) / sinAngle;
  return from.clone().multiplyScalar(fromWeight).addScaledVector(to, toWeight).normalize();
}

function animateCameraTo(targetDirection, distance, ms = 1400) {
  const token = ++flightToken;
  const fromDirection = camera.position.lengthSq() > 0
    ? camera.position.clone().normalize()
    : new THREE.Vector3(0, 0, 1);
  const toDirection = targetDirection.clone().normalize();
  const fromDistance = camera.position.length() || globalDistance;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  flightActive = true;
  controls.enabled = false;

  return new Promise((resolve) => {
    if (reducedMotion || ms <= 0) {
      camera.position.copy(toDirection).multiplyScalar(distance);
      camera.lookAt(0, 0, 0);
      flightActive = false;
      controls.enabled = true;
      controls.update();
      resolve();
      return;
    }

    const start = performance.now();
    const step = (now) => {
      if (token !== flightToken) {
        resolve();
        return;
      }
      const t = Math.min(1, (now - start) / ms);
      const eased = easeInOutCubic(t);
      const direction = slerpDirection(fromDirection, toDirection, eased);
      const nextDistance = fromDistance + (distance - fromDistance) * eased;
      camera.position.copy(direction).multiplyScalar(nextDistance);
      camera.lookAt(0, 0, 0);

      if (t < 1) {
        requestAnimationFrame(step);
      } else {
        flightActive = false;
        controls.enabled = true;
        controls.update();
        resolve();
      }
    };
    requestAnimationFrame(step);
  });
}

function flyTo(lat, lng, distance, ms = 1400) {
  return animateCameraTo(latLngToVector(lat, lng, 1), distance, ms);
}

function monthYear(date) {
  const [year, month] = date.split('-');
  return `${MONTHS[Number(month) - 1] || ''} ${year}`;
}

function renderStats() {
  const liveCount = trips.filter((trip) => trip.status === 'live').length;
  const sampleCount = trips.length - liveCount;
  const years = trips.map((trip) => Number(trip.date.slice(0, 4)));
  const minYear = Math.min(...years);
  const maxYear = Math.max(...years);
  const liveNoun = liveCount === 1 ? 'scene' : 'scenes';
  const sampleNoun = sampleCount === 1 ? 'place' : 'places';
  const samples = sampleCount === 0 ? '' : ` and ${sampleCount} sample ${sampleNoun}`;
  statsEl.textContent = `${liveCount} ${liveNoun} to explore${samples}, from ${minYear} to ${maxYear}.`;
}

function appendTripMarkup(parent, trip) {
  const item = document.createElement('li');
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'j-item';
  button.dataset.trip = trip.id;
  button.setAttribute('aria-current', 'false');

  let thumb;
  if (trip.status === 'live' && trip.cover) {
    thumb = document.createElement('img');
    thumb.className = 'j-thumb';
    thumb.src = trip.cover;
    thumb.alt = '';
    thumb.loading = 'lazy';
  } else {
    thumb = document.createElement('span');
    thumb.className = 'j-thumb j-thumb-empty';
  }
  button.append(thumb);

  const text = document.createElement('span');
  text.className = 'j-text';
  const title = document.createElement('span');
  title.className = 'j-title';
  title.textContent = trip.title;
  const meta = document.createElement('span');
  meta.className = 'j-meta';
  meta.textContent = `${trip.chapter}, ${trip.dateLabel}`;
  text.append(title, meta);
  button.append(text);

  if (trip.status === 'live') {
    const live = document.createElement('span');
    live.className = 'j-live';
    live.title = 'Scene ready';
    button.append(live);
  } else {
    const badge = document.createElement('span');
    badge.className = 'j-badge';
    badge.textContent = 'Sample';
    button.append(badge);
  }

  button.addEventListener('click', () => {
    selectTrip(trip.id);
    if (window.innerWidth < 1000) journeysEl.removeAttribute('open');
  });
  journeyButtons.set(trip.id, button);
  item.append(button);
  parent.append(item);
}

function renderJourneys() {
  journeyCountEl.textContent = `${trips.length} places`;
  journeyListEl.replaceChildren();

  const byYear = new Map();
  for (const trip of trips) {
    const year = trip.date.slice(0, 4);
    if (!byYear.has(year)) byYear.set(year, []);
    byYear.get(year).push(trip);
  }

  const years = [...byYear.keys()].sort((a, b) => Number(b) - Number(a));
  for (const year of years) {
    const section = document.createElement('section');
    section.className = 'j-year';
    const heading = document.createElement('h3');
    heading.textContent = year;
    const list = document.createElement('ol');
    const yearTrips = byYear.get(year).sort((a, b) => b.date.localeCompare(a.date));
    for (const trip of yearTrips) appendTripMarkup(list, trip);
    section.append(heading, list);
    journeyListEl.append(section);
  }
}

function setSelectedAria() {
  for (const [id, pin] of tripPins) {
    const selected = id === selectedId;
    pin.setAttribute('aria-pressed', String(selected));
    const item = journeyButtons.get(id);
    if (item) {
      if (selected) item.setAttribute('aria-current', 'true');
      else item.removeAttribute('aria-current');
    }
  }
}

function makeTripPin(trip) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = `pin ${trip.status === 'live' ? 'pin-live' : 'pin-sample'} is-hidden`;
  button.dataset.trip = trip.id;
  button.setAttribute('aria-pressed', 'false');
  const action = trip.status === 'live' ? 'Open details.' : 'Sample trip.';
  button.setAttribute('aria-label', `${trip.title}, ${trip.chapter}, ${trip.dateLabel}. ${action}`);

  const dot = document.createElement('span');
  dot.className = 'pin-dot';
  const label = document.createElement('span');
  label.className = 'pin-label';
  const title = document.createElement('span');
  title.className = 'pin-title';
  title.textContent = trip.chapter;
  const date = document.createElement('span');
  date.className = 'pin-date';
  date.textContent = monthYear(trip.date);
  label.append(title, date);
  button.append(dot, label);
  button.addEventListener('click', () => selectTrip(trip.id));
  pinsEl.append(button);
  tripPins.set(trip.id, button);
}

function makeRegionPin(region, members) {
  const count = members.length;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'pin pin-cluster is-hidden';
  button.dataset.region = region.id;
  button.setAttribute('aria-label', `${region.name}, ${count} scenes. Zoom in.`);

  const dot = document.createElement('span');
  dot.className = 'pin-dot';
  const countText = document.createElement('span');
  countText.className = 'pin-count';
  countText.textContent = String(count);
  dot.append(countText);
  const label = document.createElement('span');
  label.className = 'pin-label';
  const title = document.createElement('span');
  title.className = 'pin-title';
  title.textContent = region.name;
  const date = document.createElement('span');
  date.className = 'pin-date';
  date.textContent = `${count} scenes`;
  label.append(title, date);
  button.append(dot, label);
  button.addEventListener('click', () => selectRegion(region));
  pinsEl.append(button);
  regionPins.set(region.id, button);
}

function buildPins() {
  for (const trip of trips) makeTripPin(trip);
  for (const region of regions) {
    const members = trips.filter((trip) => trip.region === region.id);
    if (members.length >= 2) makeRegionPin(region, members);
  }
  setSelectedAria();
}

function positionPins() {
  if (!camera || !worldEl) return;
  const width = worldEl.clientWidth;
  const height = worldEl.clientHeight;
  const cameraDistance = camera.position.length();
  const showClusters = cameraDistance > 2.2;
  const cameraDirection = camera.position.clone().normalize();

  const positionOne = (el, lat, lng, clustered) => {
    const position = latLngToVector(lat, lng, 1.005);
    const behindGlobe = position.clone().normalize().dot(cameraDirection) < 0.18;
    const hidden = clustered || behindGlobe;
    if (el.classList.contains('is-hidden') !== hidden) el.classList.toggle('is-hidden', hidden);
    const tabIndex = hidden ? -1 : 0;
    if (el.tabIndex !== tabIndex) el.tabIndex = tabIndex;
    if (hidden) return;

    position.project(camera);
    const x = Math.round(((position.x + 1) * width / 2) * 10) / 10;
    const y = Math.round(((1 - position.y) * height / 2) * 10) / 10;
    const transform = `translate(${x}px,${y}px)`;
    if (el.style.transform !== transform) el.style.transform = transform;
    placed.push({ el, x, y });
  };
  const placed = [];

  for (const trip of trips) {
    const members = trip.region ? trips.filter((item) => item.region === trip.region).length : 0;
    positionOne(tripPins.get(trip.id), trip.lat, trip.lng, showClusters && members >= 2);
  }
  for (const region of regions) {
    const pin = regionPins.get(region.id);
    if (pin) positionOne(pin, region.lat, region.lng, !showClusters);
  }

  // Neighbouring pins would stack their labels; the western one reads to the left instead.
  const flipped = new Set();
  for (const a of placed) {
    for (const b of placed) {
      if (a.x < b.x && b.x - a.x < 200 && Math.abs(a.y - b.y) < 44) flipped.add(a.el);
    }
  }
  for (const el of tripPins.values()) el.classList.toggle('pin-flip', flipped.has(el));
  for (const el of regionPins.values()) el.classList.toggle('pin-flip', flipped.has(el));
}

function makeWorldTexture(topo) {
  const width = 4096;
  const height = 2048;
  const mapCanvas = document.createElement('canvas');
  mapCanvas.width = width;
  mapCanvas.height = height;
  const ctx = mapCanvas.getContext('2d');
  if (!ctx) throw new Error('Could not create the world map canvas.');

  ctx.fillStyle = '#133a46';
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = 'rgba(233,241,239,0.07)';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let lat = -90; lat <= 90; lat += 15) {
    const y = ((90 - lat) / 180) * height;
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
  }
  for (let lng = -180; lng <= 180; lng += 15) {
    const x = ((lng + 180) / 360) * width;
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
  }
  ctx.stroke();

  // d3-geo clips polygons at the antimeridian, so land fills stay closed.
  const projection = geoEquirectangular().scale(width / (2 * Math.PI)).translate([width / 2, height / 2]).precision(0.2);
  const path = geoPath(projection, ctx);

  ctx.beginPath();
  path(feature(topo, topo.objects.land));
  ctx.fillStyle = '#8fb5a3';
  ctx.fill();

  ctx.beginPath();
  path(mesh(topo, topo.objects.countries, (a, b) => a !== b));
  ctx.strokeStyle = 'rgba(15,42,51,0.28)';
  ctx.lineWidth = 1.2;
  ctx.stroke();

  ctx.beginPath();
  path(mesh(topo, topo.objects.land));
  ctx.strokeStyle = 'rgba(233,241,239,0.55)';
  ctx.lineWidth = 1.6;
  ctx.stroke();

  const texture = new THREE.CanvasTexture(mapCanvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function makeStars() {
  let seed = 1926;
  const random = () => {
    seed = (1664525 * seed + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  const positions = new Float32Array(1400 * 3);
  for (let i = 0; i < 1400; i += 1) {
    const y = random() * 2 - 1;
    const angle = random() * Math.PI * 2;
    const horizontal = Math.sqrt(1 - y * y);
    const radius = 60 + random() * 30;
    positions[i * 3] = Math.cos(angle) * horizontal * radius;
    positions[i * 3 + 1] = y * radius;
    positions[i * 3 + 2] = Math.sin(angle) * horizontal * radius;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  return new THREE.Points(geometry, new THREE.PointsMaterial({
    color: '#e9f1ef',
    size: 0.12,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.55,
    depthWrite: false,
  }));
}

function addGlobe(texture) {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(35, 1, 0.01, 200);

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = renderer.capabilities.getMaxAnisotropy();

  const globe = new THREE.Mesh(
    new THREE.SphereGeometry(1, 128, 96),
    new THREE.MeshStandardMaterial({ map: texture, roughness: 1, metalness: 0 }),
  );
  scene.add(globe);

  scene.add(new THREE.Mesh(
    new THREE.SphereGeometry(1.06, 128, 96),
    new THREE.ShaderMaterial({
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
      transparent: true,
      depthWrite: false,
      vertexShader: 'varying vec3 vN; varying vec3 vV; void main(){ vec4 mv=modelViewMatrix*vec4(position,1.); vN=normalize(normalMatrix*normal); vV=normalize(-mv.xyz); gl_Position=projectionMatrix*mv; }',
      fragmentShader: 'varying vec3 vN; varying vec3 vV; void main(){ float f=smoothstep(0.0,0.34,-dot(vN,vV)); f=f*f*f; gl_FragColor=vec4(vec3(0.498,0.820,0.780)*f*0.55, f*0.55); }',
    }),
  ));

  scene.add(new THREE.AmbientLight('#ffffff', 1.5));
  const directional = new THREE.DirectionalLight('#fff6e8', 1.4);
  directional.position.set(-3, 2, 1);
  camera.add(directional);
  scene.add(camera);
  scene.add(directional.target);
  scene.add(makeStars());

  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.rotateSpeed = 0.45;
  controls.zoomSpeed = 0.7;
  controls.enablePan = false;
  controls.minDistance = 1.35;
  controls.maxDistance = 6;
  controls.target.set(0, 0, 0);

  const resize = () => {
    const width = worldEl.clientWidth;
    const height = worldEl.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    // The view offset renders a larger virtual frame and shows part of it; the aspect must match
    // that frame or the globe stretches. Desktop: centre left of the journeys panel. Phones:
    // centre raised so a focused pin clears the bottom sheet.
    const frame = width >= 1000 ? [width + 336, height, 336, 0]
      : width < 700 ? [width, height * 1.28, 0, height * 0.28] : null;
    if (frame) {
      camera.aspect = frame[0] / frame[1];
      camera.setViewOffset(frame[0], frame[1], frame[2], frame[3], width, height);
    } else {
      camera.aspect = width / height;
      camera.clearViewOffset();
    }
    camera.updateProjectionMatrix();
    // FOV is vertical, so on tall screens back the camera off until the globe fits ~90% of the width.
    const tanHalfX = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * width / (frame ? frame[1] : height);
    const fitDistance = Math.sqrt(1 + 1 / (0.9 * tanHalfX) ** 2);
    globalDistance = Math.max(4.2, fitDistance);
    controls.maxDistance = Math.max(6, globalDistance + 1);
    if (view === 'world' && camera.position.lengthSq() > 0 && !flightActive) {
      camera.position.setLength(globalDistance);
      camera.lookAt(0, 0, 0);
      controls.update();
    }
  };
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(worldEl);
  resize();

  const initialFocus = new URLSearchParams(window.location.search).get('focus');
  const focusTrip = initialFocus ? tripById.get(initialFocus) : null;
  if (focusTrip) {
    const distance = focusTrip.region ? 1.7 : 2.6;
    camera.position.copy(latLngToVector(focusTrip.lat, focusTrip.lng, distance));
    camera.lookAt(0, 0, 0);
    openTripCard(focusTrip);
    view = 'trip';
    currentRegion = focusTrip.region || null;
    backButton.hidden = false;
  } else {
    camera.position.copy(latLngToVector(28, 70, globalDistance));
    camera.lookAt(0, 0, 0);
    view = 'world';
    currentRegion = null;
  }
  controls.update();

  const render = () => {
    if (animationStopped) return;
    try {
      if (!flightActive) controls.update();
      renderer.render(scene, camera);
      positionPins();
      if (!ready) {
        ready = true;
        loader.hidden = true;
      }
      requestAnimationFrame(render);
    } catch (err) {
      fail(err);
    }
  };
  requestAnimationFrame(render);
}

function syncTripCard(trip) {
  selectedId = trip.id;
  card.dataset.status = trip.status;
  const cover = $('#card-cover');
  if (trip.cover) cover.setAttribute('src', trip.cover);
  else cover.removeAttribute('src');
  cover.alt = trip.title;
  $('#card-badge').hidden = trip.status === 'live';
  $('#card-chapter').textContent = trip.chapter;
  $('#card-title').textContent = trip.title;
  const date = $('#card-date');
  date.textContent = trip.dateLabel;
  date.setAttribute('datetime', trip.date);
  $('#card-date-note').textContent = trip.dateNote || '';
  $('#card-summary').textContent = trip.summary;
  const photos = $('#card-photos');
  photos.textContent = trip.status === 'live' ? `${trip.memories.length} photos from this trip` : '';
  photos.hidden = !photos.textContent;
  $('#card-open').setAttribute('href', trip.scene || '#');
  card.hidden = false;
  setSelectedAria();
}

function openTripCard(trip) {
  syncTripCard(trip);
}

function selectTrip(id) {
  const trip = tripById.get(id);
  if (!trip) return;
  openTripCard(trip);
  currentRegion = trip.region || null;
  view = 'trip';
  backButton.hidden = false;
  history.replaceState(null, '', `?focus=${encodeURIComponent(id)}`);
  flyTo(trip.lat, trip.lng, trip.region ? 1.7 : 2.6);
}

function selectRegion(region) {
  card.hidden = true;
  selectedId = null;
  setSelectedAria();
  currentRegion = region.id;
  view = 'region';
  backButton.hidden = false;
  history.replaceState(null, '', 'world.html');
  flyTo(region.lat, region.lng, 1.7);
}

function clearCardSelection() {
  card.hidden = true;
  selectedId = null;
  setSelectedAria();
  history.replaceState(null, '', 'world.html');
}

function goBackToWorld() {
  card.hidden = true;
  selectedId = null;
  setSelectedAria();
  history.replaceState(null, '', 'world.html');
  const direction = camera.position.lengthSq() > 0
    ? camera.position.clone().normalize()
    : latLngToVector(28, 70, 1);
  currentRegion = null;
  view = 'world';
  backButton.hidden = true;
  animateCameraTo(direction, globalDistance);
}

backButton.addEventListener('click', goBackToWorld);
$('#card-close').addEventListener('click', clearCardSelection);
$('#card-open').addEventListener('click', (event) => {
  const trip = selectedId ? tripById.get(selectedId) : null;
  if (!trip || trip.status !== 'live') return;
  event.preventDefault();
  curtain.classList.add('is-on');
  flyTo(trip.lat, trip.lng, 1.08, 900);
  const navigate = () => { window.location.href = trip.scene; };
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) navigate();
  else window.setTimeout(navigate, 700);
});

$('#journeys').querySelector('summary').addEventListener('click', (event) => {
  if (window.innerWidth >= 1000) event.preventDefault();
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !card.hidden) clearCardSelection();
});

window.addEventListener('pageshow', (event) => {
  if (event.persisted) curtain.classList.remove('is-on');
});

async function readJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not load ${url} (${response.status}).`);
  return response.json();
}

async function init() {
  try {
    if (window.innerWidth < 1000) journeysEl.removeAttribute('open');
    const [data, topo] = await Promise.all([
      readJson('trips.json'),
      readJson('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json'),
    ]);
    trips = data.trips;
    regions = data.regions;
    for (const trip of trips) tripById.set(trip.id, trip);
    for (const region of regions) regionById.set(region.id, region);
    renderStats();
    renderJourneys();
    buildPins();
    const texture = makeWorldTexture(topo);
    addGlobe(texture);
  } catch (err) {
    fail(err);
  }
}

await init();
