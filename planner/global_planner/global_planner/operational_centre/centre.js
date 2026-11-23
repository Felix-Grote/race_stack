// The Operational Centre: tabs, the embedded editor, and the Tracks comparison.
import {$, api, element, notice, status} from './common.js';
import {drawPlots, fit, zoom} from './plots.js';
import {bindWorksheet, showWorksheet, unapplied} from './worksheet.js';

const labels = {gentle: 'Gentle', balanced: 'Balanced', aggressive: 'Aggressive'};
const visible = new Set(Object.keys(labels));
const tabs = [...document.querySelectorAll('[role="tab"]')];
let state, view, mapName, selection, requestNumber = 0, connected = false;
const emptyView = {walls: [], gates: [], start: [], period_m: 0, lines: {}};

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
    drawPlots(view || emptyView, visible, state.profiles);
  };
  const name = element('label');
  name.htmlFor = toggle.id;
  const swatch = element('i', '', 'swatch ' + kind);
  swatch.setAttribute('aria-hidden', 'true');
  name.append(swatch, document.createTextNode(title));
  const badge = element('span', 'Missing', 'trajectory-status');
  badge.id = 'result-' + kind;
  const detail = element('p', '', 'trajectory-detail');
  detail.id = 'detail-' + kind;
  row.append(toggle, name, badge, detail);
  $('trajectory-list').append(row);
  const metrics = element('tr');
  const heading = element('th', title);
  heading.scope = 'row';
  const timing = element('td', '–'), delta = element('td', '–');
  timing.id = 'time-' + kind;
  delta.id = 'delta-' + kind;
  metrics.append(heading, timing, delta);
  $('metrics-rows').append(metrics);
}

function profileInputs({alpha, margin_m, gamma}) {
  return 'α ' + Math.round(alpha * 100) + '% · ' + (margin_m * 100).toFixed(1)
    + ' cm required · γ ' + (gamma == null ? '–' : gamma.toPrecision(3));
}

function updateTracks() {
  const {map, maps, car, track, job, summaries, settings, annotation, profiles} = state;
  if (Array.from($('map').options, option => option.value).join('\n') !== maps.join('\n')) {
    $('map').replaceChildren(...maps.map(item => new Option(item, item)));
    if (!maps.length) $('map').append(new Option('No maps found', ''));
  }
  $('map').disabled = !maps.length;
  $('map').value = map || '';
  status('car', car.name || 'Car model unavailable');
  $('car').title = car.message || '';
  const routeLabels = {ready: 'Route ready', missing: 'Missing route', invalid: 'Invalid route',
                       stale: 'Route stale', unverified: 'Unverified calibration'};
  status('route-status', routeLabels[track.status] + ' · ' + track.message);
  status('route-identity', track.digest ? track.sections + ' sections · ' + track.digest.slice(0, 10) : '');
  $('open-in-editor').disabled = !map;
  $('generate').disabled = !connected || !track.digest || !car.timing || Boolean(settings.error || job?.running);
  $('stop').disabled = !connected || !job?.running;

  const attempts = job?.map === map ? job.attempts : {};
  let current = 0;
  const balanced = summaries.balanced.status === 'current' ? summaries.balanced.metrics.lap_time_s : null;
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
    const metrics = available ? item.metrics : null;
    const messages = [item.message, failed && attempt.message].filter(Boolean);
    const policy = profileInputs(profiles[kind]);
    const detail = metrics ? metrics.length_m.toFixed(2) + ' m lap · '
      + (metrics.min_clearance_m * 100).toFixed(1) + ' cm minimum clearance' : policy;
    status('detail-' + kind, messages.join(' ') || detail);
    $('trajectory-' + kind).title = policy;
    status('time-' + kind, metrics ? metrics.lap_time_s.toFixed(2) + ' s' : '–');
    const delta = metrics && balanced != null ? metrics.lap_time_s - balanced : null;
    status('delta-' + kind, delta == null || kind === 'balanced' ? '–' :
      (delta >= 0.005 ? '+' : '') + (Math.abs(delta) < 0.005 ? '0.00' : delta.toFixed(2)) + ' s');
  }

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
    unapplied() && 'Unapplied values. Generation uses the saved worksheet.',
    settings.error && 'Saved optimizer settings need attention.',
    car.message,
  ].filter(Boolean).join(' ') || 'Using saved route and applied optimizer values.');
  status('layer-status', current + ' of 3 profiles current');
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
      drawPlots(view, visible, state.profiles);
    }
    notice('connection');
    updateAnnotation();
    showWorksheet(state, connected);
    updateTracks();
  } catch (error) {
    if (request !== requestNumber) return;
    connected = false;
    notice('connection', 'Workspace unavailable. ' + error.message);
    if (state) {
      showWorksheet(state, connected);
      updateTracks();
    }
  }
}

$('generate').onclick = () => {
  selection = {map: state.map, revision: state.revision};
  status('generate-map', state.map + ' · ' + state.car.name);
  const choices = Object.entries(labels).map(([kind, name]) => {
    const label = element('label');
    const checkbox = element('input');
    checkbox.type = 'checkbox';
    checkbox.value = kind;
    checkbox.name = 'category';
    checkbox.checked = true;
    label.append(checkbox, document.createTextNode(' ' + name));
    label.append(element('small', profileInputs(state.profiles[kind])));
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
$('refresh-inputs').onclick = refresh;
$('fit').onclick = fit;
$('zoom-in').onclick = () => zoom(0.75);
$('zoom-out').onclick = () => zoom(1 / 0.75);
document.querySelectorAll('[data-close]').forEach(button =>
  button.onclick = () => button.closest('dialog').close());
document.querySelectorAll('[data-help]').forEach(button =>
  button.onclick = () => $('help-dialog').showModal());
bindWorksheet(refresh, () => { if (state) updateTracks(); });
refresh();
setInterval(refresh, 1800);
