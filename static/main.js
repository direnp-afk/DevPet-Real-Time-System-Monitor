const $ = (id) => document.getElementById(id);
let lastEventKey = '';
let lastAlertKey = '';

const descriptions = {
  happy: 'Everything looks good. Keep it up.',
  stressed: 'Something is putting pressure on your system.',
  worried: 'A watched process stopped or a file was removed.',
  sad: 'That did not go as planned. Try again.',
  excited: 'Nice work. Byte earned some progress.'
};

function percentage(value) {
  return value === null || value === undefined ? '--%' : `${Math.round(value)}%`;
}

function updateBar(name, value) {
  $(name + '-bar').style.width = `${Math.max(0, Math.min(100, value || 0))}%`;
}

function renderPet(pet) {
  $('pet-scene').dataset.mood = pet.mood;
  $('pet-mood').textContent = pet.mood[0].toUpperCase() + pet.mood.slice(1);
  $('pet-description').textContent = descriptions[pet.mood] || descriptions.happy;
  $('pet-reason').textContent = pet.reason ? `Last reaction: ${pet.reason}` : 'Waiting for the first system event.';
  $('health-number').textContent = percentage(pet.health);
  $('stress-number').textContent = percentage(pet.stress);
  updateBar('health', pet.health);
  updateBar('stress', pet.stress);
  $('pet-level').textContent = `Level ${Math.floor(pet.xp / 100) + 1}`;
  $('xp-number').textContent = `${pet.xp % 100} / 100`;
  updateBar('xp', pet.xp % 100);
}

function renderSystem(system, history) {
  for (const name of ['cpu', 'memory', 'disk']) {
    $(name).textContent = percentage(system[name]);
    updateBar(name, system[name]);
  }
  const formatRate = value => value === null || value === undefined ? '--' : `${Number(value).toFixed(1)} KB/s`;
  $('download').textContent = formatRate(system.download);
  $('upload').textContent = formatRate(system.upload);
  for (const name of ['cpu', 'memory']) {
    const svg = $(name + '-trend');
    svg.replaceChildren();
    const values = (history || []).map(x => Number(x[name])).filter(Number.isFinite);
    if (values.length < 2) continue;
    const points = values.map((v, i) => `${i * 260 / (values.length - 1)},${52 - Math.min(100, Math.max(0, v)) * .48}`).join(' ');
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    line.setAttribute('points', points);
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', name === 'cpu' ? '#5f9680' : '#7795b6');
    line.setAttribute('stroke-width', '2');
    line.setAttribute('vector-effect', 'non-scaling-stroke');
    svg.append(line);
  }
}

function renderAlerts(alerts) {
  const count = alerts.filter(a => a.status === 'new').length;
  $('alert-count').textContent = `${count} need attention`;
  const key = alerts.map(a => `${a.id}:${a.status}`).join('|');
  if (key === lastAlertKey) return;
  lastAlertKey = key;
  const list = $('alerts');
  list.replaceChildren();
  if (!alerts.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'No alerts. Byte is keeping an eye on things.';
    list.append(empty);
    return;
  }
  for (const alert of alerts.slice(0, 5)) {
    const row = document.createElement('div');
    row.className = 'alert-item' + (alert.status !== 'new' ? ' closed' : '');
    const body = document.createElement('div');
    body.className = 'alert-body';
    const heading = document.createElement('strong');
    heading.textContent = `${alert.type.replaceAll('_', ' ')} · ${alert.status}`;
    const message = document.createElement('p');
    message.textContent = alert.message;
    body.append(heading, message);
    row.append(body);
    if (alert.status === 'new') {
      const button = document.createElement('button');
      button.textContent = 'Acknowledge';
      button.addEventListener('click', async () => {
        await send('/api/ack', { id: alert.id });
        refresh();
      });
      row.append(button);
    }
    list.append(row);
  }
}

function renderWatches(items) {
  $('watch-count').textContent = `${items.length} added`;
  const list = $('watch-list');
  list.replaceChildren();
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'No watches yet. Add a process or folder above.';
    list.append(empty);
    return;
  }
  for (const item of items) {
    const row = document.createElement('div');
    row.className = 'watch-item';
    const kind = document.createElement('span');
    kind.className = 'watch-kind';
    kind.textContent = item.kind;
    const name = document.createElement('span');
    name.className = 'watch-name';
    name.textContent = item.target;
    name.title = item.target;
    const status = document.createElement('span');
    status.className = 'watch-status';
    status.textContent = item.status;
    const remove = document.createElement('button');
    remove.className = 'watch-remove';
    remove.textContent = 'Remove';
    remove.addEventListener('click', async () => {
      await send('/api/watch', { action: 'remove', kind: item.kind, target: item.target });
      refresh();
    });
    row.append(kind, name, status, remove);
    list.append(row);
  }
}

function renderEvents(items) {
  const filter = $('event-filter').value;
  if (filter === 'logs') items = items.filter(x => x.type.startsWith('LOG_'));
  if (filter === 'alerts') items = items.filter(x => /HIGH|FAILED|STOPPED|DELETED|LOG_ERROR|LOG_WARNING|MONITOR_ERROR/.test(x.type));
  $('event-count').textContent = `${items.length} recent events`;
  const key = filter + ':' + items.map(x => x.id).join('|');
  if (key === lastEventKey) return;
  lastEventKey = key;
  const list = $('events');
  list.replaceChildren();
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'Waiting for activity...';
    list.append(empty);
    return;
  }
  for (const item of items.slice(0, 12)) {
    const row = document.createElement('div');
    row.className = 'event';
    const time = document.createElement('span');
    time.className = 'event-time';
    const date = new Date(item.time);
    time.textContent = Number.isNaN(date.getTime()) ? '--:--' : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const type = document.createElement('span');
    type.className = 'event-kind' + (/HIGH|FAILED|STOPPED|DELETED/.test(item.type) ? ' bad' : '');
    type.textContent = item.type.replaceAll('_', ' ');
    const info = document.createElement('span');
    info.className = 'event-info';
    info.textContent = item.message;
    if (item.demo) {
      const demo = document.createElement('em');
      demo.textContent = 'demo';
      info.append(demo);
    }
    row.append(time, type, info);
    list.append(row);
  }
}

async function send(path, data) {
  try {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'Request failed');
    $('watch-message').textContent = '';
    return true;
  } catch (error) {
    $('watch-message').textContent = error.message;
    return false;
  }
}

async function refresh() {
  try {
    const response = await fetch('/api/state', { cache: 'no-store' });
    if (!response.ok) throw new Error('Server unavailable');
    const state = await response.json();
    renderPet(state.pet);
    renderSystem(state.system, state.history);
    renderAlerts(state.alerts || []);
    renderWatches(state.watches);
    renderEvents(state.events);
    $('tail-method').textContent = `Logs: ${state.tail.method}`;
    $('tail-status').textContent = state.tail.running ? 'Following' : (state.tail.error || 'Not running');
    $('last-updated').textContent = `Last checked: ${new Date().toLocaleTimeString()}`;
    $('connection-dot').classList.add('good');
    $('connection-text').textContent = state.tail.running ? 'Monitoring' : 'Log follower offline';
  } catch (error) {
    $('connection-dot').classList.remove('good');
    $('connection-text').textContent = 'Disconnected';
    $('last-updated').textContent = 'Unable to reach local server';
  }
}

$('watch-kind').addEventListener('change', () => {
  const placeholders = { process: 'notepad.exe or process ID', folder: 'C:\\Users\\You\\Documents', log: 'C:\\logs\\app.log' };
  $('watch-target').placeholder = placeholders[$('watch-kind').value];
});

$('watch-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const ok = await send('/api/watch', {
    action: 'add', kind: $('watch-kind').value, target: $('watch-target').value
  });
  if (ok) {
    $('watch-target').value = '';
    refresh();
  }
});

for (const button of document.querySelectorAll('[data-demo]')) {
  button.addEventListener('click', () => send('/api/demo', { type: button.dataset.demo }));
}

$('event-filter').addEventListener('change', () => { lastEventKey = ''; refresh(); });
refresh();
setInterval(refresh, 1000);
