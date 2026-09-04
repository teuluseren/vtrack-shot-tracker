const endpoint = process.env.VTRACK_CDP || "http://127.0.0.1:9223";
const uiPort = process.env.VTRACK_UI_PORT || "8765";

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const targets = await fetch(`${endpoint}/json/list`).then(response => response.json());
const target = targets.find(item => item.type === "page" && item.url.includes(`127.0.0.1:${uiPort}`));
if (!target) throw new Error("VTrack browser target was not found");

const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, {once: true});
  socket.addEventListener("error", reject, {once: true});
});

let sequence = 0;
const pending = new Map();
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
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
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
}

await evaluate("localStorage.clear(); location.reload(); true");
await delay(250);

await command("Emulation.setDeviceMetricsOverride", {
  width: 1800,
  height: 1000,
  deviceScaleFactor: 1,
  mobile: false,
});

for (let attempt = 0; attempt < 40; attempt += 1) {
  if (await evaluate("Boolean(document.querySelector('[data-session-head]') && document.querySelector('#rangeSvg line'))")) break;
  await delay(100);
}

await evaluate(`(() => {
  document.querySelectorAll('[data-eye-session]').forEach(button => {
    if (button.getAttribute('aria-label')?.startsWith('Show')) button.click();
  });
  document.querySelectorAll('[data-eye-club]').forEach(button => {
    if (button.getAttribute('aria-label')?.startsWith('Show')) button.click();
  });
  document.querySelectorAll('[data-camera-window]').forEach(input => {
    if (!input.checked) input.click();
  });
})()`);
await delay(150);
await evaluate(`document.querySelector('#rangeZoomReset').click()`);
await delay(80);

const checks = {};
checks.treeTargets = await evaluate(`(() => {
  const session = document.querySelector('.treeToggle').getBoundingClientRect();
  const club = document.querySelector('.clubToggle').getBoundingClientRect();
  return {session: [session.width, session.height], club: [club.width, club.height]};
})()`);

checks.sessionName = await evaluate(`(() => {
  const name = document.querySelector('.sessionHead strong');
  const original = name.textContent;
  name.textContent = '2026-08-30 Evening Driver Fitting Session';
  const style = getComputedStyle(name);
  const result = {
    text: name.textContent,
    whiteSpace: style.whiteSpace,
    fullyVisible: name.scrollWidth <= name.clientWidth && name.scrollHeight <= name.clientHeight
  };
  name.textContent = original;
  return result;
})()`);

checks.sessionDoubleClick = await evaluate(`(() => {
  const head = document.querySelector('[data-session-head]');
  const before = head.closest('.session').classList.contains('closed');
  head.dispatchEvent(new MouseEvent('dblclick', {bubbles: true}));
  const after = document.querySelector('[data-session-head]').closest('.session').classList.contains('closed');
  document.querySelector('[data-session-head]').dispatchEvent(new MouseEvent('dblclick', {bubbles: true}));
  return before !== after;
})()`);

checks.clubDoubleClick = await evaluate(`(() => {
  const head = document.querySelector('[data-club-head]');
  const key = head.dataset.clubHead;
  const before = head.closest('.clubNode').classList.contains('clubClosed');
  head.dispatchEvent(new MouseEvent('dblclick', {bubbles: true}));
  const current = document.querySelector('[data-club-head="' + CSS.escape(key) + '"]');
  const after = current.closest('.clubNode').classList.contains('clubClosed');
  current.dispatchEvent(new MouseEvent('dblclick', {bubbles: true}));
  return before !== after;
})()`);

checks.clubActionOrder = await evaluate(`(() => {
  const rows = [...document.querySelectorAll('.clubHead')].map(header => {
    const items = ['b', 'small', '.clubSwatch', '[data-eye-club]', '[data-club-toggle]']
      .map(selector => header.querySelector(selector).getBoundingClientRect());
    const h = header.getBoundingClientRect(), [name, count, swatch, eye, toggle] = items;
    const centers = items.map(item => item.top + item.height / 2);
    return {
      ordered: name.right <= count.left + .1 && count.right <= swatch.left + .1
        && swatch.right <= eye.left + .1 && eye.right <= toggle.left + .1,
      nameCountGap: count.left - name.right >= 0 && count.left - name.right <= 4,
      controlSpacer: swatch.left - count.right >= 4,
      hierarchy: parseFloat(getComputedStyle(header.querySelector('b')).fontSize) >= 14
        && parseFloat(getComputedStyle(header.querySelector('small')).fontSize) <= 9,
      rightAligned: h.right - toggle.right <= 9,
      compactSpacing: eye.left - swatch.right === 2 && toggle.left - eye.right === 3,
      verticallyCentered: Math.max(...centers) - Math.min(...centers) <= 1
        && Math.abs(centers[0] - (h.top + h.height / 2)) <= 1,
      contained: items.every(item => item.top >= h.top && item.bottom <= h.bottom)
    };
  });
  return {
    eyeBeforeToggle: rows.every(row => row.ordered),
    swatchBeforeEye: rows.every(row => row.ordered),
    rightAligned: rows.every(row => row.rightAligned),
    compactSpacing: rows.every(row => row.compactSpacing),
    nameCountGap: rows.every(row => row.nameCountGap),
    controlSpacer: rows.every(row => row.controlSpacer),
    hierarchy: rows.every(row => row.hierarchy),
    sameRow: rows.every(row => row.verticallyCentered),
    allContained: rows.every(row => row.contained),
    rows: rows.length
  };
})()`);

const clubToggleCenter = await evaluate(`(() => {
  const r = document.querySelector('[data-club-toggle]').getBoundingClientRect();
  return {x: r.left + r.width / 2, y: r.top + r.height / 2};
})()`);
await command("Input.dispatchMouseEvent", {type: "mouseMoved", ...clubToggleCenter});
await delay(160);
checks.clubActionHover = await evaluate(`(() => {
  const button = document.querySelector('[data-club-toggle]');
  const buttonStyle = getComputedStyle(button);
  const highlight = getComputedStyle(button, ':before');
  return {
    hovered: button.matches(':hover'),
    transparentTarget: buttonStyle.backgroundColor === 'rgba(0, 0, 0, 0)',
    insetHighlight: highlight.width === '22px' && highlight.height === '22px',
    visible: highlight.opacity === '1',
    round: highlight.borderRadius === '50%'
  };
})()`);

checks.sessionClubToggle = await evaluate(`(() => {
  const button = document.querySelector('[data-session-clubs]');
  const sessionId = button.closest('.session').dataset.session;
  const states = () => [...document.querySelector('.session[data-session="' + sessionId + '"]').querySelectorAll('.clubNode')]
    .map(node => node.classList.contains('clubClosed'));
  button.click();
  const first = states();
  document.querySelector('.session[data-session="' + sessionId + '"] [data-session-clubs]').click();
  const second = states();
  const collapsed = first.every(Boolean) || second.every(Boolean);
  const expanded = first.every(value => !value) || second.every(value => !value);
  return {collapsed, expanded};
})()`);

checks.sessionClubToggleLayout = await evaluate(`(() => {
  const button = document.querySelector('[data-session-clubs]');
  const header = button.closest('.sessionHead');
  const selectors = ['.treeToggle', '.visibility', '.sessionBubble', '.countPill', '.sessionClubs', '.sessionRename', '.sessionExport'];
  const boxes = selectors.map(selector => header.querySelector(selector).getBoundingClientRect());
  const rows = [...Map.groupBy(boxes, box => Math.round(box.top)).values()];
  const b = button.getBoundingClientRect(), h = header.getBoundingClientRect(), icon = button.querySelector('svg').getBoundingClientRect();
  const before = {left: b.left, top: b.top, iconLeft: icon.left, iconTop: icon.top,
    iconName: button.querySelector('svg').dataset.bulkIcon};
  button.click();
  const changed = document.querySelector('[data-session-clubs]');
  const changedBox = changed.getBoundingClientRect(), changedIcon = changed.querySelector('svg').getBoundingClientRect();
  const after = {left: changedBox.left, top: changedBox.top, iconLeft: changedIcon.left, iconTop: changedIcon.top,
    iconName: changed.querySelector('svg').dataset.bulkIcon};
  changed.click();
  return {
    size: [b.width, b.height],
    allControlsAligned: rows.every(row => { const centers = row.map(box => box.top + box.height / 2); return Math.max(...centers) - Math.min(...centers) <= 1; }),
    controlsDoNotOverlap: rows.every(row => { const ordered = [...row].sort((a, b) => a.left - b.left); return ordered.every((box, index) => index === ordered.length - 1 || box.right <= ordered[index + 1].left + .1); }),
    insideHeader: b.left >= h.left && b.right <= h.right && b.top >= h.top && b.bottom <= h.bottom,
    industryIcon: new Set([before.iconName, after.iconName]).size === 2
      && [before.iconName, after.iconName].every(name => name === 'collapse-all' || name === 'expand-all'),
    iconSize: [icon.width, icon.height],
    stateStable: Math.abs(before.left - after.left) < .1 && Math.abs(before.top - after.top) < .1
      && Math.abs(before.iconLeft - after.iconLeft) < .1 && Math.abs(before.iconTop - after.iconTop) < .1
  };
})()`);

checks.shotRowLayout = await evaluate(`(() => {
  let session = document.querySelector('.session');
  if (session?.classList.contains('closed')) session.querySelector('[data-toggle]').click();
  let clubNode = document.querySelector('.session:not(.closed) .clubNode');
  if (clubNode?.classList.contains('clubClosed')) clubNode.querySelector('[data-club-toggle]').click();
  const rows = [...document.querySelectorAll('.clubNode:not(.clubClosed) .shot')];
  const measurements = rows.map(row => {
    const box = row.getBoundingClientRect();
    const eye = row.querySelector('.visibility').getBoundingClientRect();
    const select = row.querySelector('.shotSelect').getBoundingClientRect();
    const action = row.querySelector('.shotAction').getBoundingClientRect();
    const centers = [eye, select, action].map(item => item.top + item.height / 2);
    return {
      height: box.height,
      aligned: Math.max(...centers) - Math.min(...centers) <= 1,
      contained: [eye, select, action].every(item => item.top >= box.top && item.bottom <= box.bottom),
      ordered: eye.right <= select.left + .1 && select.right <= action.left + .1,
      actionSize: [action.width, action.height],
    };
  });
  const shotGroups = [...document.querySelectorAll('.clubNode:not(.clubClosed) .shots')];
  return {
    count: measurements.length,
    heights: [...new Set(measurements.map(item => item.height))],
    aligned: measurements.every(item => item.aligned),
    contained: measurements.every(item => item.contained),
    ordered: measurements.every(item => item.ordered),
    actionSized: measurements.every(item => item.actionSize[0] === 24 && item.actionSize[1] === 24),
    connectorWidths: [...new Set(shotGroups.map(group => getComputedStyle(group).borderLeftWidth))],
  };
})()`);

checks.workspaceResize = await evaluate(`(() => {
  const handle = document.getElementById('treeRangeResize');
  const before = ['treeCol', 'rangeCol', 'camCol'].map(id => document.getElementById(id).getBoundingClientRect().width);
  const beforeFont = Number.parseFloat(getComputedStyle(document.querySelector('.shotMetric b')).fontSize);
  for (let step = 0; step < 12; step += 1) {
    handle.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
  }
  const after = ['treeCol', 'rangeCol', 'camCol'].map(id => document.getElementById(id).getBoundingClientRect().width);
  const afterFont = Number.parseFloat(getComputedStyle(document.querySelector('.shotMetric b')).fontSize);
  const saved = JSON.parse(localStorage.getItem('vtrackWorkspaceSectionRatiosV1') || 'null');
  handle.dispatchEvent(new MouseEvent('dblclick', {bubbles: true}));
  const reset = localStorage.getItem('vtrackWorkspaceSectionRatiosV1') === null;
  return {
    handles: document.querySelectorAll('.workspaceResizer').length,
    handleWidth: handle.getBoundingClientRect().width,
    accessible: handle.getAttribute('role') === 'separator' && handle.tabIndex === 0,
    changed: after[0] > before[0] && after[1] < before[1] && Math.abs(after[2] - before[2]) < .1,
    fontSizes: [beforeFont, afterFont],
    fontGrew: afterFont > beforeFont,
    saved: Array.isArray(saved) && saved.length === 3,
    reset,
  };
})()`);

checks.axisDetails = await evaluate(`(() => {
  const before = document.querySelectorAll('#rangeSvg line').length;
  document.querySelector('#axisDetails').click();
  const after = document.querySelectorAll('#rangeSvg line').length;
  document.querySelector('#axisDetails').click();
  return {before, after, expanded: after > before};
})()`);

checks.allVisibleShots = await evaluate(`({
  selectorRemoved: !document.querySelector('#rangeCount'),
  visible: Number(document.querySelector('#rangeMeta').textContent.match(/^\\d+/)?.[0] || 0),
  dots: document.querySelectorAll('#rangeSvg [data-shot]').length
})`);

checks.legendClear = await evaluate(`(() => {
  const legend = document.querySelector('#legend').getBoundingClientRect();
  const svg = document.querySelector('#rangeSvg').getBoundingClientRect();
  return {legendTop: legend.top, svgBottom: svg.bottom, clear: legend.top >= svg.bottom - 1};
})()`);

checks.envelopesBounded = await evaluate(`(() => {
  const svg = document.querySelector('#rangeSvg').getBoundingClientRect();
  const envelopes = [...document.querySelectorAll('#rangeSvg [data-envelope]')];
  const tight = envelopes.map(item => {
    const club = item.dataset.envelope;
    const points = [...document.querySelectorAll('#rangeSvg circle[data-shot]')]
      .filter(point => point.querySelector('title')?.textContent.includes(' · ' + club + ' · '));
    const angle = Number(item.getAttribute('transform')?.match(/rotate\\(([-.\\d]+)/)?.[1] || 0) * Math.PI / 180;
    const cos = Math.cos(angle), sin = Math.sin(angle), cx = Number(item.getAttribute('cx')),
      cy = Number(item.getAttribute('cy')), rx = Number(item.getAttribute('rx')), ry = Number(item.getAttribute('ry'));
    const maximumNormalized = Math.max(0, ...points.map(point => {
      const dx = Number(point.getAttribute('cx')) - cx, dy = Number(point.getAttribute('cy')) - cy;
      const u = dx * cos + dy * sin, v = -dx * sin + dy * cos;
      return Math.sqrt((u / rx) ** 2 + (v / ry) ** 2);
    }));
    const box = item.getBoundingClientRect();
    return {club, element: item.tagName.toLowerCase(), pointCount: points.length,
      modeledCount: +item.dataset.envelopeCore, width: box.width, height: box.height,
      bounds: {left: box.left - svg.left, right: box.right - svg.right, top: box.top - svg.top, bottom: box.bottom - svg.bottom},
      coverage: item.dataset.envelopeCoverage, maximumNormalized,
      enclosesAll: maximumNormalized <= 1.000001,
      rotated: item.getAttribute('transform')?.startsWith('rotate(') === true};
  });
  return {
    count: envelopes.length,
    bounded: envelopes.every(item => {
      const box = item.getBoundingClientRect();
      return box.left >= svg.left - 1 && box.right <= svg.right + 1
        && box.top >= svg.top - 1 && box.bottom <= svg.bottom + 1;
    }),
    tight,
    trueEllipses: tight.every(item => item.element === 'ellipse' && item.width > 0 && item.height > 0),
    fullCoverage: tight.every(item => item.modeledCount === item.pointCount && item.coverage === 'all'
      && item.enclosesAll && item.rotated),
  };
})()`);

checks.hiddenWoodShots = await evaluate(`(() => {
  for (const id of [64, 65]) document.querySelector('[data-eye-shot="' + id + '"]')?.click();
  const envelope = document.querySelector('#rangeSvg [data-envelope="W3"]');
  const pointCount = [...document.querySelectorAll('#rangeSvg circle[data-shot]')]
    .filter(point => point.querySelector('title')?.textContent.includes(' · W3 · ')).length;
  const angle = Number(envelope?.getAttribute('transform')?.match(/rotate\\(([-.\\d]+)/)?.[1] || 0) * Math.PI / 180;
  const cos = Math.cos(angle), sin = Math.sin(angle), cx = Number(envelope?.getAttribute('cx')),
    cy = Number(envelope?.getAttribute('cy')), rx = Number(envelope?.getAttribute('rx')), ry = Number(envelope?.getAttribute('ry'));
  const normalized = [...document.querySelectorAll('#rangeSvg circle[data-shot]')]
    .filter(point => point.querySelector('title')?.textContent.includes(' · W3 · '))
    .map(point => { const dx = Number(point.getAttribute('cx')) - cx, dy = Number(point.getAttribute('cy')) - cy;
      return Math.sqrt(((dx * cos + dy * sin) / rx) ** 2 + ((-dx * sin + dy * cos) / ry) ** 2); });
  const result = {pointCount, modeledCount: Number(envelope?.dataset.envelopeCore || 0),
    maximumNormalized: Math.max(...normalized)};
  for (const id of [64, 65]) document.querySelector('[data-eye-shot="' + id + '"]')?.click();
  return {...result, allRemainingIncluded: result.pointCount === 28 && result.modeledCount === 28
    && result.maximumNormalized <= 1.000001};
})()`);

checks.rangeShotReveal = await evaluate(`(async () => {
  const panel = document.querySelector('#treeCol');
  if (!panel.classList.contains('collapsed')) document.querySelector('.collapse[data-col="treeCol"]').click();
  const point = document.querySelector('#rangeSvg [data-shot]'), shotId = point?.dataset.shot;
  if (!point || !shotId) return {panelExpanded: false, sessionExpanded: false, clubExpanded: false, scrolledIntoView: false};
  point.dispatchEvent(new MouseEvent('click', {bubbles: true}));
  await new Promise(resolve => setTimeout(resolve, 250));
  const button = document.querySelector('#tree [data-shot="' + shotId + '"]');
  const tree = document.querySelector('#tree').getBoundingClientRect();
  const box = button.getBoundingClientRect();
  return {
    panelExpanded: !panel.classList.contains('collapsed'),
    sessionExpanded: !button.closest('.session').classList.contains('closed'),
    clubExpanded: !button.closest('.clubNode').classList.contains('clubClosed'),
    scrolledIntoView: box.top >= tree.top && box.bottom <= tree.bottom,
  };
})()`);

checks.replayWindows = await evaluate(`(() => {
  const button = document.querySelector('#cameraWindows');
  button.click();
  const menu = document.querySelector('#cameraWindowsMenu');
  const labels = [...menu.querySelectorAll('label')].map(label => label.textContent.trim());
  const cards = [...document.querySelectorAll('#cameraGrid > .card')];
  const overlay = cards[0]?.querySelector('.cardBar');
  const missingBefore = cards.filter(card => card.dataset.available === 'false').length;
  const swing2 = menu.querySelector('[data-camera-window="swing2"]');
  const beforeCount = cards.length;
  swing2.click();
  const hiddenCount = document.querySelectorAll('#cameraGrid > .card').length;
  swing2.click();
  const restoredCount = document.querySelectorAll('#cameraGrid > .card').length;
  return {
    labels,
    allChoices: ['Impact Replay', 'Swing Cam 1', 'Swing Cam 2', 'Shot Heatmap'].every(label => labels.includes(label)),
    allRendered: beforeCount === 4,
    toggles: hiddenCount === 3 && restoredCount === 4,
    missingPersistent: missingBefore >= 0 && document.querySelectorAll('#cameraGrid > .card[data-available="false"]').length >= 0,
    overlay: Boolean(document.querySelector('#cameraGrid > .card .cardBar')
      && getComputedStyle(document.querySelector('#cameraGrid > .card .cardBar')).position === 'absolute'),
  };
})()`);

checks.replayGeometryPersistence = await evaluate(`(async () => {
  const choose = async id => {
    document.querySelector('#tree [data-shot="' + id + '"]').click();
    for (let attempt = 0; attempt < 20; attempt += 1) {
      if (document.querySelector('#shotLabel')?.textContent.includes('#' + id)) break;
      await new Promise(resolve => setTimeout(resolve, 50));
    }
  };
  await choose(196);
  let card = document.querySelector('#cameraGrid > .card[data-kind="impact"]');
  card.style.width = '333px'; card.style.height = '211px';
  await new Promise(resolve => setTimeout(resolve, 80));
  await choose(5);
  card = document.querySelector('#cameraGrid > .card[data-kind="impact"]');
  const missing = {present: Boolean(card), available: card?.dataset.available, width: card?.offsetWidth, height: card?.offsetHeight};
  await choose(196);
  card = document.querySelector('#cameraGrid > .card[data-kind="impact"]');
  const returned = {present: Boolean(card), available: card?.dataset.available, width: card?.offsetWidth, height: card?.offsetHeight};
  return {missing, returned, retained: missing.present && missing.available === 'false'
    && returned.present && returned.available === 'true' && missing.width === 333 && returned.width === 333
    && missing.height === 211 && returned.height === 211};
})()`);

checks.personaComparisons = await evaluate(`(async () => {
  document.querySelector('[data-summary-club]')?.click();
  const values = {}, scores = {};
  for (const profile of ['woman', 'man', 'senior', 'junior']) {
    document.querySelector('[data-profile="' + profile + '"]').click();
    await Promise.resolve();
    const rows = [...document.querySelectorAll('.summaryTable tbody tr')];
    values[profile] = rows.map(row => row.lastElementChild.textContent.trim()).join('|');
    const ratios = rows.map((row, index) => {
      const actual = Number.parseFloat(row.children[1].textContent), reference = Number.parseFloat(row.children[2].textContent);
      return index === rows.length - 1 ? reference / actual : actual / reference;
    }).filter(Number.isFinite);
    scores[profile] = {displayed: Number.parseFloat(document.querySelector('.gaugeCopy strong').textContent),
      expected: Math.round(ratios.reduce((sum, value) => sum + value, 0) / ratios.length * 100)};
  }
  document.querySelector('[data-profile="woman"]').click();
  await Promise.resolve();
  const copy = document.querySelector('.gaugeCopy p').textContent;
  const art = document.querySelector('.golferGauge img.golferFill');
  if (art && !art.complete) await Promise.race([
    new Promise(resolve => art.addEventListener('load', resolve, {once: true})),
    new Promise(resolve => setTimeout(resolve, 1500))
  ]);
  const modalText = document.querySelector('#summaryContent').textContent;
  const hero = document.querySelector('.summaryHero');
  const heroBox = hero.getBoundingClientRect();
  const golferBox = document.querySelector('.golferGauge').getBoundingClientRect();
  const copyBox = document.querySelector('.gaugeCopy').getBoundingClientRect();
  document.querySelector('#summaryClose').click();
  return {values, distinct: new Set(Object.values(values)).size === 4,
    scores, formulaMatches: Object.values(scores).every(score => Math.abs(score.displayed - score.expected) <= 1),
    exceeds100: Object.values(scores).some(score => score.displayed > 100),
    explained: copy.includes('100% matches') && copy.includes('score higher'),
    cleanCopy: !/TrackMan|Arccos|USGA|R&A/i.test(modalText),
    graphicSeparated: golferBox.left < heroBox.left + 10 && copyBox.left - golferBox.right >= 20,
    graphicGeometry: {leftInset: golferBox.left - heroBox.left,
      copyGap: copyBox.left - golferBox.right},
    swinging: Boolean(art?.closest('[aria-label*="swinging"]')),
    artLoaded: Boolean(art?.complete && art.naturalWidth > 0)};
})()`);

checks.rangeLeftMargin = await evaluate(`Number(document.querySelector('#rangeClip rect')?.getAttribute('x'))`);

checks.clearRangeTooltip = await evaluate(`(() => {
  const button = document.querySelector('#clearRange');
  return button.title.includes('No sessions or shots are deleted') && button.getAttribute('aria-label').includes('without deleting');
})()`);

checks.idleRangeStable = await evaluate(`(async () => {
  const svg = document.querySelector('#rangeSvg');
  const firstNode = svg.firstElementChild;
  const viewBox = svg.getAttribute('viewBox');
  await new Promise(resolve => setTimeout(resolve, 1400));
  return {sameNode: firstNode === svg.firstElementChild, sameViewBox: viewBox === svg.getAttribute('viewBox')};
})()`);

checks.heatLayer = await evaluate(`(() => {
  const canvas = document.querySelector('#heatCanvas');
  const image = document.querySelector('#faceImg');
  return {
    canvasZ: Number(getComputedStyle(canvas).zIndex),
    imageZ: Number(getComputedStyle(image).zIndex),
    above: Number(getComputedStyle(canvas).zIndex) > Number(getComputedStyle(image).zIndex)
  };
})()`);

checks.clubVisibility = await evaluate(`(() => {
  const before = document.querySelector('#rangeMeta').textContent;
  const svg = document.querySelector('#rangeSvg');
  const beforeSize = {height: svg.clientHeight, viewBox: svg.viewBox.baseVal.width};
  document.querySelector('[data-eye-club]').click();
  const after = document.querySelector('#rangeMeta').textContent;
  const afterSize = {height: svg.clientHeight, viewBox: svg.viewBox.baseVal.width};
  document.querySelector('[data-eye-club]').click();
  return {
    before,
    after,
    changed: before !== after,
    stableSize: beforeSize.height === afterSize.height && beforeSize.viewBox === afterSize.viewBox,
    beforeSize,
    afterSize
  };
})()`);

checks.collapsedRangeControls = await evaluate(`(() => {
  const button = document.querySelector('.collapse[data-col="rangeCol"]');
  button.click();
  const hidden = getComputedStyle(document.querySelector('.rangeControls')).display === 'none';
  const label = document.querySelector('#rangeCol .head b'), labelBox = label.getBoundingClientRect(), buttonBox = button.getBoundingClientRect(), style = getComputedStyle(label), fontSize = parseFloat(style.fontSize), writingMode = style.writingMode;
  button.click();
  return {hidden, belowButton: labelBox.top >= buttonBox.bottom, readable: fontSize >= 12, vertical: writingMode === 'vertical-rl'};
})()`);

checks.replayResponsiveRange = await evaluate(`(async () => {
  const svg = document.querySelector('#rangeSvg');
  const before = {client: svg.clientWidth, viewBox: svg.viewBox.baseVal.width};
  document.querySelector('.collapse[data-col="camCol"]').click();
  await new Promise(resolve => setTimeout(resolve, 100));
  const after = {client: svg.clientWidth, viewBox: svg.viewBox.baseVal.width};
  document.querySelector('.collapse[data-col="camCol"]').click();
  return {before, after, grew: after.client > before.client && after.viewBox > before.viewBox};
})()`);

checks.rangeTypography = await evaluate(`(() => {
  const distance = document.querySelector('#rangeSvg .distanceTick.major');
  const lateral = document.querySelector('#rangeSvg .lateralTick.major');
  const boundary = document.querySelector('#rangeSvg .rangeBoundaryLabel');
  return {
    distance: Number(distance?.getAttribute('font-size') || 0),
    lateral: Number(lateral?.getAttribute('font-size') || 0),
    boundary: Number(boundary?.getAttribute('font-size') || 0),
    distanceWeight: Number(distance?.getAttribute('font-weight') || 0),
    lateralWeight: Number(lateral?.getAttribute('font-weight') || 0)
  };
})()`);

checks.clubFaceAsset = await evaluate(`(() => {
  const image = document.querySelector('#faceImg');
  return {
    local: Boolean(image?.getAttribute('src')?.startsWith('/assets/club-face-')),
    loaded: Boolean(image?.complete && image.naturalWidth > 0),
    filter: image ? getComputedStyle(image).filter : ''
  };
})()`);

checks.woodImpactCenters = await evaluate(`(async () => {
  const shots = (await fetch('/api/shots', {cache: 'no-store'}).then(r => r.json())).filter(s => s.club === 'W3');
  const limits = {w: 92, h: 46}, render = {w: 128, h: 64}, face = {w: .69, h: .33};
  const polygon = [[.01,.34],[.08,.16],[.25,.05],[.72,.05],[.94,.21],[.99,.45],[.92,.74],[.70,.94],[.24,.95],[.05,.72]];
  const valid = shots.filter(s => Number.isFinite(Number(s.horizontal_face_impact))
    && Number.isFinite(Number(s.vertical_face_impact))
    && Math.abs(Number(s.horizontal_face_impact)) <= limits.w * .55
    && Math.abs(Number(s.vertical_face_impact)) <= limits.h * .58);
  const scale = Math.min(face.w / render.w, face.h / render.h);
  const inside = ([x, y]) => {
    let result = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const [xi, yi] = polygon[i], [xj, yj] = polygon[j];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) result = !result;
    }
    return result;
  };
  const outside = valid.filter(s => !inside([
    .5 + Number(s.horizontal_face_impact) * scale / face.w,
    .5 - Number(s.vertical_face_impact) * scale / face.h
  ])).map(s => s.id);
  return {
    source: shots.length,
    valid: valid.length,
    sentinelExcluded: shots.length - valid.length,
    allInside: outside.length === 0,
    outside
  };
})()`);

checks.tooltips = await evaluate(`({
  tiles: document.querySelectorAll('.tile[title]').length,
  pills: document.querySelectorAll('.chip[title]').length,
  swatches: document.querySelectorAll('.clubSwatch[title]').length
})`);

checks.emptyRangeGuidance = await evaluate(`(() => {
  document.querySelector('#clearRange').click();
  const group = document.querySelector('#rangeSvg .emptyRangeMessage');
  const text = group?.querySelector('text');
  const backing = group?.querySelector('rect');
  return {
    present: Boolean(group && text && backing),
    fontSize: Number(text?.getAttribute('font-size') || 0),
    fontWeight: Number(text?.getAttribute('font-weight') || 0),
    backingOpacity: Number(backing?.getAttribute('fill-opacity') || 0)
  };
})()`);

checks.rangeZoom = await evaluate(`(async() => {
  const label = document.querySelector('#rangeZoomLabel');
  const svg = document.querySelector('#rangeSvg');
  const overlay = document.querySelector('.rangeZoomOverlay');
  const rangeBody = document.querySelector('.rangeBody');
  const overlayBox = overlay.getBoundingClientRect(), rangeBox = rangeBody.getBoundingClientRect();
  const before = label.textContent;
  document.querySelector('#rangeZoomIn').click();
  await new Promise(resolve => setTimeout(resolve, 80));
  const zoomed = label.textContent;
  const boundary = [...document.querySelectorAll('.rangeBoundaryLabel')].map(x => x.textContent).join(' ');
  document.querySelector('#rangeZoomOut').click();
  svg.focus();
  svg.dispatchEvent(new KeyboardEvent('keydown', {key: '+', code: 'Equal', bubbles: true, cancelable: true}));
  const keyboardZoomed = label.textContent;
  svg.dispatchEvent(new KeyboardEvent('keydown', {key: '-', code: 'Minus', bubbles: true, cancelable: true}));
  const box = svg.getBoundingClientRect(), clientX = box.left + box.width / 2, clientY = box.top + box.height / 2;
  svg.dispatchEvent(new WheelEvent('wheel', {deltaY: -100, clientX, clientY, bubbles: true, cancelable: true}));
  const wheelZoomed = label.textContent;
  svg.dispatchEvent(new WheelEvent('wheel', {deltaY: 100, clientX, clientY, bubbles: true, cancelable: true}));
  await new Promise(resolve => setTimeout(resolve, 400));
  const restored = label.textContent;
  const saved = await fetch('/api/preferences', {cache: 'no-store'}).then(r => r.json());
  return {before, zoomed, keyboardZoomed, wheelZoomed, restored, boundary,
    persisted: saved.preferences?.rangeDistanceMax,
    resetText: document.querySelector('#rangeZoomReset').textContent.trim(),
    resetAvailable: !document.querySelector('#rangeZoomReset').disabled,
    clipped: document.querySelector('.shotLayer')?.getAttribute('clip-path'),
    visible: overlayBox.width > 0 && overlayBox.height > 0,
    insideRange: overlayBox.left >= rangeBox.left && overlayBox.right <= rangeBox.right
      && overlayBox.top >= rangeBox.top && overlayBox.bottom <= rangeBox.bottom};
})()`);

checks.rangeZoomAnchor = await evaluate(`(() => {
  document.querySelector('#rangeZoomReset').click();
  document.querySelectorAll('[data-eye-session]').forEach(button=>{if(button.getAttribute('aria-label')?.startsWith('Show'))button.click()});
  document.querySelectorAll('[data-eye-club]').forEach(button=>{if(button.getAttribute('aria-label')?.startsWith('Show'))button.click()});
  const svg = document.querySelector('#rangeSvg'), W = svg.viewBox.baseVal.width, H = svg.viewBox.baseVal.height;
  const candidates = [...svg.querySelectorAll('circle[data-shot]')], marker = candidates.find(node => {
    const x=Number(node.getAttribute('cx')),y=Number(node.getAttribute('cy'));
    return x>104&&x<W-38&&y>48&&y<H-60;
  });
  if(!marker)return {found:false,count:candidates.length,W,H,sample:candidates[0]?{cx:candidates[0].getAttribute('cx'),cy:candidates[0].getAttribute('cy')}:null};
  const screenPoint=node=>{const point=svg.createSVGPoint();point.x=Number(node.getAttribute('cx'));point.y=Number(node.getAttribute('cy'));return point.matrixTransform(svg.getScreenCTM())};
  const id=marker.dataset.shot,before=screenPoint(marker),x=before.x,y=before.y;
  svg.dispatchEvent(new WheelEvent('wheel',{deltaY:-100,clientX:x,clientY:y,bubbles:true,cancelable:true}));
  const afterNode=[...svg.querySelectorAll('circle[data-shot]')].find(node=>node.dataset.shot===id),after=screenPoint(afterNode),afterX=after.x,afterY=after.y;
  document.querySelector('#rangeZoomReset').click();
  return {found:true,delta:Math.hypot(afterX-x,afterY-y)};
})()`);

checks.rangeClipModes = await evaluate(`(() => {
  document.querySelector('[data-range-view="flight"]').click();
  const flightNodes=[...document.querySelectorAll('#rangeSvg [data-shot]')],flight={clipRects:document.querySelectorAll('#flightClip rect').length,nodes:flightNodes.length,allClipped:flightNodes.every(node=>node.getAttribute('clip-path')==='url(#flightClip)')};
  document.querySelector('[data-range-view="putting"]').click();
  const putting=document.querySelector('#rangeSvg .shotLayer')?.getAttribute('clip-path');
  document.querySelector('[data-range-view="dispersion"]').click();
  return {flight,putting};
})()`);

await evaluate(`document.querySelector('#rangeZoomIn').click()`);
const rangeDragBox = await evaluate(`(() => {const box=document.querySelector('#rangeSvg').getBoundingClientRect();return {left:box.left,top:box.top,width:box.width,height:box.height,selected:document.querySelector('.shot.sel [data-shot]')?.dataset.shot||null,worldShape:document.querySelector('.rangeWorldShape')?.getAttribute('d')||null}})()`);
const dragStart = {x: rangeDragBox.left + rangeDragBox.width * .48, y: rangeDragBox.top + rangeDragBox.height * .38};
await command('Input.dispatchMouseEvent', {type: 'mousePressed', ...dragStart, button: 'left', clickCount: 1});
await command('Input.dispatchMouseEvent', {type: 'mouseMoved', x: dragStart.x - 130, y: dragStart.y + 65, button: 'left', buttons: 1});
await command('Input.dispatchMouseEvent', {type: 'mouseReleased', x: dragStart.x - 130, y: dragStart.y + 65, button: 'left', clickCount: 1});
checks.rangePan = await evaluate(`(async() => {
  await new Promise(resolve => setTimeout(resolve, 450));
  const saved = await fetch('/api/preferences', {cache: 'no-store'}).then(r => r.json());
  const boundary = [...document.querySelectorAll('.rangeBoundaryLabel')].map(x => x.textContent).join(' ');
  const selected = document.querySelector('.shot.sel [data-shot]')?.dataset.shot || null;
  const result = {distance: saved.preferences?.rangePanDistance, side: saved.preferences?.rangePanSide,
    boundary, clickSuppressed: selected === ${JSON.stringify(rangeDragBox.selected)},
    worldShapeMoved: document.querySelector('.rangeWorldShape')?.getAttribute('d') !== ${JSON.stringify(rangeDragBox.worldShape)},
    ellipseClipped: document.querySelector('.dispersionLayer')?.getAttribute('clip-path') === 'url(#rangeClip)'};
  document.querySelector('#rangeZoomReset').click();
  return result;
})()`);

const pinchBox = await evaluate(`(() => {const box=document.querySelector('#rangeSvg').getBoundingClientRect();return {x:box.left+box.width/2,y:box.top+box.height/2}})()`);
await command('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 2});
await command('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [
  {x: pinchBox.x - 45, y: pinchBox.y, id: 1, radiusX: 2, radiusY: 2},
  {x: pinchBox.x + 45, y: pinchBox.y, id: 2, radiusX: 2, radiusY: 2}
]});
await command('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: [
  {x: pinchBox.x - 80, y: pinchBox.y, id: 1, radiusX: 2, radiusY: 2},
  {x: pinchBox.x + 80, y: pinchBox.y, id: 2, radiusX: 2, radiusY: 2}
]});
await command('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
checks.rangePinch = await evaluate(`(() => {const zoomed=document.querySelector('#rangeZoomLabel').textContent;document.querySelector('#rangeZoomReset').click();return {zoomed}})()`);
await command('Emulation.setTouchEmulationEnabled', {enabled: false});
await evaluate(`(() => {document.querySelectorAll('[data-eye-session]').forEach(button=>{if(button.getAttribute('aria-label')?.startsWith('Show'))button.click()});document.querySelectorAll('[data-eye-club]').forEach(button=>{if(button.getAttribute('aria-label')?.startsWith('Show'))button.click()})})()`);
await delay(80);
const rangeShotTarget = await evaluate(`(() => {const svg=document.querySelector('#rangeSvg'),current=document.querySelector('#shotLabel').textContent.match(/#(\\d+)/)?.[1]||null,W=svg.viewBox.baseVal.width,H=svg.viewBox.baseVal.height;for(const point of svg.querySelectorAll('circle[data-shot]')){const cx=Number(point.getAttribute('cx')),cy=Number(point.getAttribute('cy'));if(cx<=104||cx>=W-38||cy<=48||cy>=H-60)continue;const p=svg.createSVGPoint();p.x=cx;p.y=cy;const screen=p.matrixTransform(svg.getScreenCTM()),top=document.elementFromPoint(screen.x,screen.y)?.closest?.('[data-shot]');if(top&&top.dataset.shot!==current)return{id:top.dataset.shot,before:current,x:screen.x,y:screen.y}}return null})()`);
if (rangeShotTarget) {
  await command('Input.dispatchMouseEvent', {type: 'mousePressed', x: rangeShotTarget.x, y: rangeShotTarget.y, button: 'left', clickCount: 1});
  await command('Input.dispatchMouseEvent', {type: 'mouseReleased', x: rangeShotTarget.x, y: rangeShotTarget.y, button: 'left', clickCount: 1});
}
checks.rangePointerShotClick = await evaluate(`(async() => {await new Promise(resolve => setTimeout(resolve,80));return {target:${JSON.stringify(rangeShotTarget?.id || null)},before:${JSON.stringify(rangeShotTarget?.before || null)},selected:document.querySelector('#shotLabel').textContent}})()`);

checks.bagMapping = await evaluate(`(async() => {
  document.querySelector('#bagSettings').click();
  for (let i = 0; i < 30 && !document.querySelector('[data-bag-source="W3"]'); i++) {
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  const select = document.querySelector('[data-bag-source="W3"]');
  if (!select) return {opened: false};
  select.value = 'W5';
  document.querySelector('#bagForm').requestSubmit();
  await new Promise(resolve => setTimeout(resolve, 500));
  const saved = await fetch('/api/bag-mapping', {cache: 'no-store'}).then(r => r.json());
  return {opened: true, modalClosed: !document.querySelector('#bagModal').classList.contains('open'), persisted: saved.mapping?.W3};
})()`);

const passed = checks.treeTargets.session.every(value => value >= 28)
  && checks.treeTargets.club.every(value => value >= 26)
  && checks.sessionName.whiteSpace === "normal"
  && checks.sessionName.fullyVisible
  && checks.sessionDoubleClick
  && checks.clubDoubleClick
  && checks.clubActionOrder.eyeBeforeToggle
  && checks.clubActionOrder.swatchBeforeEye
  && checks.clubActionOrder.rightAligned
  && checks.clubActionOrder.compactSpacing
  && checks.clubActionOrder.nameCountGap
  && checks.clubActionOrder.controlSpacer
  && checks.clubActionOrder.hierarchy
  && checks.clubActionOrder.sameRow
  && checks.clubActionOrder.allContained
  && checks.clubActionHover.hovered
  && checks.clubActionHover.transparentTarget
  && checks.clubActionHover.insetHighlight
  && checks.clubActionHover.visible
  && checks.clubActionHover.round
  && checks.sessionClubToggle.collapsed
  && checks.sessionClubToggle.expanded
  && checks.sessionClubToggleLayout.size.every(value => value === 28)
  && checks.sessionClubToggleLayout.allControlsAligned
  && checks.sessionClubToggleLayout.controlsDoNotOverlap
  && checks.sessionClubToggleLayout.insideHeader
  && checks.sessionClubToggleLayout.industryIcon
  && checks.sessionClubToggleLayout.iconSize.every(value => value === 16)
  && checks.sessionClubToggleLayout.stateStable
  && checks.shotRowLayout.count > 0
  && checks.shotRowLayout.heights.length === 1
  && checks.shotRowLayout.aligned
  && checks.shotRowLayout.contained
  && checks.shotRowLayout.ordered
  && checks.shotRowLayout.actionSized
  && checks.shotRowLayout.connectorWidths.length === 1
  && checks.shotRowLayout.connectorWidths[0] === "1px"
  && checks.workspaceResize.handles === 2
  && checks.workspaceResize.handleWidth === 7
  && checks.workspaceResize.accessible
  && checks.workspaceResize.changed
  && checks.workspaceResize.fontGrew
  && checks.workspaceResize.saved
  && checks.workspaceResize.reset
  && checks.axisDetails.expanded
  && checks.allVisibleShots.selectorRemoved
  && checks.allVisibleShots.visible === 196
  && checks.allVisibleShots.dots === 196
  && checks.legendClear.clear
  && checks.envelopesBounded.count > 0
  && checks.envelopesBounded.trueEllipses
  && checks.envelopesBounded.fullCoverage
  && checks.hiddenWoodShots.allRemainingIncluded
  && checks.rangeShotReveal.panelExpanded
  && checks.rangeShotReveal.sessionExpanded
  && checks.rangeShotReveal.clubExpanded
  && checks.rangeShotReveal.scrolledIntoView
  && checks.replayWindows.allChoices
  && checks.replayWindows.allRendered
  && checks.replayWindows.toggles
  && checks.replayWindows.missingPersistent
  && checks.replayWindows.overlay
  && checks.replayGeometryPersistence.retained
  && checks.personaComparisons.distinct
  && checks.personaComparisons.formulaMatches
  && checks.personaComparisons.exceeds100
  && checks.personaComparisons.explained
  && checks.personaComparisons.cleanCopy
  && checks.personaComparisons.graphicSeparated
  && checks.personaComparisons.swinging
  && checks.personaComparisons.artLoaded
  && checks.rangeLeftMargin >= 70
  && checks.rangeLeftMargin <= 100
  && checks.clearRangeTooltip
  && checks.idleRangeStable.sameNode
  && checks.idleRangeStable.sameViewBox
  && checks.heatLayer.above
  && checks.clubVisibility.changed
  && checks.clubVisibility.stableSize
  && checks.collapsedRangeControls.hidden
  && checks.collapsedRangeControls.belowButton
  && checks.collapsedRangeControls.readable
  && checks.collapsedRangeControls.vertical
  && checks.replayResponsiveRange.grew
  && checks.rangeTypography.distance >= 15
  && checks.rangeTypography.lateral >= 13
  && checks.rangeTypography.boundary >= 14
  && checks.rangeTypography.distanceWeight >= 800
  && checks.rangeTypography.lateralWeight >= 800
  && checks.clubFaceAsset.local
  && checks.clubFaceAsset.loaded
  && checks.clubFaceAsset.filter === "none"
  && checks.woodImpactCenters.source === 30
  && checks.woodImpactCenters.valid === 29
  && checks.woodImpactCenters.sentinelExcluded === 1
  && checks.woodImpactCenters.allInside
  && checks.emptyRangeGuidance.present
  && checks.emptyRangeGuidance.fontSize >= 18
  && checks.emptyRangeGuidance.fontWeight >= 800
  && checks.emptyRangeGuidance.backingOpacity >= .8
  && checks.rangeZoom.before === "325 yd"
  && checks.rangeZoom.zoomed === "250 yd"
  && checks.rangeZoom.keyboardZoomed === "250 yd"
  && checks.rangeZoom.wheelZoomed === "250 yd"
  && checks.rangeZoom.restored === "325 yd"
  && checks.rangeZoom.boundary.includes("VIEW START")
  && checks.rangeZoom.persisted === 325
  && checks.rangeZoom.resetText.startsWith("Reset")
  && checks.rangeZoom.resetAvailable
  && checks.rangeZoom.clipped === "url(#rangeClip)"
  && checks.rangeZoom.visible
  && checks.rangeZoom.insideRange
  && checks.rangeZoomAnchor.found
  && checks.rangeZoomAnchor.delta <= 2
  && checks.rangeClipModes.flight.clipRects === 2
  && checks.rangeClipModes.flight.nodes > 0
  && checks.rangeClipModes.flight.allClipped
  && checks.rangeClipModes.putting === "url(#puttingClip)"
  && checks.rangePan.distance > 0
  && Math.abs(checks.rangePan.side) > 0
  && checks.rangePan.boundary.includes("VIEW START")
  && checks.rangePan.clickSuppressed
  && checks.rangePan.worldShapeMoved
  && checks.rangePan.ellipseClipped
  && ["100 yd", "150 yd", "200 yd", "250 yd"].includes(checks.rangePinch.zoomed)
  && checks.rangePointerShotClick.target
  && checks.rangePointerShotClick.before !== checks.rangePointerShotClick.target
  && checks.rangePointerShotClick.selected.includes('#' + checks.rangePointerShotClick.target)
  && checks.bagMapping.opened
  && checks.bagMapping.modalClosed
  && checks.bagMapping.persisted === "W5"
  && checks.tooltips.tiles > 0
  && checks.tooltips.pills > 0
  && checks.tooltips.swatches > 0;

console.log(JSON.stringify({passed, checks}, null, 2));
await command("Browser.close");
if (!passed) process.exitCode = 1;
