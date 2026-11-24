// Export to car: which line goes into each slot of the map's global_waypoints.json.
import {$, api, notice, status} from './common.js';

let current, selection;

/*
 * getState: returns the Centre's last state.
 * labels:   each profile's name.
 * facts:    heads the dialog with the map and the car.
 * refresh:  reloads the state once the file is written, or the export refused.
 */
export function bindExport(getState, labels, facts, refresh) {
  current = getState;
  $('export').onclick = () => {
    const state = current();
    selection = {map: state.map, revision: state.revision};
    facts('export-map', [['Writes', state.map.split('/')[0] + '/global_waypoints.json']]);
    for (const [slot, preferred] of [['raceline', 'balanced'], ['shortest_path', 'shortest']]) {
      const select = $('export-' + slot);
      const kept = select.value;
      select.replaceChildren(...state.exportable.map(kind => new Option(labels[kind], kind)),
                             new Option('Centreline', 'centreline'));
      select.value = [kept, preferred].find(kind => state.exportable.includes(kind)) || select.value;
    }
    notice('export-error', state.exportable.length ? ''
      : 'No driving profile is current for these inputs: generate one first, or the car gets the centreline.');
    exportChoice();
    $('export-dialog').showModal();
  };

  // Next to each choice, what is known of that line; and the centreline's caveat only when the
  // centreline is about to go to the car.
  function exportChoice() {
    const state = current();
    const slots = ['raceline', 'shortest_path'];
    for (const slot of slots) {
      const metrics = state.summaries[$('export-' + slot).value]?.metrics;
      status('export-' + slot + '-time', metrics ? metrics.lap_time_s.toFixed(2) + ' s' : '–');
      status('export-' + slot + '-length', metrics ? metrics.length_m.toFixed(2) + ' m' : '–');
    }
    $('export-centreline-note').hidden = !slots.some(slot => $('export-' + slot).value === 'centreline');
  }
  $('export-raceline').onchange = $('export-shortest_path').onchange = exportChoice;

  $('export-form').onsubmit = async event => {
    event.preventDefault();
    $('export-run').disabled = true;
    try {
      const {note} = await api('export', {...selection, raceline: $('export-raceline').value,
                                          shortest_path: $('export-shortest_path').value});
      $('export-dialog').close();
      notice('track-error', ['Exported ' + selection.map + ' to its global_waypoints.json.', note]
        .filter(Boolean).join(' '));
      await refresh();
    } catch (error) {
      notice('export-error', error.message);
      await refresh();
    } finally {
      $('export-run').disabled = false;
    }
  };
}
