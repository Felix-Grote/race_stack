// The Settings tab: one value per exposed optimizer setting, applied to every map.
import {$, api, element, notice, status} from './common.js';

let state, connected = false, revision, edited = false, saving = false;
let refresh = () => {}, changed = () => {};

export const unapplied = () => edited;

export function bindWorksheet(onRefresh, onChange) {
  refresh = onRefresh;
  changed = onChange;
}

function build(values) {
  $('parameter-rows').replaceChildren(...Object.entries(state.parameters).map(([key, item]) => {
    const heading = element('th');
    heading.scope = 'row';
    heading.append(element('strong', item.label + (item.unit ? ' (' + item.unit + ')' : '')),
                   element('span', item.hint));
    const input = element('input');
    Object.assign(input, {type: 'number', step: item.integer ? '1' : 'any', min: item.min,
                          max: item.max, value: values[key], name: key});
    input.setAttribute('aria-label', item.label);
    const cell = element('td'), row = element('tr');
    cell.append(input);
    row.append(heading, cell);
    return row;
  }));
}

function load() {
  revision = state.settings.revision;
  edited = false;
  build(state.settings.parameters);
  notice('settings-error');
}

export function showWorksheet(next, online) {
  state = next;
  connected = online;
  if (revision !== state.settings.revision && !edited && !saving) load();
  const conflict = revision !== state.settings.revision;
  status('worksheet-status', conflict
    ? 'Saved values changed on disk. Reload saved values before applying.'
    : state.settings.error || (edited ? 'Unapplied changes' : 'Using applied values'));
  $('apply').disabled = !connected || saving || conflict || (!edited && !state.settings.error);
  $('parameters-form').querySelector('fieldset').disabled = saving;
  $('reload-settings').disabled = saving;
  $('defaults').disabled = saving;
}

function edit() {
  edited = true;
  notice('settings-error');
  showWorksheet(state, connected);
  changed();
}

$('parameters-form').oninput = edit;
$('defaults').onclick = () => {
  if (!state) return;
  build(Object.fromEntries(Object.entries(state.parameters).map(([key, item]) =>
    [key, item.default])));
  edit();
};
$('reload-settings').onclick = () => {
  if (!state) return;
  load();
  showWorksheet(state, connected);
  changed();
};
$('parameters-form').onsubmit = async event => {
  event.preventDefault();
  if ($('apply').disabled) return;
  const inputs = $('parameters-form').elements;
  const parameters = Object.fromEntries(Object.keys(state.parameters).map(key =>
    [key, inputs.namedItem(key).valueAsNumber]));
  saving = true;
  showWorksheet(state, connected);
  try {
    await api('settings', {revision, parameters});
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
