// Active constraints: which limits a profile reaches, and how Inspect lists them.
export const constraintTypes = {
  road: {label: 'Road speed', unit: 'm/s', color: '#147566'},
  vehicle_speed: {label: 'Vehicle speed', unit: 'm/s', color: '#3030a0'},
  cornering: {label: 'Cornering grip', unit: 'm/s²', color: '#a57000'},
  drive: {label: 'Tyre drive', unit: 'm/s²', color: '#4d7200'},
  motor: {label: 'Motor drive', unit: 'm/s²', color: '#a74900'},
  braking: {label: 'Braking grip', unit: 'm/s²', color: '#a10027'},
  steering_cap: {label: 'Steering rate cap', unit: 'rad/s', color: '#8a268e'},
  multiple: {label: 'Multiple limits', color: '#151515'},
  slack: {label: 'No local limit reached', color: '#777777'},
};

export function activeConstraints(line, index) {
  return Object.keys(line.constraints).filter(key => line.constraints[key].active[index]);
}

export function constraintCategory(line, index) {
  const active = activeConstraints(line, index);
  if (active.length > 1) return 'multiple';
  return active[0] || 'slack';
}

function percent(value) {
  return (value * 100).toFixed(1) + '%';
}

function capacity(actual, limit, unit) {
  return limit.toFixed(2) + ' ' + unit + (limit > 0 ? ' (' + percent(actual / limit) + ')' : ' (—)');
}

// Whether the limits that are not reached at the inspected point are unfolded.
let showOthers = false;

// One limit as a bar: full width is what the car can do (base), the tick is what the profile
// allows, the fill is what the lap asks for there. The exact figures are in the tooltip.
function constraintRow(list, label, actual, profile, base, unit, color, active) {
  const row = document.createElement('div');
  row.className = active ? 'limit active' : 'limit';
  const full = base ?? profile;
  row.style.setProperty('--c', color);
  row.style.setProperty('--used', full > 0 ? Math.min(1, actual / full) : 0);
  row.style.setProperty('--cap', base ? Math.min(1, profile / base) : 1);
  row.title = label + ': ' + actual.toFixed(2) + ' ' + unit + ' · '
    + (base === null ? 'road cap ' + capacity(actual, profile, unit)
      : 'profile ' + capacity(actual, profile, unit) + ' · base ' + capacity(actual, base, unit));
  const name = document.createElement('span'), used = document.createElement('em');
  name.textContent = label;
  used.textContent = profile > 0 ? Math.round(actual / profile * 100) + '%' : '—';
  row.append(document.createElement('i'), name, document.createElement('b'), used);
  list.append(row);
}

// append(tag, text) adds an element to the Inspect panel and returns it.
export function showConstraints(line, index, append) {
  const active = activeConstraints(line, index);
  // Reached limits first; the others fold away, since at most points they are most of the list.
  const rows = append('div', '');
  append('strong', 'Overall use');
  const usage = append('div', ''), others = append('details', '');
  const inactive = Object.keys(line.constraints).filter(key => !active.includes(key));
  others.open = showOthers;
  others.ontoggle = () => { showOthers = others.open; };
  others.append(Object.assign(document.createElement('summary'),
                              {textContent: 'Other limits (' + (inactive.length + 2) + ')'}));
  for (const key of [...active, ...inactive]) {
    const data = line.constraints[key], {label, unit, color} = constraintTypes[key];
    const reached = data.active[index];
    const end = data.end[index] ? 'end' : 'start';
    const where = reached === 3 ? 'both ends of the interval' : end + ' of the interval';
    constraintRow(reached ? rows : others, label, data.actual[index], data.profile[index],
                  data.base?.[index] ?? null, unit, color, reached);
    (reached ? rows : others).lastChild.title += ' · at the ' + where;
  }
  if (!active.length) rows.append('None reached here.');

  // The car as a whole: how much of it the lap uses there.
  const used = line.values.vehicle_usage[index];
  constraintRow(usage, 'Vehicle use', used, 1, null, '', '#777777', false);
  usage.lastChild.title = 'Base vehicle utilisation ' + percent(used) + ': the highest use of '
    + 'top speed, tyre grip, motor, steering angle or steering rate';
  const grip = line.values.grip_usage[index], profileGrip = line.profile_grip[index];
  constraintRow(usage, 'Tyre grip', grip, profileGrip > 0 ? grip / profileGrip : 1, 1, '',
                '#777777', false);
  usage.lastChild.title = 'Combined tyre grip · profile ' + percent(profileGrip)
    + ' · base ' + percent(grip);

  const [angleProfile, angleBase, rateProfile, rateBase] = line.steering_limits;
  constraintRow(others, 'Steering angle', Math.abs(line.values.angle[index]),
                angleProfile, angleBase, 'rad', '#777777', false);
  constraintRow(others, 'Mean steering rate', Math.abs(line.values.steering_rate[index]),
                rateProfile, rateBase, 'rad/s', '#777777', false);
}
