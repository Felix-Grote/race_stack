// The Logs tab: everything the planner wrote during the last run of one profile on the map
// selected in Tracks, down to each pass, and the stack trace if the run failed.
import {$, api, status} from './common.js';

let shown;

export async function showLog(map) {
  if ($('logs').hidden || !map) return;
  try {
    const {text} = await api('log?' + new URLSearchParams({map, kind: $('log-profile').value}));
    const box = $('log-text');
    // Follow a run as it writes, unless the operator has scrolled back to read.
    const following = box.scrollTop + box.clientHeight >= box.scrollHeight - 4;
    if (text !== shown) {
      shown = text;
      box.textContent = text || 'No run of this profile on this map yet.';
      if (following) box.scrollTop = box.scrollHeight;
    }
    const failed = /Traceback \(most recent call last\)/.test(text);
    status('log-status', map + ' · ' + (text ? text.trimEnd().split('\n').length + ' lines' : 'no log')
      + (failed ? ' · ended in an error, see the stack trace at the end' : ''));
  } catch (error) {
    status('log-status', error.message);
  }
}
