// The telemetry graph: one quantity against route progress q, for every visible profile.
import {$, path} from './common.js';

const graph = $('telemetry-plot');
export const quantity = $('telemetry-quantity');

export const metrics = {
  speed: {label: 'Speed', unit: 'm/s'},
  longitudinal: {label: 'Longitudinal acceleration / braking', unit: 'm/s²', step: true},
  lateral: {label: 'Lateral acceleration', unit: 'm/s²'},
  curvature: {label: 'Curvature', unit: '1/m'},
  angle: {label: 'Steering angle', unit: 'rad'},
  steering_rate: {label: 'Steering rate', unit: 'rad/s', step: true},
  clearance: {label: 'Actual wall clearance', unit: 'm'},
};
const usageMetrics = {
  vehicle_usage: 'Vehicle utilisation (base)',
  speed_usage: 'Vehicle speed (base)',
  grip_usage: 'Combined tyre grip (base)',
  motor_usage: 'Motor drive (base)',
  angle_usage: 'Steering angle (base)',
  steering_usage: 'Mean steering rate (base)',
  road_usage: 'Road speed limit use',
};
for (const [key, label] of Object.entries(usageMetrics)) {
  metrics[key] = {label, unit: '%', factor: 100, step: true};
}

export const frame = {left: 49, right: 693, top: 12, bottom: 118};

const capabilityOptions = document.createElement('optgroup');
capabilityOptions.label = 'Limit usage (%)';
for (const [id, metric] of Object.entries(metrics)) {
  const option = new Option(metric.label, id);
  if (id in usageMetrics) capabilityOptions.append(option);
  else quantity.add(option);
}
quantity.append(capabilityOptions);

function yScale(lines, metric, key) {
  let low = 0, high = 0;
  for (const [, line] of lines) {
    for (const value of line.values[key]) {
      if (value === null) continue;
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

export function drawGraph(lines, view) {
  const key = quantity.value;
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
    const paths = [];
    let vertices = [];
    for (let i = 0; i <= line.q.length; i++) {
      const station = i === line.q.length ? view.period_m : line.q[i];
      if (metric.step && i > 0 && values[i - 1] !== null) {
        vertices.push([x(station), y(values[i - 1] * factor)]);
      }
      const value = values[i % values.length];
      if (value === null) {
        paths.push(path(vertices));
        vertices = [];
      } else {
        vertices.push([x(station), y(value * factor)]);
      }
    }
    paths.push(path(vertices));
    return '<path class="curve ' + kind + '" d="' + paths.join('') + '"/>';
  });
  graph.innerHTML = grid + '<path class="axis" fill="none" d="M49,12V118H693"/>'
    + '<text class="graph-label" x="2" y="11">' + metric.unit + '</text>' + curves.join('')
    + '<path class="cursor" id="graph-cursor"/>';
}

export function sampleAt(line, q, period) {
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
