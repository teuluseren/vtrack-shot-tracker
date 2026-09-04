const endpoint = process.env.VTRACK_CDP || "http://127.0.0.1:9223";
const uiPort = process.env.VTRACK_UI_PORT || "8765";
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

let targets = [];
for (let attempt = 0; attempt < 40; attempt += 1) {
  try {
    targets = await fetch(`${endpoint}/json/list`).then(response => response.json());
    if (targets.some(item => item.type === "page" && item.url.includes(`127.0.0.1:${uiPort}`))) break;
  } catch {}
  await delay(100);
}
const target = targets.find(item => item.type === "page" && item.url.includes(`127.0.0.1:${uiPort}`));
if (!target) throw new Error("VTrack browser target was not found");

const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, {once: true});
  socket.addEventListener("error", reject, {once: true});
});

let sequence = 0;
const pending = new Map();
const exceptions = [];
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.method === "Runtime.exceptionThrown") {
    exceptions.push(message.params?.exceptionDetails?.exception?.description || message.params?.exceptionDetails?.text || "unknown exception");
  }
  if (!message.id || !pending.has(message.id)) return;
  const {resolve, reject} = pending.get(message.id);
  pending.delete(message.id);
  message.error ? reject(new Error(message.error.message)) : resolve(message.result);
});

function command(method, params = {}) {
  const id = ++sequence;
  socket.send(JSON.stringify({id, method, params}));
  return new Promise((resolve, reject) => pending.set(id, {resolve, reject}));
}

async function evaluate(expression) {
  const result = await command("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  }
  return result.result.value;
}

await command("Runtime.enable");
await command("Emulation.setDeviceMetricsOverride", {
  width: 1600,
  height: 900,
  deviceScaleFactor: 1,
  mobile: false,
});
await evaluate("localStorage.clear(); location.reload(); true");

for (let attempt = 0; attempt < 60; attempt += 1) {
  if (await evaluate("document.querySelectorAll('#tree [data-shot]').length >= 9")) break;
  await delay(100);
}

// Put the synthetic session into a predictable, fully visible state.
await evaluate(`(() => {
  document.querySelectorAll('[data-toggle]').forEach(button => {
    if (button.getAttribute('aria-label')?.startsWith('Expand')) button.click();
  });
  document.querySelectorAll('[data-club-toggle]').forEach(button => {
    if (button.getAttribute('aria-label')?.startsWith('Expand')) button.click();
  });
  document.querySelectorAll('[data-eye-session],[data-eye-club]').forEach(button => {
    if (button.getAttribute('aria-label')?.startsWith('Show')) button.click();
  });
})()`);
await delay(250);

const checks = {};
checks.beginnerWorkspace = await evaluate(`(() => ({
  title: document.title,
  sessions: Boolean(document.querySelector('#treeCol')),
  range: Boolean(document.querySelector('#rangeCol')),
  replay: Boolean(document.querySelector('#camCol')),
  metrics: Boolean(document.querySelector('.rail')),
  shotRows: document.querySelectorAll('#tree [data-shot]').length,
  follow: document.querySelector('#follow')?.textContent || '',
  live: document.querySelector('#liveText')?.textContent || ''
}))()`);

checks.selectShot = await evaluate(`(async () => {
  const button = document.querySelector('#tree .clubNode[data-club$="|D"] [data-shot]');
  if (!button) return {ok:false};
  const id = button.dataset.shot;
  button.click();
  for (let i=0;i<30;i++) {
    if (document.querySelector('#shotLabel')?.textContent.includes('#'+id)) break;
    await new Promise(resolve=>setTimeout(resolve,50));
  }
  return {
    ok: document.querySelector('#shotLabel')?.textContent.includes('#'+id),
    id,
    tiles: document.querySelectorAll('#tiles .tile').length,
    replayCards: document.querySelectorAll('#cameraGrid > .card').length,
    gracefulNoMedia: Boolean(document.querySelector('#cameraGrid .mediaUnavailable')),
    followPaused: document.querySelector('#follow')?.textContent.includes('paused')
  };
})()`);

checks.range = await evaluate(`(() => {
  const dots = document.querySelectorAll('#rangeSvg [data-shot]').length;
  const envelopes = document.querySelectorAll('#rangeSvg [data-envelope]').length;
  document.querySelector('[data-distance-mode="total"]').click();
  const totalActive = document.querySelector('[data-distance-mode="total"]').classList.contains('active');
  document.querySelector('[data-distance-mode="carry"]').click();
  document.querySelector('[data-range-view="flight"]').click();
  const flightActive = document.querySelector('[data-range-view="flight"]').classList.contains('active');
  document.querySelector('[data-range-view="dispersion"]').click();
  return {dots,envelopes,totalActive,flightActive};
})()`);

const pointerTarget = await evaluate(`(() => {
  const svg=document.querySelector('#rangeSvg');
  const current=document.querySelector('#shotLabel').textContent.match(/#(\\d+)/)?.[1]||null;
  for (const point of svg.querySelectorAll('circle[data-shot]')) {
    if (point.dataset.shot===current) continue;
    const p=svg.createSVGPoint();p.x=Number(point.getAttribute('cx'));p.y=Number(point.getAttribute('cy'));
    const screen=p.matrixTransform(svg.getScreenCTM());
    const top=document.elementFromPoint(screen.x,screen.y)?.closest?.('[data-shot]');
    if (top) return {id:top.dataset.shot,x:screen.x,y:screen.y};
  }
  return null;
})()`);
if (pointerTarget) {
  await command("Input.dispatchMouseEvent", {type:"mousePressed",x:pointerTarget.x,y:pointerTarget.y,button:"left",clickCount:1});
  await command("Input.dispatchMouseEvent", {type:"mouseReleased",x:pointerTarget.x,y:pointerTarget.y,button:"left",clickCount:1});
  await delay(150);
}
checks.rangePointerSelection = await evaluate(`({
  target:${JSON.stringify(pointerTarget?.id || null)},
  selected:document.querySelector('#shotLabel').textContent
})`);

checks.putting = await evaluate(`(async () => {
  const button=document.querySelector('#tree .clubNode[data-club$="|PT"] [data-shot]');
  if(!button)return {ok:false};
  const id=button.dataset.shot;button.click();
  for(let i=0;i<30;i++){
    if(document.querySelector('#shotLabel')?.textContent.includes('#'+id))break;
    await new Promise(resolve=>setTimeout(resolve,50));
  }
  await new Promise(resolve=>setTimeout(resolve,80));
  return {
    ok:document.querySelector('[data-range-view="putting"]').classList.contains('active'),
    rollPaths:document.querySelectorAll('#rangeSvg [data-shot]').length,
    feet:/ft/i.test(document.querySelector('#rangeMeta')?.textContent||'') || /ft/i.test(document.querySelector('#rangeSvg')?.textContent||'')
  };
})()`);

checks.bag = await evaluate(`(async () => {
  document.querySelector('#bagSettings').click();
  for(let i=0;i<30&&!document.querySelector('#bagModal.open');i++)await new Promise(resolve=>setTimeout(resolve,30));
  const options=[...document.querySelectorAll('#bagMapList option')].map(option=>option.textContent);
  const mapping=document.querySelector('[data-bag-source="SW"]');
  if(mapping)mapping.value='54DEG';
  document.querySelector('#bagCancel').click();
  return {opened:options.length>0,loft54:options.some(text=>text.includes('54°')),cancelled:!document.querySelector('#bagModal').classList.contains('open')};
})()`);

checks.reclassify = await evaluate(`(() => {
  const action=document.querySelector('#tree .clubNode[data-club$="|54DEG"] [data-edit-shot]');
  if(!action)return {opened:false};
  action.click();
  const labels=[...document.querySelectorAll('#shotClub option')].map(option=>option.textContent);
  const result={opened:document.querySelector('#shotModal').classList.contains('open'),loft54:labels.some(text=>text.includes('54°')),putter:labels.some(text=>/Putter/i.test(text))};
  document.querySelector('#shotEditCancel').click();
  return result;
})()`);

checks.report = await evaluate(`(async () => {
  const id=Number(document.querySelector('[data-session]')?.dataset.session||0);
  const response=await fetch('/report/session/'+id,{cache:'no-store'});
  const text=await response.text();
  return {status:response.status,name:text.includes('Share readiness smoke session'),print:text.includes('Print / Save PDF')};
})()`);

checks.clearIsNonDestructive = await evaluate(`(async () => {
  const before=(await fetch('/api/shots',{cache:'no-store'}).then(r=>r.json())).length;
  document.querySelector('#clearRange').click();
  await new Promise(resolve=>setTimeout(resolve,80));
  const after=(await fetch('/api/shots',{cache:'no-store'}).then(r=>r.json())).length;
  return {before,after,empty:Boolean(document.querySelector('#rangeSvg .emptyRangeMessage'))};
})()`);

checks.theme = await evaluate(`(() => {
  const before=document.documentElement.dataset.theme||'dark';
  document.querySelector('#themeToggle').click();
  const after=document.documentElement.dataset.theme;
  return {before,after,changed:before!==after};
})()`);

checks.layout = await evaluate(`(() => ({
  resizers:document.querySelectorAll('.workspaceResizer').length,
  sessionCollapse:Boolean(document.querySelector('.collapse[data-col="treeCol"]')),
  rangeCollapse:Boolean(document.querySelector('.collapse[data-col="rangeCol"]')),
  replayCollapse:Boolean(document.querySelector('.collapse[data-col="camCol"]')),
  windows:Boolean(document.querySelector('#cameraWindows')),
  snap:Boolean(document.querySelector('#snapCameras'))
}))()`);

checks.shotHeaderAlignment = await evaluate(`(() => {
  const header = document.querySelector('.shotHeaderSelect');
  const row = document.querySelector('.shot .shotSelect');
  if (!header || !row) return {ok:false,reason:'missing header or shot row'};
  const h = [...header.children].map(el => el.getBoundingClientRect());
  const r = [...row.children].map(el => el.getBoundingClientRect());
  if (h.length !== 4 || r.length !== 4) return {ok:false,reason:'unexpected column count',header:h.length,row:r.length};
  const deltas = h.flatMap((box,index) => [Math.abs(box.left-r[index].left),Math.abs(box.right-r[index].right)]);
  const maxDelta = Math.max(...deltas);
  return {ok:maxDelta <= 0.75,maxDelta,header:h.map(x=>[x.left,x.right]),row:r.map(x=>[x.left,x.right])};
})()`);

const passed = checks.beginnerWorkspace.title === 'vTrack Shot Tracker'
  && checks.beginnerWorkspace.sessions && checks.beginnerWorkspace.range
  && checks.beginnerWorkspace.replay && checks.beginnerWorkspace.metrics
  && checks.beginnerWorkspace.shotRows >= 9
  && /Follow/i.test(checks.beginnerWorkspace.follow)
  && /Collector live/i.test(checks.beginnerWorkspace.live)
  && checks.selectShot.ok && checks.selectShot.tiles > 0 && checks.selectShot.replayCards > 0
  && checks.selectShot.gracefulNoMedia && checks.selectShot.followPaused
  && checks.range.dots >= 6 && checks.range.envelopes >= 3
  && checks.range.totalActive && checks.range.flightActive
  && (!checks.rangePointerSelection.target || checks.rangePointerSelection.selected.includes('#'+checks.rangePointerSelection.target))
  && checks.putting.ok && checks.putting.rollPaths >= 3 && checks.putting.feet
  && checks.bag.opened && checks.bag.loft54 && checks.bag.cancelled
  && checks.reclassify.opened && checks.reclassify.loft54 && checks.reclassify.putter
  && checks.report.status === 200 && checks.report.name && checks.report.print
  && checks.clearIsNonDestructive.before === checks.clearIsNonDestructive.after
  && checks.clearIsNonDestructive.empty
  && checks.theme.changed
  && checks.layout.resizers === 2 && checks.layout.sessionCollapse && checks.layout.rangeCollapse
  && checks.layout.replayCollapse && checks.layout.windows && checks.layout.snap
  && checks.shotHeaderAlignment.ok
  && exceptions.length === 0;

console.log(JSON.stringify({passed,exceptions,checks}, null, 2));
socket.close();
if (!passed) process.exitCode = 1;
