import {writeFileSync} from "node:fs";

const endpoint = process.env.VTRACK_CDP || "http://127.0.0.1:9224";
const uiPort = process.env.VTRACK_UI_PORT || "8766";
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const targets = await fetch(`${endpoint}/json/list`).then(response => response.json());
const target = targets.find(item => item.type === "page" && item.url.includes(`127.0.0.1:${uiPort}`));
if (!target) throw new Error("Putter verification browser target was not found");

const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, {once: true});
  socket.addEventListener("error", reject, {once: true});
});

let sequence = 0;
const pending = new Map();
const runtimeErrors = [];
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.method === "Runtime.exceptionThrown") runtimeErrors.push(message.params.exceptionDetails);
  if (!message.id || !pending.has(message.id)) return;
  const handlers = pending.get(message.id);
  pending.delete(message.id);
  message.error ? handlers.reject(new Error(message.error.message)) : handlers.resolve(message.result);
});
await command("Runtime.enable");
await command("Page.reload", {ignoreCache: true});

function command(method, params = {}) {
  const id = ++sequence;
  socket.send(JSON.stringify({id, method, params}));
  return new Promise((resolve, reject) => pending.set(id, {resolve, reject}));
}

async function evaluate(expression) {
  const result = await command("Runtime.evaluate", {expression, awaitPromise: true, returnByValue: true});
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}

for (let attempt = 0; attempt < 50; attempt += 1) {
  if (await evaluate("Boolean(document.querySelector('[data-putt-path]') && document.querySelector('#faceImg')?.complete)")) break;
  await delay(100);
}
if (!await evaluate("Boolean(document.querySelector('.sessionHead'))")) {
  console.error(JSON.stringify({runtimeErrors, body: await evaluate("document.body.innerText.slice(0,1000)")}, null, 2));
  await command("Browser.close");
  process.exit(1);
}

const checks = await evaluate(`(() => {
  const active = document.querySelector('[data-range-view].active');
  const distanceButtons = [...document.querySelectorAll('[data-distance-mode]')];
  const image = document.querySelector('#faceImg');
  const labels = [...document.querySelectorAll('.tile label')].map(node => node.textContent);
  const session = document.querySelector('.sessionHead');
  const firstRow = ['.sessionBubble', 'strong', '.visibility', '.sessionClubs', '.treeToggle'].map(selector => session.querySelector(selector).getBoundingClientRect());
  const secondRow = ['.sessionDate', '.countPill', '.sessionExport', '.sessionRename'].map(selector => session.querySelector(selector).getBoundingClientRect());
  const rowAligned = boxes => Math.max(...boxes.map(box => box.top + box.height / 2)) - Math.min(...boxes.map(box => box.top + box.height / 2)) <= 1;
  const noOverlap = boxes => [...boxes].sort((a, b) => a.left - b.left).every((box, index, ordered) => index === ordered.length - 1 || box.right <= ordered[index + 1].left + .1);
  const sessionControlDetails = [...session.querySelectorAll('button')].map(button => { const box=button.getBoundingClientRect(), style=getComputedStyle(button); return {className:button.className,size:[box.width,box.height],border:[style.borderTopWidth,style.borderRightWidth,style.borderBottomWidth,style.borderLeftWidth]}; });
  const bulk = session.querySelector('.sessionClubs');
  const beforeBox = bulk.getBoundingClientRect(), beforeIcon = bulk.querySelector('svg').getBoundingClientRect();
  const beforeName = bulk.querySelector('svg').dataset.bulkIcon;
  bulk.click();
  const changed = document.querySelector('.sessionClubs'), afterBox = changed.getBoundingClientRect(), afterIcon = changed.querySelector('svg').getBoundingClientRect();
  const afterName = changed.querySelector('svg').dataset.bulkIcon;
  changed.click();
  return {
    puttingActive: active?.dataset.rangeView === 'putting',
    paths: document.querySelectorAll('[data-putt-path]').length,
    envelopes: document.querySelectorAll('[data-putt-envelope]').length,
    hole: Boolean(document.querySelector('.puttingHole')),
    aria: document.querySelector('#rangeSvg')?.getAttribute('aria-label'),
    meta: document.querySelector('#rangeMeta')?.textContent,
    legend: document.querySelector('#legend')?.textContent,
    distanceDisabled: distanceButtons.every(button => button.disabled),
    face: {src: image?.getAttribute('src'), loaded: Boolean(image?.complete && image.naturalWidth > 0), putterClass: image?.closest('.faceStage')?.classList.contains('putter')},
    putterTiles: ['Roll', 'Target', 'Offline'].every(label => labels.includes(label)),
    treeUsesFeet: [...document.querySelectorAll('.clubNode')].filter(node => /PT|PUTTER/.test(node.textContent)).every(node => node.textContent.includes('ft')),
    headerAligned: rowAligned(firstRow) && rowAligned(secondRow),
    headerNoOverlap: noOverlap(firstRow) && noOverlap(secondRow),
    newSessionAnchored: (() => { const button = document.querySelector('#newSession').getBoundingClientRect(), body = document.querySelector('.sessionListBody').getBoundingClientRect(); return Math.abs(button.bottom - body.bottom + 9) < 1 && getComputedStyle(document.querySelector('#newSession')).position === 'absolute'; })(),
    summaryPills: Boolean(document.querySelector('[data-summary-session]') && document.querySelector('[data-summary-club]')),
    tileVertical: (() => { const tile = document.querySelector('.tile'), label = tile.querySelector('label').getBoundingClientRect(), value = tile.querySelector('strong').getBoundingClientRect(); return label.bottom <= value.top; })(),
    pageFits: document.documentElement.scrollHeight <= innerHeight && [...document.querySelectorAll('.tile')].every(tile => tile.getBoundingClientRect().bottom <= innerHeight),
    tilesCentered: [...document.querySelectorAll('.tile')].every(tile => getComputedStyle(tile).textAlign === 'center'),
    sessionButtonsBorderless: sessionControlDetails.every(control => control.border.every(width => parseFloat(width) === 0)),
    sessionControlsSameSize: sessionControlDetails.every(control => control.size.every(value => value === 28)),
    sessionControlDetails,
    clubToggleFarRight: (() => { const head=document.querySelector('.clubHead'), toggle=head.querySelector('.clubToggle').getBoundingClientRect(), swatch=head.querySelector('.clubSwatch').getBoundingClientRect(); return toggle.left >= swatch.right; })(),
    snapPreservesSize: (() => { const card=document.querySelector('#cameraGrid>.card'); card.style.width='333px'; card.style.height='222px'; const before=[card.offsetWidth,card.offsetHeight]; document.querySelector('#snapCameras').click(); return before[0]===card.offsetWidth && before[1]===card.offsetHeight; })(),
    panelExportModal: (() => { document.querySelector('#exportReplay').click(); const modal=document.querySelector('#panelExportModal'), result=modal.classList.contains('open') && modal.querySelectorAll('input[name="panel"]').length>=1 && document.querySelector('#exportReplay').textContent.trim()==='Export'; document.querySelector('#panelExportCancel').click(); return result; })(),
    summaryGraphic: (() => { document.querySelector('[data-summary-club]').click(); const modal=document.querySelector('#summaryModal'), result=modal.classList.contains('open') && Boolean(modal.querySelector('.golferGauge svg')) && modal.querySelector('[data-profile="woman"]')?.classList.contains('active') && Boolean(document.querySelector('#exportSummary')); document.querySelector('#summaryClose').click(); return result; })(),
    preferenceStore: (() => { const raw=localStorage.getItem('vtrackWorkspacePreferencesV1'); if(!raw)return false; const saved=JSON.parse(raw); return Boolean(saved.version===1 && Array.isArray(saved.collapsedColumns) && Array.isArray(saved.openClubs) && saved.cameraLayout); })(),
    bulkSize: [beforeBox.width, beforeBox.height],
    bulkIconSize: [beforeIcon.width, beforeIcon.height],
    bulkNames: [beforeName, afterName],
    bulkStable: Math.abs(beforeBox.left - afterBox.left) < .1 && Math.abs(beforeBox.top - afterBox.top) < .1 && Math.abs(beforeIcon.left - afterIcon.left) < .1 && Math.abs(beforeIcon.top - afterIcon.top) < .1
  };
})()`);

const screenshot = await command("Page.captureScreenshot", {format: "png", fromSurface: true});
writeFileSync("build/putter-ui-verification.png", Buffer.from(screenshot.data, "base64"));

const passed = checks.puttingActive
  && checks.paths === 3
  && checks.envelopes >= 1
  && checks.hole
  && checks.aria?.includes("Putting green")
  && checks.meta?.includes("3 visible putts")
  && checks.legend?.includes("ft")
  && checks.distanceDisabled
  && checks.face.src === "/assets/club-face-putter.png"
  && checks.face.loaded
  && checks.face.putterClass
  && checks.putterTiles
  && checks.treeUsesFeet
  && checks.headerAligned
  && checks.headerNoOverlap
  && checks.newSessionAnchored
  && checks.summaryPills
  && checks.tileVertical
  && checks.pageFits
  && checks.tilesCentered
  && checks.sessionButtonsBorderless
  && checks.sessionControlsSameSize
  && checks.clubToggleFarRight
  && checks.snapPreservesSize
  && checks.panelExportModal
  && checks.summaryGraphic
  && checks.preferenceStore
  && checks.bulkSize.every(value => value === 28)
  && checks.bulkIconSize.every(value => value === 16)
  && checks.bulkNames[0] === "expand-all"
  && checks.bulkNames[1] === "collapse-all"
  && checks.bulkStable;

console.log(JSON.stringify({passed, checks, screenshot: "build/putter-ui-verification.png"}, null, 2));
await command("Browser.close");
if (!passed) process.exitCode = 1;
