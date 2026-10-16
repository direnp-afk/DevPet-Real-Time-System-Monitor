'use strict';
const $ = (id) => document.getElementById(id);
const moodText = {
  happy: ['😊 HAPPY & HEALTHY', 'All systems looking good! Keep it up, human.'],
  excited: ['✨ SUPER EXCITED!', 'A win for the team! You earned XP.'],
  stressed: ['😰 FEELING STRESSED', 'Yikes! Your CPU is working overtime.'],
  tired: ['😴 A LITTLE TIRED', 'Too much memory pressure. Can I nap?'],
  sick: ['🤒 NOT FEELING GREAT', 'Something crashed. Let’s get things running again!'],
  sad: ['🥺 A BIT SAD', 'Tests failed, but every bug is a lesson.'],
  worried: ['😟 A LITTLE WORRIED', 'One of your monitored processes has stopped.'],
};
const icons = {
  CPU_HIGH: ['♨','warning','CPU spike detected'], RAM_HIGH:['▦','warning','Memory pressure'],
  APP_CRASH:['✕','danger','Application crashed'], APP_STOPPED:['■','warning','Application stopped'],
  TEST_FAILED:['!','danger','Tests failed'], TEST_PASSED:['✓','success','Tests passed'],
  BUILD_SUCCESS:['⚡','success','Build successful'], GIT_COMMIT:['⑂','success','New Git commit'],
  SYSTEM_RECOVERED:['♥','success','System recovered'], MONITOR_ERROR:['!','warning','Monitor warning']
};
let fetching = false;
let lastSeen = '';
function text(id, value) { $(id).textContent = value; }
function percent(id, value) { $(id).style.width = Math.min(100,Math.max(0,value)) + '%'; }
function niceTime(raw) {
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? '--:--' : date.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
function setSparkline(id, values) {
  const displayed = values.slice(-35);
  const points = displayed.map((y,i) => `${displayed.length < 2 ? 0 : (i/(displayed.length-1))*145},${42-(Math.max(0,Math.min(100,y))/100)*38}`);
  $(id).setAttribute('points', points.length ? points.join(' ') : '0,40 145,40');
}
function renderFeed(events) {
  const root = $('feed-items');
  const key = events.map(x => x.id).join(',');
  if (key === lastSeen) return;
  lastSeen = key;
  root.replaceChildren();
  if (!events.length) {
    const empty=document.createElement('div'); empty.className='empty-feed';
    empty.textContent='Waiting for your first event... Try a demo action below.';
    root.append(empty); return;
  }
  for (const ev of events.slice(0,5)) {
    const data = icons[ev.type] || ['•','neutral',ev.type.replaceAll('_',' ')];
    const item = document.createElement('div'); item.className='feed-item';
    const icon = document.createElement('span'); icon.className=`feed-icon ${data[1]}`; icon.textContent=data[0];
    const desc = document.createElement('div'); desc.className='feed-desc';
    const head = document.createElement('strong'); head.textContent=data[2];
    const msg = document.createElement('small'); msg.textContent=ev.message;
    desc.append(head,msg);
    const time = document.createElement('span'); time.className='feed-time'; time.textContent=niceTime(ev.ts);
    item.append(icon,desc,time); root.append(item);
  }
}
function update(data) {
  const pet=data.pet;
  const mood=moodText[pet.mood] || moodText.happy;
  $('pet-stage').className=`pet-stage mood-${pet.mood}`;
  text('pet-level',`LVL ${pet.level}`);
  text('pet-mood',mood[0]); text('pet-message',mood[1]);
  ['health','energy','stress'].forEach(k => {text(`${k}-value`,pet[k]+'%');percent(`${k}-bar`,pet[k]);});
  text('xp-label',pet.xp+' / 100 XP'); percent('xp-bar',pet.xp);
  const cpu=data.system.cpu,ram=data.system.ram;
  text('cpu-value',cpu===null?'--':cpu.toFixed(0));
  text('ram-value',ram===null?'--':ram.toFixed(0));
  text('cpu-status',cpu===null?'Sampling...':cpu>=90?'High load':cpu>=60?'Moderate load':'Looking good');
  text('ram-status',ram===null?'Sampling...':ram>=90?'High memory':ram>=70?'Moderate usage':'All clear');
  setSparkline('cpu-line',data.history.map(x=>x.cpu));setSparkline('ram-line',data.history.map(x=>x.ram));
  text('event-count',data.events_seen); text('alerts-count',`${data.alerts_seen} alerts`);
  renderFeed(data.events);
  const recent=data.events[0];
  if (recent) text('terminal-output',`[${niceTime(recent.ts)}] ${recent.type} ${recent.message}`);
  text('connection-status',data.tail.running?`Connected: ${data.tail.command}`:(data.tail.error || 'Log follower unavailable'));
  text('tail-command', data.tail.command || 'Starting log follower...');
  $('tail-indicator').style.color=data.tail.running?'#69e3a9':'#ff7d87';
}
async function refresh() {
  if (fetching) return;
  fetching=true;
  try {
    const response=await fetch('/api/state',{cache:'no-store'});
    if(!response.ok) throw new Error(`HTTP ${response.status}`);
    const data=await response.json(); update(data);
  } catch(e) {text('connection-status',`Connection lost: ${e.message}`);$('tail-indicator').style.color='#ff7d87';}
  finally{fetching=false;}
}
async function demo(event,button) {
  button.disabled=true;
  try {
    const res=await fetch('/api/demo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:event})});
    const data=await res.json();if(!res.ok) throw new Error(data.error || 'Request failed');
    text('toast',`✓ ${event.replaceAll('_',' ')} event sent to events.log. tail will pick it up!`);
    setTimeout(refresh,250);
  } catch(e) {text('toast',`Error: ${e.message}`);}
  finally {button.disabled=false;}
}
for(const button of document.querySelectorAll('[data-demo]')){
  button.addEventListener('click',()=>demo(button.dataset.demo,button));
}
text('local-date',new Date().toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric',year:'numeric'}).toUpperCase());
refresh();setInterval(refresh,1000);
