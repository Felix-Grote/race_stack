// The lap overlay and the Inspect panel, kept in step with the telemetry graph.
import {$, path} from './common.js';
import {constraintCategory, constraintTypes, showConstraints} from './constraints.js';
import {drawGraph, frame, metrics, quantity, sampleAt} from './graph.js';

const map = $('track-plot'), graph = $('telemetry-plot'), inspection = $('inspection');
const mode = $('map-mode'), heatProfile = $('heat-profile');
const heatColors = ['#247540', '#c29000', '#da5a00', '#a30021'];
let scene, fitted, dragging, cursorQ;

function title(kind) {
  return kind[0].toUpperCase() + kind.slice(1);
}

function drawPath(points, style, closed = false) {
  return '<path class="' + style + '" d="' + path(points, closed) + '"/>';
}

function box([x, y, width, height]) {
  map.setAttribute('viewBox', [x, y, width, height].join(' '));
  const scale = map.getScreenCTM()?.a;
  if (scale) map.querySelectorAll('.marker').forEach(marker => marker.setAttribute('r', 4 / scale));
}

export function fit() {
  if (fitted) box(fitted);
}

// Zoom about `at`, a point of the map that stays where it is on screen, or about the middle.
export function zoom(factor, at) {
  if (!fitted) return;
  const {x, y, width, height} = map.viewBox.baseVal;
  if (width * factor < fitted[2] / 8 || width * factor > fitted[2] * 4) return;
  const cx = at?.x ?? x + width / 2, cy = at?.y ?? y + height / 2;
  box([cx - (cx - x) * factor, cy - (cy - y) * factor, width * factor, height * factor]);
}

map.addEventListener('wheel', event => {
  if (!fitted) return;
  event.preventDefault();
  // A trackpad pinch arrives as a wheel with ctrl held, in finer steps than a mouse wheel's.
  const step = event.deltaY * (event.deltaMode ? 16 : 1) * (event.ctrlKey ? 0.01 : 0.0015);
  zoom(Math.exp(step), pointerAt(map, event));
}, {passive: false});

map.addEventListener('pointerdown', event => {
  if (!fitted || event.button !== 0) return;
  map.setPointerCapture(event.pointerId);
  const {x, y, width, height} = map.viewBox.baseVal;
  dragging = {x, y, width, height, clientX: event.clientX, clientY: event.clientY, scale: map.getScreenCTM().a};
  map.classList.add('dragging');
});
map.addEventListener('lostpointercapture', () => {
  dragging = null;
  map.classList.remove('dragging');
});

function clearanceScale(required) {
  return {
    breaks: [required, required + 0.05, required + 0.15],
    colors: [...heatColors].reverse(),
    labels: ['Below required gap', '0–5 cm spare', '5–15 cm spare', '15 cm or more spare'],
  };
}

function drawMapOverlay(line, legend, required) {
  const categorical = mode.value === 'constraints';
  const scale = categorical ? null : clearanceScale(required);
  const palette = categorical ? constraintTypes : Object.fromEntries(scale.labels.map((label, i) =>
    [i, {label, color: scale.colors[i]}]));
  const buckets = new Map();
  for (const [i, here] of line.points.entries()) {
    const key = categorical ? constraintCategory(line, i)
      : String(scale.breaks.filter(limit => line.values.clearance[i] >= limit).length);
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(path([here, line.points[(i + 1) % line.points.length]]));
  }
  for (const [key, style] of Object.entries(palette)) {
    if (categorical && !buckets.has(key)) continue;
    const label = document.createElement('span'), swatch = document.createElement('i');
    swatch.style.background = style.color;
    label.append(swatch, document.createTextNode(style.label));
    legend.append(label);
  }
  return Array.from(buckets, ([key, segments]) =>
    '<path class="heat-line" stroke="' + palette[key].color + '" d="' + segments.join('') + '"/>').join('');
}

function drawMap() {
  const {view, lines, profiles} = scene;
  const hasRoute = view.walls.length > 0;
  const isHeatmap = mode.value !== 'trajectories';
  const active = heatProfile.value;
  $('heat-profile-label').hidden = !isHeatmap;
  heatProfile.disabled = !lines.length;
  $('no-route').hidden = hasRoute;
  map.classList.toggle('pannable', hasRoute);
  for (const id of ['fit', 'zoom-in', 'zoom-out']) $(id).disabled = !hasRoute;

  const legend = $('heat-legend');
  legend.replaceChildren();
  legend.hidden = !isHeatmap || !hasRoute;
  if (!hasRoute) {
    fitted = null;
    map.innerHTML = '';
    return;
  }

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const wall of view.walls) {
    for (const [x, y] of wall) {
      minX = Math.min(minX, x);
      minY = Math.min(minY, -y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, -y);
    }
  }
  const pad = Math.max(maxX - minX, maxY - minY) * 0.075;
  const next = [minX - pad, minY - pad, maxX - minX + 2 * pad, maxY - minY + 2 * pad];
  if (!fitted || next.some((value, index) => value !== fitted[index])) {
    fitted = next;
    fit();
  }

  const road = view.walls.map(wall => drawPath(wall, 'road', true))
    .concat(view.gates.map(gate => drawPath(gate, 'gate')), drawPath(view.start, 'start'));
  let overlay = '';
  if (!isHeatmap) {
    overlay = scene.stale.map(points => drawPath(points, 'curve stale', true)).join('')
      + lines.map(([kind, line]) => drawPath(line.points, 'curve ' + kind, true)).join('');
  } else if (active) {
    overlay = drawMapOverlay(view.lines[active], legend, profiles[active].margin_m);
  } else {
    legend.textContent = 'Select a current profile to inspect its trajectory.';
  }
  map.innerHTML = '<g transform="scale(1,-1)">' + road.join('') + overlay + '<g id="map-cursor"/></g>';
}

function appendText(tag, text) {
  const item = document.createElement(tag);
  item.textContent = text;
  inspection.append(item);
  return item;
}

function inspect(q) {
  const {view, lines, profiles} = scene;
  const key = quantity.value, metric = metrics[key];
  const isHeatmap = mode.value !== 'trajectories';
  const markers = [];
  const graphCursor = $('graph-cursor');
  const mapCursor = $('map-cursor');
  cursorQ = q;
  inspection.replaceChildren();
  if (q == null || !lines.length) {
    inspection.textContent = 'Point at the graph or a diagnostic line to inspect a location.';
    graphCursor?.removeAttribute('d');
    if (mapCursor) mapCursor.innerHTML = '';
    return;
  }

  const x = frame.left + (frame.right - frame.left) * q / view.period_m;
  graphCursor.setAttribute('d', 'M' + x + ',' + frame.top + 'V' + frame.bottom);
  const lapQ = q === view.period_m ? 0 : q;
  const scale = map.getScreenCTM()?.a || 1;
  appendText('strong', 'q ' + q.toFixed(2) + ' m · ' + metric.label);
  for (const [kind, line] of lines) {
    const sample = sampleAt(line, lapQ, view.period_m);
    const {xy: [x, y]} = sample;
    const value = sample.value(line.values[key], metric.step);
    const display = value === null ? '—' : (value * (metric.factor || 1))
      .toFixed(key === 'curvature' ? 3 : 2) + ' ' + metric.unit;
    // One line a profile: its colour on the map, its name, its value.
    const reading = appendText('div', '');
    reading.className = 'reading';
    const swatch = document.createElement('i'), name = document.createElement('span');
    swatch.className = 'swatch ' + kind;
    name.textContent = title(kind);
    reading.append(swatch, name, display);
    if (isHeatmap && kind !== heatProfile.value) continue;
    markers.push('<circle class="marker ' + kind + '" cx="' + x + '" cy="' + y + '" r="' + 4 / scale + '"/>');
  }
  if (isHeatmap && heatProfile.value) {
    const kind = heatProfile.value, line = view.lines[kind];
    const {index} = sampleAt(line, lapQ, view.period_m);
    appendText('strong', title(kind) + (mode.value === 'constraints' ? ' · active constraints' : ' clearance'))
      .title = 'The interval from q ' + line.q[index].toFixed(2) + ' m to the next point';
    if (mode.value === 'constraints') {
      showConstraints(line, index, appendText);
    } else {
      const actual = line.values.clearance[index], required = profiles[kind].margin_m;
      appendText('p', 'Actual ' + (actual * 100).toFixed(1) + ' cm · required '
        + (required * 100).toFixed(1) + ' cm · spare ' + ((actual - required) * 100).toFixed(1) + ' cm');
    }
  }
  mapCursor.innerHTML = markers.join('');
}

function display() {
  drawMap();
  drawGraph(scene.lines, scene.view);
  inspect(null);
}

export function drawPlots(view, visible, profiles) {
  const lines = Object.entries(view.lines).filter(([kind]) => visible.has(kind));
  const current = heatProfile.value;
  heatProfile.replaceChildren(...lines.map(([kind]) => new Option(title(kind), kind)));
  if (lines.some(([kind]) => kind === current)) heatProfile.value = current;
  else if (lines.some(([kind]) => kind === 'balanced')) heatProfile.value = 'balanced';
  const stale = Object.entries(view.stale || {}).filter(([kind]) => visible.has(kind))
    .map(([, points]) => points);
  scene = {view, lines, profiles, stale};
  display();
}

mode.onchange = heatProfile.onchange = quantity.onchange = () => { if (scene) display(); };

function pointerAt(svg, event) {
  return new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.getScreenCTM().inverse());
}

graph.addEventListener('pointermove', event => {
  if (!scene?.lines.length) return;
  const {x} = pointerAt(graph, event);
  inspect(Math.min(1, Math.max(0, (x - frame.left) / (frame.right - frame.left))) * scene.view.period_m);
});
graph.addEventListener('keydown', event => {
  if (!scene?.lines.length) return;
  const period = scene.view.period_m;
  const delta = {ArrowLeft: -period / 100, ArrowRight: period / 100}[event.key];
  if (delta === undefined && !['Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  inspect(event.key === 'Home' ? 0 : event.key === 'End' ? period
    : Math.min(period, Math.max(0, (cursorQ ?? 0) + delta)));
});

map.addEventListener('pointermove', event => {
  if (dragging && map.hasPointerCapture(event.pointerId)) {
    const {x, y, width, height, clientX, clientY, scale} = dragging;
    box([x - (event.clientX - clientX) / scale, y - (event.clientY - clientY) / scale, width, height]);
    return;
  }
  const line = scene?.view.lines[heatProfile.value];
  if (!line || mode.value === 'trajectories') return;
  const pointer = pointerAt(map, event);
  let closest = 14 / map.getScreenCTM().a, index = -1;
  for (const [i, [x, y]] of line.points.entries()) {
    const [endX, endY] = line.points[(i + 1) % line.points.length];
    const dx = endX - x, dy = endY - y, px = pointer.x - x, py = -pointer.y - y;
    const along = Math.min(1, Math.max(0, (px * dx + py * dy) / (dx * dx + dy * dy || 1)));
    const distance = Math.hypot(px - dx * along, py - dy * along);
    if (distance < closest) {
      closest = distance;
      index = i;
    }
  }
  if (index !== -1) inspect(line.q[index]);
});
