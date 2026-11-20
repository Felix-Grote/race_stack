const $ = id => document.getElementById(id);
const map = $('track-plot'), graph = $('telemetry-plot'), inspection = $('inspection');
const mode = $('map-mode'), heatProfile = $('heat-profile'), quantity = $('telemetry-quantity');

const metrics = {
  speed: {label: 'Speed', unit: 'm/s'},
  longitudinal: {label: 'Longitudinal acceleration / braking', unit: 'm/s²', step: true},
  lateral: {label: 'Lateral acceleration', unit: 'm/s²'},
  curvature: {label: 'Curvature', unit: '1/m'},
  angle: {label: 'Steering angle', unit: 'rad'},
  steering_rate: {label: 'Steering rate', unit: 'rad/s', step: true},
  clearance: {label: 'Actual wall clearance', unit: 'm'},
  utilization: {label: 'Constraint utilisation', unit: '%', factor: 100, step: true},
};
const constraintUnits = {
  'Road speed': 'm/s', 'Vehicle speed': 'm/s', 'Combined tyre grip': '%',
  'Motor acceleration': 'm/s²', 'Steering angle': 'rad', 'Steering rate cap': 'rad/s',
};
const heatColors = ['#247540', '#c29000', '#da5a00', '#a30021'];
const frame = {left: 49, right: 693, top: 12, bottom: 118};
let scene, fitted, dragging, cursorQ;

for (const [id, metric] of Object.entries(metrics)) quantity.add(new Option(metric.label, id));

function title(kind) {
  return kind[0].toUpperCase() + kind.slice(1);
}

function path(points, closed = false) {
  return points.length ? 'M' + points.map(([x, y]) => [Number(x), Number(y)].join(',')).join('L')
    + (closed ? 'Z' : '') : '';
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

export function zoom(factor) {
  if (!fitted) return;
  const {x, y, width, height} = map.viewBox.baseVal;
  if (width * factor < fitted[2] / 8 || width * factor > fitted[2] * 4) return;
  box([x + width * (1 - factor) / 2, y + height * (1 - factor) / 2, width * factor, height * factor]);
}

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

function heatScale(required) {
  if (mode.value === 'utilization') {
    return {breaks: [0.70, 0.90, 1.0], colors: heatColors,
            labels: ['Below 70%', '70–90%', '90–100%', 'At or over 100%']};
  }
  return {
    breaks: [required, required + 0.05, required + 0.15],
    colors: [...heatColors].reverse(),
    labels: ['Below required gap', '0–5 cm spare', '5–15 cm spare', '15 cm or more spare'],
  };
}

function drawHeat(line, scale) {
  const buckets = scale.colors.map(() => []);
  const values = line.values[mode.value];
  for (const [i, here] of line.points.entries()) {
    const bucket = scale.breaks.filter(limit => values[i] >= limit).length;
    buckets[bucket].push(path([here, line.points[(i + 1) % line.points.length]]));
  }
  return buckets.map((segments, i) =>
    '<path class="heat-line" stroke="' + scale.colors[i] + '" d="' + segments.join('') + '"/>').join('');
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
    .concat(view.gates.map(gate => drawPath(gate, 'gate')), drawPath(view.start, 'start', true));
  let overlay = '';
  if (!isHeatmap) {
    overlay = lines.map(([kind, line]) => drawPath(line.points, 'curve ' + kind, true)).join('');
  } else if (active) {
    const scale = heatScale(profiles[active].margin_m);
    overlay = drawHeat(view.lines[active], scale);
    for (const [i, text] of scale.labels.entries()) {
      const label = document.createElement('span'), swatch = document.createElement('i');
      swatch.style.background = scale.colors[i];
      label.append(swatch, document.createTextNode(text));
      legend.append(label);
    }
  } else {
    legend.textContent = 'Select a current profile to show its heatmap.';
  }
  map.innerHTML = '<g transform="scale(1,-1)">' + road.join('') + overlay + '<g id="map-cursor"/></g>';
}

function yScale(lines, metric, key) {
  let low = 0, high = 0;
  for (const [, line] of lines) {
    for (const value of line.values[key]) {
      low = Math.min(low, value * (metric.factor || 1));
      high = Math.max(high, value * (metric.factor || 1));
    }
  }
  const target = Math.max(high - low, 0.05) / 4;
  const power = 10 ** Math.floor(Math.log10(target));
  const tick = [1, 2, 5, 10].find(n => n * power >= target) * power;
  return {low: Math.floor(low / tick) * tick, high: Math.max(tick, Math.ceil(high / tick) * tick),
          tick};
}

function drawGraph() {
  const {lines, view} = scene, key = quantity.value;
  const metric = metrics[key], factor = metric.factor || 1;
  $('no-telemetry').hidden = Boolean(lines.length);
  if (!lines.length) {
    graph.innerHTML = '';
    return;
  }
  const {left, right, top, bottom} = frame;
  const {low, high, tick} = yScale(lines, metric, key);
  const x = q => left + (right - left) * q / view.period_m;
  const y = value => bottom - (bottom - top) * (value - low) / (high - low);
  let grid = '';
  for (let value = low; value <= high + tick / 1000; value += tick) {
    const row = y(value);
    const label = Math.abs(value) < tick / 1000 ? 0 : Number(value.toPrecision(4));
    grid += '<path class="' + (label === 0 ? 'axis' : 'gridline') + '" d="M' + left + ',' + row + 'H' + right + '"/>';
    grid += '<text class="graph-label" x="43" y="' + (row + 4) + '" text-anchor="end">' + label + '</text>';
  }
  for (let i = 0; i <= 4; i++) {
    const q = view.period_m * i / 4;
    grid += '<text class="graph-label" x="' + x(q) + '" y="136" text-anchor="middle">' + q.toFixed(1) + '</text>';
  }
  const curves = lines.map(([kind, line]) => {
    const values = line.values[key];
    const vertices = [[x(line.q[0]), y(values[0] * factor)]];
    for (let i = 1; i <= line.q.length; i++) {
      const station = i === line.q.length ? view.period_m : line.q[i];
      if (metric.step) vertices.push([x(station), y(values[i - 1] * factor)]);
      vertices.push([x(station), y(values[i % values.length] * factor)]);
    }
    return drawPath(vertices, 'curve ' + kind);
  });
  graph.innerHTML = grid + '<path class="axis" fill="none" d="M49,12V118H693"/>'
    + '<text class="graph-label" x="2" y="11">' + metric.unit + '</text>' + curves.join('')
    + '<path class="cursor" id="graph-cursor"/>';
}

function sampleAt(line, q, period) {
  let low = 0, high = line.q.length;
  while (low + 1 < high) {
    const mid = Math.floor((low + high) / 2);
    if (line.q[mid] <= q) low = mid;
    else high = mid;
  }
  const next = high % line.q.length;
  const fraction = (q - line.q[low]) / ((line.q[high] ?? period) - line.q[low]);
  const blend = (a, b) => a + (b - a) * fraction;
  const [x, y] = line.points[low], [nextX, nextY] = line.points[next];
  return {index: low, xy: [blend(x, nextX), blend(y, nextY)],
          value: (values, step) => step ? values[low] : blend(values[low], values[next])};
}

function appendText(tag, text) {
  const item = document.createElement(tag);
  item.textContent = text;
  inspection.append(item);
  return item;
}

function showConstraints(line, index) {
  const details = Object.entries(line.constraints).map(([name, [actual, limit]]) => {
    const allowed = Array.isArray(limit) ? limit[index] : limit;
    return {name, actual: actual[index], allowed, ratio: allowed > 0 ? actual[index] / allowed : null};
  });
  details.sort((a, b) => (b.ratio ?? -1) - (a.ratio ?? -1));
  appendText('strong', details[0].name + ' · ' + (details[0].ratio * 100).toFixed(1) + '%');
  const rows = appendText('ul', '');
  for (const {name, actual, allowed, ratio} of details) {
    const row = document.createElement('li'), unit = constraintUnits[name];
    const factor = unit === '%' ? 100 : 1;
    row.textContent = name + ' · ' + (actual * factor).toFixed(2) + ' / '
      + (allowed * factor).toFixed(2) + ' ' + unit + (ratio === null ? ' (no available drive)' :
        ' · ' + (ratio * 100).toFixed(1) + '%');
    rows.append(row);
  }
  const {grip} = line;
  const tyreDemand = grip.longitudinal[index];
  appendText('p', 'Grip at gap ' + (grip.end[index] ? 'end' : 'start') + ' · lateral '
    + grip.lateral[index].toFixed(2) + ' / ' + grip.lateral_limit.toFixed(2)
    + ', ' + (tyreDemand < 0 ? 'braking ' : 'drive ') + Math.abs(tyreDemand).toFixed(2) + ' / '
    + grip.longitudinal_limit[index].toFixed(2) + ' m/s²');
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
    inspection.textContent = 'Point at the graph or a heatmap line to inspect a location.';
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
    const value = sample.value(line.values[key], metric.step) * (metric.factor || 1);
    appendText('p', title(kind) + ' · ' + value.toFixed(key === 'curvature' ? 3 : 2) + ' ' + metric.unit);
    if (isHeatmap && kind !== heatProfile.value) continue;
    markers.push('<circle class="marker ' + kind + '" cx="' + x + '" cy="' + y + '" r="' + 4 / scale + '"/>');
  }
  if (isHeatmap && heatProfile.value) {
    const kind = heatProfile.value, line = view.lines[kind];
    const {index} = sampleAt(line, lapQ, view.period_m);
    appendText('p', title(kind) + ' heatmap sample · q ' + line.q[index].toFixed(2) + ' m');
    if (mode.value === 'utilization') {
      showConstraints(line, index);
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
  drawGraph();
  inspect(null);
}

export function drawPlots(view, visible, profiles) {
  const lines = Object.entries(view.lines).filter(([kind]) => visible.has(kind));
  const current = heatProfile.value;
  heatProfile.replaceChildren(...lines.map(([kind]) => new Option(title(kind), kind)));
  if (lines.some(([kind]) => kind === current)) heatProfile.value = current;
  else if (lines.some(([kind]) => kind === 'balanced')) heatProfile.value = 'balanced';
  scene = {view, lines, profiles};
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
