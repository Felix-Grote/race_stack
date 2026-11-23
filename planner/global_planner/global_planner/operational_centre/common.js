// Small helpers shared by the Operational Centre's modules.
export const $ = id => document.getElementById(id);

export function status(id, message) {
  const element = $(id);
  if (element.textContent !== message) element.textContent = message;
}

export function notice(id, message = '') {
  status(id, message);
  $(id).hidden = !message;
}

export function element(tag, label, className) {
  const item = document.createElement(tag);
  if (label) item.textContent = label;
  if (className) item.className = className;
  return item;
}

// An SVG path through points, closed when asked.
export function path(points, closed = false) {
  return points.length ? 'M' + points.map(([x, y]) => [Number(x), Number(y)].join(',')).join('L')
    + (closed ? 'Z' : '') : '';
}

export async function api(action, body) {
  const response = await fetch('/api/centre/' + action, body === undefined ? {} : {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw Error(payload.error || response.statusText);
  return payload;
}
