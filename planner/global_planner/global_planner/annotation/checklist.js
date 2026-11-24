// The annotation page's checklist (ui.js): how the route stands and what is wrong.
// A classic script like ui.js, loaded before it: it reads ui.js's V, sourceChanged and
// carUnavailable when it is called, never before.
// The first box under the map: what the tool in hand does.
const HINTS = {
  null: 'Pick a tool. Wheel zooms; drag pans (with a tool picked, the right or middle button).',
  stroke: 'Draw wall: click points, double-click to finish. Backspace drops the last point, ' +
          'Escape the whole line.',
  region: 'Pick region: the track is picked for you; click inside another piece of free ' +
          'space to keep that one instead.',
  guide: 'Draw guide: click points round the track in the direction of travel; click the first ' +
         'point (or double-click) to close it. Backspace drops the last point, Escape all. ' +
         'A drawn guide stays as drawn; Suggest makes it follow the road again.',
  start: 'Set start: draw the start line with two clicks, one on each side of the road. ' +
         'It is run on to the walls and is the first gate; the lap starts where a line crosses it.'};
// Two of the three boxes under the map: how the route stands, step by step, and what is
// wrong. (The first, the tool in hand, is set where a tool is picked.)
function showStatus(message) {
  const box = $('status'), errors = $('errors');
  box.replaceChildren();
  errors.replaceChildren();
  const add = (parent, text, className) => {
    const item = document.createElement('p');
    item.textContent = text;
    if (className) item.className = className;
    parent.append(item);
  };
  // The Errors box is headed by what is wrong, and holds why.
  const wrong = [];
  const error = (name, text) => { wrong.push(name); add(errors, text); };
  const failed = /^(REFUSED|FAILED): /.test(message || '');
  if (failed) error(message.startsWith('REFUSED') ? 'Refused' : 'Editor',
                    message.replace(/^(REFUSED|FAILED): /, ''));
  if (V.map) {
    const hasGuide = (V.guide_px || []).length >= 3, drawn = Array.isArray(V.start_px?.[0]);
    const invalid = !V.result && hasGuide && V.start_px && !V.walls_error;
    const file = V.exported_path.split('/').pop();
    const steps = [
      ['Road', V.walls_error ? 'bad' : 'ok', V.walls_error ? 'not a closed ring' : 'closed ring'],
      ['Guide', hasGuide ? 'ok' : 'wait',
       hasGuide ? (V.guide_auto ? 'suggested, follows the road' : 'drawn by hand') : 'none yet'],
      ['Start', V.start_px ? 'ok' : 'wait',
       V.start_px ? (drawn ? 'line drawn across the road' : 'one click, from an older draft')
         : 'not set'],
      ['Route', V.result ? 'ok' : invalid ? 'bad' : 'wait',
       V.result ? V.route_summary : invalid ? 'not valid' : 'needs a road, a guide and a start'],
      ['Exported', V.exported === 'current' ? 'ok' : V.exported === 'changed' ? 'warn' : 'wait',
       V.exported === 'current' ? file + ', matches this draft'
         : V.exported === 'changed' ? file + ' is older than this draft' : 'not yet'],
    ];
    const list = document.createElement('div');
    list.className = 'steps';
    for (const [label, state, text] of steps) {
      const row = document.createElement('div'), mark = document.createElement('i');
      row.className = 'step';
      row.dataset.state = state;
      mark.textContent = {ok: '✓', bad: '✗', warn: '!', wait: '·'}[state];
      row.append(mark, Object.assign(document.createElement('b'), {textContent: label}),
                 Object.assign(document.createElement('span'), {textContent: text}));
      if (label === 'Exported') row.title = V.exported_path;
      list.append(row);
    }
    box.append(list);
    // What stands in the way, in full; the steps only say that something does.
    if (V.walls_error) error('Road', V.walls_error);
    if (invalid) error('Route', V.route.replace(/^not valid: /, ''));
    if (sourceChanged) error('Map', 'The map changed on disk: press Open again before saving or exporting.');
    if (carUnavailable) error('Car', 'The configured car cannot be checked, so the route cannot be exported.');
  } else if (!message) {
    add(box, 'Pick a map and press Open.');
  }
  // What the last action did, when it did it.
  if (message && !failed) add(box, message, 'said');
  $('errors-title').textContent = 'Errors: ' + (wrong.join(', ') || 'None');
}
