const map = document.getElementById('track-plot');
const speed = document.getElementById('speed-plot');
let fitted, dragging;

function path(points, closed = false) {
  return points.length ? 'M' + points.map(([x, y]) => [Number(x), Number(y)].join(',')).join('L') + (closed ? 'Z' : '') : '';
}

function drawPath(points, style, closed = false) {
  return '<path class="' + style + '" d="' + path(points, closed) + '"/>';
}

function box([x, y, width, height]) {
  map.setAttribute('viewBox', [x, y, width, height].join(' '));
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
map.addEventListener('pointermove', event => {
  if (!dragging || !map.hasPointerCapture(event.pointerId)) return;
  const {x, y, width, height, clientX, clientY, scale} = dragging;
  box([x - (event.clientX - clientX) / scale, y - (event.clientY - clientY) / scale, width, height]);
});
map.addEventListener('lostpointercapture', () => {
  dragging = null;
  map.classList.remove('dragging');
});

function drawSpeed(lines) {
  const profiles = lines.filter(([, line]) => line.speed.length);
  document.getElementById('no-speed').hidden = Boolean(profiles.length);
  if (!profiles.length) {
    speed.innerHTML = '';
    return;
  }
  let max = 0;
  for (const [, line] of profiles) {
    for (const [, velocity] of line.speed) max = Math.max(max, velocity);
  }
  const interval = Math.max(0.5, Math.ceil(max / 2) / 2);
  const left = 42, right = 695, top = 13, bottom = 120;
  const x = progress => left + (right - left) * progress;
  const y = velocity => bottom - (bottom - top) * velocity / (4 * interval);
  let grid = '';
  for (let i = 0; i <= 4; i++) {
    const velocity = i * interval;
    grid += '<path class="gridline" d="M' + left + ',' + y(velocity) + 'H' + right + '"/>';
    grid += '<text class="graph-label" x="35" y="' + (y(velocity) + 4) + '" text-anchor="end">' + velocity + '</text>';
    grid += '<text class="graph-label" x="' + x(i / 4) + '" y="138" text-anchor="middle">' + i * 25 + '%</text>';
  }
  const curves = profiles.map(([kind, {speed: samples}]) => {
    const points = samples.map(([progress, velocity]) => [x(progress), y(velocity)]);
    points.push([right, points[0][1]]);
    return drawPath(points, 'curve ' + kind);
  });
  speed.innerHTML = grid + '<path class="axis" fill="none" d="M42,13V120H695"/>' +
    '<text class="graph-label" x="5" y="12">m/s</text>' + curves.join('');
}

export function drawPlots(view, visible) {
  const lines = Object.entries(view.lines).filter(([kind]) => visible.has(kind));
  const hasRoute = view.walls.length > 0;
  document.getElementById('no-route').hidden = hasRoute;
  map.classList.toggle('pannable', hasRoute);
  for (const id of ['fit', 'zoom-in', 'zoom-out']) document.getElementById(id).disabled = !hasRoute;
  if (hasRoute) {
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
    const paths = view.walls.map(wall => drawPath(wall, 'road', true))
      .concat(view.gates.map(gate => drawPath(gate, 'gate')))
      .concat(drawPath(view.start, 'start', true), lines.map(([kind, line]) => drawPath(line.points, 'curve ' + kind, true)));
    map.innerHTML = '<g transform="scale(1,-1)">' + paths.join('') + '</g>';
  } else {
    fitted = null;
    map.innerHTML = '';
  }
  drawSpeed(lines);
}
