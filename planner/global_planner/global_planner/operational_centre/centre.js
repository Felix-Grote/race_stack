import {drawPlots, fit, zoom} from './plots.js';

const $ = id => document.getElementById(id);
const labels = {
  centreline: 'Centreline',
  curvature: 'Minimum curvature',
  laptime: 'Lap time',
};
const descriptions = {
  centreline: 'Geometric reference',
  curvature: 'Optimized for smoothness',
  laptime: 'Optimized for flying lap time',
};
const visible = new Set(Object.keys(labels));
const tabs = [...document.querySelectorAll('[role="tab"]')];
let state, view, mapName, requestNumber = 0;
let edited = false, revision, saving = false, selection;
let connected = false;
const emptyView = {walls: [], gates: [], start: [], lines: {}};

function status(id, message) {
  const element = $(id);
  if (element.textContent !== message) element.textContent = message;
}

function notice(id, message = '') {
  status(id, message);
  $(id).hidden = !message;
}

function element(tag, label, className) {
  const item = document.createElement(tag);
  if (label) item.textContent = label;
  if (className) item.className = className;
  return item;
}

async function api(action, body) {
  const response = await fetch('/api/centre/' + action, body === undefined ? {} : {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw Error(payload.error || response.statusText);
  return payload;
}

function activate(id, focus = false) {
  for (const tab of tabs) {
    const selected = tab.getAttribute('aria-controls') === id;
    tab.setAttribute('aria-selected', selected);
    tab.tabIndex = selected ? 0 : -1;
    $(tab.getAttribute('aria-controls')).hidden = !selected;
    if (selected && focus) tab.focus();
  }
  document.querySelectorAll('.menubar details[open]').forEach(menu => menu.open = false);
}

function tabFromHash() {
  const id = location.hash.slice(1);
  activate(tabs.some(tab => tab.getAttribute('aria-controls') === id) ? id : 'tracks');
}

for (const [index, tab] of tabs.entries()) {
  tab.onclick = () => { location.hash = tab.getAttribute('aria-controls'); };
  tab.onkeydown = event => {
    const indexes = {ArrowLeft: (index + tabs.length - 1) % tabs.length,
                     ArrowRight: (index + 1) % tabs.length, Home: 0, End: tabs.length - 1};
    if (!(event.key in indexes)) return;
    event.preventDefault();
    const id = tabs[indexes[event.key]].getAttribute('aria-controls');
    activate(id, true);
    location.hash = id;
  };
}
window.addEventListener('hashchange', tabFromHash);
tabFromHash();

function sendEditor(details) {
  $('editor').contentWindow.postMessage(details, location.origin);
}

function updateAnnotation() {
  if (!state) return;
  const annotation = state.annotation;
  status('annotation-status', annotation.message);
  sendEditor({type: 'annotation-status', sourceChanged: Boolean(annotation.source_changed),
              carUnavailable: Boolean(annotation.export_blocked)});
}

$('editor').addEventListener('load', updateAnnotation);
window.addEventListener('message', event => {
  if (event.origin === location.origin && event.source === $('editor').contentWindow &&
      event.data?.type === 'annotation-updated') refresh();
});
$('open-in-editor').onclick = () => {
  location.hash = 'annotator';
  if (state.map !== state.annotation.map) sendEditor({type: 'open-map', map: state.map});
};
$('map').onchange = () => {
  mapName = $('map').value;
  refresh();
};

function buildWorksheet(values) {
  const rows = Object.entries(state.parameters).map(([key, parameter]) => {
    const row = element('tr');
    const heading = element('th');
    heading.scope = 'row';
    heading.append(element('strong', parameter.label + (parameter.unit ? ' (' + parameter.unit + ')' : '')));
    heading.append(element('span', parameter.hint));
    row.append(heading);
    for (const [field, label] of [['value', 'value'], ['lower', 'lower bound'], ['upper', 'upper bound']]) {
      const cell = element('td');
      const input = element('input');
      input.type = 'number';
      input.step = parameter.integer ? '1' : 'any';
      input.min = parameter.lower;
      input.max = parameter.upper;
      input.value = values[key][field];
      input.name = key + '-' + field;
      input.setAttribute('aria-label', parameter.label + ' ' + label);
      row.append(cell);
      cell.append(input);
    }
    return row;
  });
  $('parameter-rows').replaceChildren(...rows);
}

function loadWorksheet() {
  revision = state.settings.revision;
  edited = false;
  buildWorksheet(state.settings.parameters);
  notice('settings-error');
  updateWorksheet();
}

function updateWorksheet() {
  if (!state) return;
  const conflict = revision !== state.settings.revision;
  if ((revision === undefined || conflict) && !edited && !saving) {
    loadWorksheet();
    return;
  }
  status('worksheet-status', conflict
    ? 'Saved values changed on disk. Reload saved values before applying.'
    : state.settings.error || (edited ? 'Unapplied changes' : 'Using applied values'));
  $('apply').disabled = !connected || saving || conflict || (!edited && !state.settings.error);
  $('parameters-form').querySelector('fieldset').disabled = saving;
  $('reload-settings').disabled = saving;
  $('defaults').disabled = saving;
}

$('parameters-form').oninput = () => {
  edited = true;
  notice('settings-error');
  updateWorksheet();
  if (state) updateTracks();
};
$('reload-settings').onclick = () => { if (state) { loadWorksheet(); updateTracks(); } };
$('defaults').onclick = () => {
  if (!state) return;
  const defaults = Object.fromEntries(Object.entries(state.parameters).map(([key, item]) =>
    [key, {value: item.default, lower: item.lower, upper: item.upper}]));
  buildWorksheet(defaults);
  edited = true;
  notice('settings-error');
  updateWorksheet();
  updateTracks();
};

$('parameters-form').onsubmit = async event => {
  event.preventDefault();
  if ($('apply').disabled) return;
  const inputs = $('parameters-form').elements;
  const values = Object.fromEntries(Object.keys(state.parameters).map(key =>
    [key, Object.fromEntries(['value', 'lower', 'upper'].map(field =>
      [field, inputs.namedItem(key + '-' + field).valueAsNumber]))]));
  saving = true;
  updateWorksheet();
  try {
    await api('settings', {revision, parameters: values});
    edited = false;
    revision = undefined;
    notice('settings-error');
  } catch (error) {
    notice('settings-error', error.message);
  } finally {
    saving = false;
    await refresh();
  }
};

for (const [kind, title] of Object.entries(labels)) {
  const row = element('div', '', 'trajectory');
  row.id = 'trajectory-' + kind;
  const toggle = element('input');
  toggle.type = 'checkbox';
  toggle.id = 'show-' + kind;
  toggle.checked = true;
  toggle.disabled = true;
  toggle.onchange = () => {
    if (toggle.checked) visible.add(kind);
    else visible.delete(kind);
    drawPlots(view || emptyView, visible);
  };
  const name = element('label');
  name.htmlFor = toggle.id;
  const swatch = element('i', '', 'swatch ' + kind);
  swatch.setAttribute('aria-hidden', 'true');
  name.append(swatch, document.createTextNode(title));
  const badge = element('span', 'Missing', 'trajectory-status');
  badge.id = 'result-' + kind;
  const detail = element('p', descriptions[kind], 'trajectory-detail');
  detail.id = 'detail-' + kind;
  row.append(toggle, name, badge, detail);
  $('trajectory-list').append(row);
  const metrics = element('tr');
  const heading = element('th', title);
  heading.scope = 'row';
  const length = element('td', '–'), timing = element('td', '–');
  length.id = 'length-' + kind;
  timing.id = 'time-' + kind;
  metrics.append(heading, length, timing);
  $('metrics-rows').append(metrics);
}

function updateTracks() {
  const {map, maps, car, track, job, summaries, settings, annotation} = state;
  if (Array.from($('map').options, option => option.value).join('\n') !== maps.join('\n')) {
    $('map').replaceChildren(...maps.map(item => new Option(item, item)));
    if (!maps.length) $('map').append(new Option('No maps found', ''));
  }
  $('map').disabled = !maps.length;
  $('map').value = map || '';
  status('car', car.name ? car.name + ' · ' + car.margin.toFixed(2) + ' m clearance' : 'Car model unavailable');
  $('car').title = car.message || '';
  const routeLabels = {ready: 'Route ready', missing: 'Missing route', invalid: 'Invalid route',
                       stale: 'Route stale', unverified: 'Unverified calibration'};
  status('route-status', routeLabels[track.status] + ' · ' + track.message);
  status('route-identity', track.digest ? track.sections + ' sections · ' + track.digest.slice(0, 10) : '');
  $('open-in-editor').disabled = !map;
  $('generate').disabled = !connected || !track.digest || Boolean(job?.running);
  $('stop').disabled = !connected || !job?.running;

  const attempts = job?.map === map ? job.attempts : {};
  let current = 0;
  for (const [kind, item] of Object.entries(summaries)) {
    const attempt = attempts[kind];
    const running = job?.running && ['queued', 'running'].includes(attempt?.status);
    const failed = ['failed', 'cancelled'].includes(attempt?.status);
    const available = item.status === 'current';
    if (available) current++;
    $('show-' + kind).disabled = !available;
    const label = running ? attempt.status : (failed && item.status === 'missing' ? attempt.status : item.status);
    $('trajectory-' + kind).dataset.status = label;
    status('result-' + kind, label[0].toUpperCase() + label.slice(1));
    const messages = [item.message, failed && attempt.message].filter(Boolean);
    status('detail-' + kind, messages.join(' ') || descriptions[kind]);
    const metrics = available ? item.metrics : null;
    status('length-' + kind, metrics ? metrics.length_m.toFixed(2) + ' m' : '–');
    status('time-' + kind, metrics?.lap_time_s != null ? metrics.lap_time_s.toFixed(2) + ' s' : '–');
  }
  const curve = summaries.curvature.status === 'current' ? summaries.curvature.metrics.lap_time_s : null;
  const timed = summaries.laptime.status === 'current' ? summaries.laptime.metrics.lap_time_s : null;
  const difference = curve != null && timed != null ? timed - curve : null;
  notice('lap-delta', difference == null ? '' :
    'Lap time vs minimum curvature · ' + (difference > 0 ? '+' : '') + difference.toFixed(2) + ' s');

  const allAttempts = Object.entries(job?.attempts || {});
  const active = allAttempts.find(([, attempt]) => attempt.status === 'running');
  const completed = allAttempts.filter(([, attempt]) => !['running', 'queued'].includes(attempt.status)).length;
  const succeeded = allAttempts.filter(([, attempt]) => attempt.status === 'complete').length;
  status('job-status', job?.running
    ? (active ? labels[active[0]] + ' running' : 'Starting planner') + ' · ' + job.map
    : job ? succeeded + ' of ' + completed + ' completed · ' + job.map : 'No job running.');
  $('progress').hidden = !job?.running;
  $('progress').setAttribute('aria-valuemax', allAttempts.length || 1);
  $('progress').setAttribute('aria-valuenow', completed);
  $('progress').firstElementChild.style.width = (allAttempts.length ? completed / allAttempts.length * 100 : 0) + '%';
  status('generation-inputs', [
    annotation.draft_differs && 'Draft differs from the saved route.',
    edited && 'Unapplied values. Generation uses the saved worksheet.',
    settings.error && 'Saved optimizer settings need attention.',
    car.message,
  ].filter(Boolean).join(' ') || 'Using saved route and applied optimizer values.');
  status('layer-status', current + ' of 3 trajectories current');
  for (const button of document.querySelectorAll('[data-command]')) {
    const target = $(button.dataset.command);
    if (target) button.disabled = target.disabled;
  }
}

async function refresh() {
  const request = ++requestNumber;
  const query = new URLSearchParams();
  if (mapName) query.set('map', mapName);
  if (view) query.set('view', view.id);
  try {
    const next = await api('state?' + query);
    if (request !== requestNumber) return;
    connected = true;
    state = next;
    mapName = next.map;
    if (state.view) {
      view = state.view;
      drawPlots(view, visible);
    }
    notice('connection');
    updateAnnotation();
    updateWorksheet();
    updateTracks();
  } catch (error) {
    if (request !== requestNumber) return;
    connected = false;
    notice('connection', 'Workspace unavailable. ' + error.message);
    if (state) {
      updateWorksheet();
      updateTracks();
    }
  }
}

$('generate').onclick = () => {
  selection = {map: state.map, revision: state.revision};
  status('generate-map', state.map + ' · ' + (state.car.name || 'Geometry only'));
  const choices = Object.entries(labels).map(([kind, name]) => {
    const label = element('label');
    const checkbox = element('input');
    checkbox.type = 'checkbox';
    checkbox.value = kind;
    checkbox.name = 'category';
    checkbox.disabled = kind !== 'centreline' &&
      (Boolean(state.settings.error) || !state.car.name || (kind === 'laptime' && !state.car.timing));
    checkbox.checked = !checkbox.disabled;
    label.append(checkbox, document.createTextNode(' ' + name));
    label.append(element('small', checkbox.disabled ? 'Unavailable with the current inputs' : descriptions[kind]));
    return label;
  });
  $('generate-choices').replaceChildren(...choices);
  $('legacy-warning').hidden = state.track.status !== 'unverified';
  $('allow-unverified').checked = false;
  status('legacy-message', state.track.message);
  notice('generate-error');
  $('generate-dialog').showModal();
};

$('generate-form').onsubmit = async event => {
  event.preventDefault();
  const categories = [...$('generate-choices').querySelectorAll('input:checked')].map(input => input.value);
  $('run').disabled = true;
  try {
    await api('generate', {...selection, categories, allow_unverified: $('allow-unverified').checked});
    $('generate-dialog').close();
    await refresh();
  } catch (error) {
    notice('generate-error', error.message);
    await refresh();
  } finally {
    $('run').disabled = false;
  }
};

$('stop').onclick = async () => {
  try {
    await api('stop', {id: state.job.id});
    notice('track-error');
  } catch (error) {
    notice('track-error', error.message);
  }
  await refresh();
};
$('fit').onclick = fit;
$('zoom-in').onclick = () => zoom(0.75);
$('zoom-out').onclick = () => zoom(1 / 0.75);
document.querySelectorAll('[data-close]').forEach(button =>
  button.onclick = () => button.closest('dialog').close());
document.querySelectorAll('[data-help]').forEach(button =>
  button.onclick = () => $('help-dialog').showModal());
document.addEventListener('click', event => {
  for (const menu of document.querySelectorAll('.menubar details[open]')) {
    const button = event.target.closest('button');
    if (!menu.contains(event.target) || button) menu.open = false;
    if (button && menu.contains(button)) {
      if (!document.querySelector('dialog[open]')) menu.querySelector('summary').focus();
      const command = button.dataset.command;
      if (command === 'refresh') refresh();
      else if (command) $(command)?.click();
    }
  }
});
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  const openMenu = document.querySelector('.menubar details[open]');
  if (openMenu) {
    openMenu.open = false;
    openMenu.querySelector('summary').focus();
  }
});

refresh();
setInterval(refresh, 1800);
