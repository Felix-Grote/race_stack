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

function constraintRow(list, label, actual, profile, base, unit) {
  const row = document.createElement('li');
  row.textContent = label + ' · ' + actual.toFixed(2) + ' ' + unit;
  const bounds = document.createElement('div');
  bounds.textContent = base === null ? 'Road cap ' + capacity(actual, profile, unit)
    : 'Profile ' + capacity(actual, profile, unit) + ' · Base ' + capacity(actual, base, unit);
  row.append(bounds);
  list.append(row);
}

// append(tag, text) adds an element to the Inspect panel and returns it.
export function showConstraints(line, index, append) {
  const active = activeConstraints(line, index);
  append('strong', active.length
    ? 'Active · ' + active.map(key => constraintTypes[key].label).join(' + ')
    : 'No local limit reached');
  append('p', 'Base vehicle utilisation ' + percent(line.values.vehicle_usage[index])
    + ' · Road limit use ' + percent(line.values.road_usage[index]));
  append('p', 'Combined tyre grip · Profile ' + percent(line.profile_grip[index])
    + ' · Base ' + percent(line.values.grip_usage[index]));
  const rows = append('ul', '');
  const inactive = Object.keys(line.constraints).filter(key => !active.includes(key));
  for (const key of [...active, ...inactive]) {
    const data = line.constraints[key], {label, unit} = constraintTypes[key];
    const end = data.end[index] ? 'end' : 'start';
    const where = data.active[index] === 3 ? 'both active, showing ' + end
      : data.active[index] ? end + ' active' : end;
    constraintRow(rows, label + ' (' + where + ')', data.actual[index], data.profile[index],
                  data.base?.[index] ?? null, unit);
  }
  const [angleProfile, angleBase, rateProfile, rateBase] = line.steering_limits;
  constraintRow(rows, 'Steering angle at start', Math.abs(line.values.angle[index]),
                angleProfile, angleBase, 'rad');
  constraintRow(rows, 'Mean steering rate', Math.abs(line.values.steering_rate[index]),
                rateProfile, rateBase, 'rad/s');
}
