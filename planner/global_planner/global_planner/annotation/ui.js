// The annotation page: draws the map and the draft, and sends the operator's edits.
const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
const $ = id => document.getElementById(id);
const embedded = window.parent !== window;
document.body.classList.toggle('embedded', embedded);
let V = {}, tool = null, draft = [], vp = null, pan = null, hover = null, picked = -1;
let sourceChanged = false, carUnavailable = false;
// Whether the line on screen was refused: it shows, dashed in the problem colour, for a moment.
let refused = false;
const REFUSED_MS = 2000;
const images = {}, shown = {map: true, road: true, guide: true, route: true};
const HINTS = {
  null: 'Pick a tool. Wheel zooms; drag with the right or middle button pans.',
  stroke: 'Draw wall: click points, double-click to finish. Backspace drops the last point, ' +
          'Escape the whole line.',
  region: 'Pick region: the track is picked for you; click inside another piece of free ' +
          'space to keep that one instead.',
  guide: 'Draw guide: click points round the track in the direction of travel; click the first ' +
         'point (or double-click) to close it. Backspace drops the last point, Escape all. ' +
         'A drawn guide stays as drawn; Suggest makes it follow the road again.',
  start: 'Set start: click on the track where the car starts; the first gate and the start ' +
         'zone are placed there, facing along the guide.'};
// How close, in canvas pixels, a click must be to the guide's first point to close it.
const CLOSE_PX = 10;

// Map pixels <-> canvas: canvas = s * pixel + offset. Only the view, never the draft.
// The view frames the track's outer wall, or the whole map while there is no track.
function bounds() {
  const w = V.walls_px && V.walls_px[0];
  if (!w) return [0, 0, V.size[0], V.size[1]];
  const us = w.map(p => p[0]), vs = w.map(p => p[1]);
  return [Math.min(...us), Math.min(...vs), Math.max(...us), Math.max(...vs)];
}
function fit() {
  if (!V.size) return;
  const [u0, v0, u1, v1] = bounds(), m = .05 * Math.max(u1 - u0, v1 - v0, 1);
  const s = Math.min(cv.width / (u1 - u0 + 2 * m), cv.height / (v1 - v0 + 2 * m));
  vp = {s, x: cv.width / 2 - s * (u0 + u1) / 2, y: cv.height / 2 - s * (v0 + v1) / 2};
}
// Match the backing store to the laid-out canvas so clicks use the same pixels as drawing.
function resize() {
  const {clientWidth: width, clientHeight: height} = cv;
  if (!width || !height || (cv.width === width && cv.height === height)) return;
  cv.width = width;
  cv.height = height;
  fit(); draw();
}
const toCanvas = p => [vp.x + p[0] * vp.s, vp.y + p[1] * vp.s];
function toPixel(e) {
  const r = cv.getBoundingClientRect();
  const cx = (e.clientX - r.left) * cv.width / r.width, cy = (e.clientY - r.top) * cv.height / r.height;
  return [(cx - vp.x) / vp.s, (cy - vp.y) / vp.s];
}

function image(url) {
  if (!url) return null;
  if (!images[url]) { images[url] = new Image(); images[url].onload = draw; images[url].src = url; }
  return images[url].complete ? images[url] : null;
}
const css = getComputedStyle(document.documentElement);
const C = name => css.getPropertyValue('--' + name).trim();
// A line in its colour over a thin dark edge, so it shows on the light road and the dark walls.
function line(pts, color, closed, width) {
  if (!pts || pts.length < 2) return;
  ctx.beginPath();
  pts.forEach((p, i) => { const q = toCanvas(p); i ? ctx.lineTo(...q) : ctx.moveTo(...q); });
  if (closed) ctx.closePath();
  ctx.lineJoin = 'round';
  ctx.strokeStyle = 'rgba(0,0,0,.65)'; ctx.lineWidth = (width || 2) + 2.5; ctx.stroke();
  ctx.strokeStyle = color; ctx.lineWidth = width || 2; ctx.stroke();
}
// An arrowhead every 80 canvas pixels along the loop, in its order.
function arrows(pts, color) {
  const c = pts.map(toCanvas); let done = 0, next = 30;
  ctx.fillStyle = color; ctx.strokeStyle = 'rgba(0,0,0,.65)'; ctx.lineWidth = 1.5;
  for (let i = 1; i < c.length; i++) {
    const [a, b] = [c[i - 1], c[i]], seg = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const t = Math.atan2(b[1] - a[1], b[0] - a[0]);
    for (; next <= done + seg; next += 80) {
      const f = (next - done) / seg, x = a[0] + (b[0] - a[0]) * f, y = a[1] + (b[1] - a[1]) * f;
      ctx.beginPath(); ctx.moveTo(x + 10 * Math.cos(t), y + 10 * Math.sin(t));
      ctx.lineTo(x - 7 * Math.cos(t - .5), y - 7 * Math.sin(t - .5));
      ctx.lineTo(x - 7 * Math.cos(t + .5), y - 7 * Math.sin(t + .5)); ctx.closePath();
      ctx.stroke(); ctx.fill();
    }
    done += seg;
  }
}
function draw() {
  if (!V.size) { ctx.clearRect(0, 0, cv.width, cv.height); return; }
  ctx.fillStyle = '#222'; ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.imageSmoothingEnabled = false;
  // The map dimmed, so the road is a mid grey and every line shows on it.
  for (const [url, layer, alpha] of [[V.png, 'map', .55], [V.excluded_png, 'road', 1]]) {
    const img = shown[layer] && image(url);
    ctx.globalAlpha = alpha;
    if (img) ctx.drawImage(img, vp.x, vp.y, V.size[0] * vp.s, V.size[1] * vp.s);
    ctx.globalAlpha = 1;
  }
  if (shown.road) {
    (V.walls_px || []).forEach(w => line(w, C('walls'), true));
    V.strokes_px.forEach((s, i) => {
      const color = i === picked ? C('picked') : C('stroke');
      line(s, color, false, i === picked ? 5 : 3);
      const [x, y] = toCanvas(s[0]);
      ctx.font = 'bold 13px system-ui'; ctx.lineWidth = 3; ctx.strokeStyle = '#000';
      ctx.strokeText(String(i + 1), x + 5, y - 5); ctx.fillStyle = color;
      ctx.fillText(String(i + 1), x + 5, y - 5);
    });
  }
  if (shown.guide) {
    line(V.guide_px, C('guide')); arrows(V.guide_px, C('guide'));
    if (V.start_px) {
      const [x, y] = toCanvas(V.start_px);
      ctx.beginPath(); ctx.arc(x, y, 7, 0, 2 * Math.PI);
      ctx.fillStyle = C('startmark'); ctx.strokeStyle = '#000'; ctx.lineWidth = 2;
      ctx.fill(); ctx.stroke();
    }
  }
  const R = shown.route && V.result;
  if (R) {
    R.left_px.concat(R.right_px).forEach(w => line(w, C('route'), false, 2.5));
    if (R.start_px.length > 2) {
      ctx.beginPath();
      R.start_px.forEach((p, i) => { const q = toCanvas(p); i ? ctx.lineTo(...q) : ctx.moveTo(...q); });
      ctx.closePath(); ctx.globalAlpha = .4; ctx.fillStyle = C('start'); ctx.fill(); ctx.globalAlpha = 1;
    }
    line(R.start_px, C('start'), true, 1.5);
    R.gates_px.forEach(g => line(g, C('gates'), false, 3.5));
  }
  // Where the route fails: a ring round every cell named.
  ctx.strokeStyle = C('problem'); ctx.lineWidth = 2.5;
  (V.problem_px || []).forEach(p => {
    const [x, y] = toCanvas(p);
    ctx.beginPath(); ctx.arc(x, y, Math.max(5, vp.s), 0, 2 * Math.PI); ctx.stroke();
  });
  // The line being drawn: its points, and dashed where the next click would take it.
  const color = refused ? C('problem') : tool === 'stroke' ? C('stroke') : C('guide');
  if (refused) ctx.setLineDash([6, 4]);
  line(draft, color);
  ctx.setLineDash([]);
  ctx.fillStyle = color;
  draft.forEach(p => { const [x, y] = toCanvas(p); ctx.fillRect(x - 3, y - 3, 6, 6); });
  if (draft.length && hover) {
    ctx.setLineDash([5, 4]);
    line([draft.at(-1), hover], color);
    if (tool === 'guide' && draft.length > 1) line([hover, draft[0]], color, false, 1);
    ctx.setLineDash([]);
  }
}

let framed = null, framedMap = null;
function showAvailability() {
  for (const [action, disabled] of Object.entries({
    save: sourceChanged, export: !V.result || sourceChanged || carUnavailable
  })) {
    $(action).disabled = disabled;
    document.querySelector('[data-command="' + action + '"]').disabled = disabled;
  }
}

function show(view, message) {
  V = view;
  $('caption').textContent = `${V.map || 'Untitled'} - ForzaETH Annotation`;
  $('maps').replaceChildren(...V.maps.map(m => new Option(m, m, false, m === V.map)));
  for (const k of ['name', 'surface', 'max_speed_mps', 'stroke_width_px'])
    if (k in V && document.activeElement !== $(k)) $(k).value = V[k];
  // Frame the track again when another map opens or the track changes; zoom and pan stay
  // otherwise, also while the track is open.
  const frame = V.walls_px || V.map !== framedMap ? V.size && V.map + bounds().join() : framed;
  if (frame !== framed) { framed = frame; framedMap = V.map; fit(); }
  showAvailability();
  // One button per drawn wall, to remove it.
  picked = -1;
  $('strokes').replaceChildren(...(V.strokes_px || []).map((_, i) => {
    const b = document.createElement('button');
    b.textContent = `remove wall ${i + 1}`;
    b.onmouseenter = b.onfocus = () => { picked = i; draw(); };
    b.onmouseleave = b.onblur = () => { picked = -1; draw(); };
    b.onclick = () => edit('strokes_px', V.strokes_px.filter((_, k) => k !== i));
    return b;
  }));
  $('no-walls').hidden = $('strokes').childElementCount > 0;
  $('status').textContent = (message ? message + '\n' : '') + (V.map ?
    `${V.map} · road: ${V.walls_error || 'closed ring'} · guide: ` +
    `${V.guide_auto ? 'suggested, follows the road' : 'drawn'}\nroute: ${V.route}` :
    message ? '' : 'Pick a map and press Open.');
  $('status').scrollTop = 0;
  draw();
}
async function finish() {
  // A double-click also fired two clicks on the same spot: keep one.
  while (draft.length > 1 && Math.hypot(...draft.at(-1).map((v, i) => v - draft.at(-2)[i])) < .5) draft.pop();
  const done = draft, drawing = tool; draft = []; hover = null; refused = false;
  if (done.length < 2 || (drawing === 'guide' && done.length < 3)) return draw();
  const ok = drawing === 'stroke' ? await edit('strokes_px', [...V.strokes_px, done])
                                  : await edit('guide_px', [...done, done[0]]);
  // A refused line shows where it was.
  if (!ok && tool === drawing) {
    draft = done; refused = true; draw();
    // Shown for a moment, then gone; the status keeps saying why.
    setTimeout(() => { if (refused && draft === done) { draft = []; refused = false; draw(); } },
               REFUSED_MS);
  }
}
async function call(action, body) {
  document.body.classList.add('busy');
  try {
    const response = await fetch('api/' + action, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {})
    });
    const r = await response.json();
    if (!response.ok) throw Error(r.error || response.statusText);
    show(r.view, (r.ok ? '' : 'REFUSED: ') + r.message);
    if (embedded) window.parent.postMessage({type: 'annotation-updated'}, location.origin);
    return r.ok;
  } catch (e) {
    $('status').textContent = 'FAILED: the editor is not answering (' + e + ')';
    return false;
  } finally { document.body.classList.remove('busy'); }
}
const edit = (field, value) => call('edit', {field, value});

cv.addEventListener('click', e => {
  if (!V.size || pan) return;
  const p = toPixel(e);
  if (tool === 'region') return edit('region_px', p.map(Math.round));
  if (tool === 'start') return edit('start_px', p);
  if (!tool) return;
  // A click while a refused line shows starts a new one.
  if (refused) { draft = []; refused = false; }
  // A click on the guide's first point closes it.
  const [fx, fy] = draft.length > 2 ? toCanvas(draft[0]) : [Infinity, Infinity];
  const [cx, cy] = toCanvas(p);
  if (tool === 'guide' && Math.hypot(cx - fx, cy - fy) < CLOSE_PX) return finish();
  draft.push(p); draw();
});
cv.addEventListener('dblclick', finish);
cv.addEventListener('mousemove', e => { if (draft.length && !pan && !refused) { hover = toPixel(e); draw(); } });
cv.addEventListener('mouseleave', () => { hover = null; draw(); });
cv.addEventListener('contextmenu', e => e.preventDefault());
cv.addEventListener('mousedown', e => { if (e.button > 0 && vp) pan = {x: e.clientX, y: e.clientY, vx: vp.x, vy: vp.y}; });
window.addEventListener('mouseup', () => setTimeout(() => pan = null));
window.addEventListener('mousemove', e => {
  if (!pan) return;
  const k = cv.width / cv.getBoundingClientRect().width;
  vp.x = pan.vx + (e.clientX - pan.x) * k; vp.y = pan.vy + (e.clientY - pan.y) * k; draw();
});
cv.addEventListener('wheel', e => {
  if (!vp) return;
  e.preventDefault();
  const p = toPixel(e), s = vp.s * (e.deltaY < 0 ? 1.15 : 1 / 1.15);
  vp = {s, x: vp.x + p[0] * (vp.s - s), y: vp.y + p[1] * (vp.s - s)}; draw();
}, {passive: false});
window.addEventListener('keydown', e => {
  if (/INPUT|SELECT/.test(e.target.tagName)) return;
  if (e.key === 'Escape') { draft = []; refused = false; draw(); }
  if (e.key === 'Backspace' && draft.length) { e.preventDefault(); draft.pop(); draw(); }
});

document.querySelectorAll('.tool').forEach(b => b.onclick = () => {
  tool = tool === b.dataset.tool ? null : b.dataset.tool; draft = []; hover = null; refused = false;
  document.querySelectorAll('.tool').forEach(x => {
    const active = x.classList.toggle('on', x.dataset.tool === tool);
    x.setAttribute('aria-pressed', active);
  });
  $('hint').textContent = HINTS[tool];
  $('hint').scrollTop = 0;
  draw();
});
$('open').onclick = () => call('open', {map: $('maps').value});
$('name').onchange = e => edit('name', e.target.value);
$('surface').onchange = e => edit('surface', e.target.value);
$('max_speed_mps').onchange = e => edit('max_speed_mps', parseFloat(e.target.value));
$('stroke_width_px').onchange = e => edit('stroke_width_px', parseInt(e.target.value));
$('suggest').onclick = () => call('suggest');
$('reverse').onclick = () => call('reverse');
$('clearGuide').onclick = () => edit('guide_px', []);
for (const a of ['export', 'save']) $(a).onclick = () => call(a);
$('fit').onclick = () => { fit(); draw(); };
document.querySelectorAll('.layer').forEach(c => c.onchange = () => { shown[c.value] = c.checked; draw(); });

const menus = document.querySelector('.menubar');
function dismissMenu(restoreFocus = false) {
  const open = menus.querySelector('details[open]');
  if (!open) return;
  open.open = false;
  if (restoreFocus) open.querySelector('summary').focus();
}
document.addEventListener('click', e => {
  if (!menus.contains(e.target)) { dismissMenu(); return; }
  const button = e.target.closest('button');
  if (!button) return;
  dismissMenu(true);
  if (button.dataset.command) $(button.dataset.command).click();
});
document.addEventListener('focusin', e => { if (!menus.contains(e.target)) dismissMenu(); });
menus.addEventListener('keydown', e => {
  if (e.key !== 'Escape' || !menus.querySelector('details[open]')) return;
  e.stopPropagation();
  dismissMenu(true);
});

new ResizeObserver(resize).observe(cv);
resize();
if (embedded) window.addEventListener('message', event => {
  if (event.origin !== location.origin || event.source !== window.parent) return;
  if (event.data?.type === 'open-map') call('open', {map: event.data.map});
  if (event.data?.type === 'annotation-status') {
    sourceChanged = event.data.sourceChanged;
    carUnavailable = event.data.carUnavailable;
    showAvailability();
  }
});
fetch('api/view').then(r => r.json()).then(v => show(v)).catch(error => {
  $('status').textContent = 'FAILED: the editor is not answering (' + error + ')';
});
