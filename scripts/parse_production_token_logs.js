/**
 * Parse production MindGraph logs for token usage estimates.
 * Run: node scripts/parse_production_token_logs.js [logsDir]
 */
const fs = require('fs');
const path = require('path');

const logsDir = process.argv[2] || path.join(process.env.USERPROFILE || '', 'Desktop', 'logs');

const RE_DIFY = /\[STREAM\] Tracked Dify token usage: input=(\d+), output=(\d+), total=(\d+)/;
const RE_TOKEN_BUFFER = /\[TokenBuffer\] Wrote (\d+) records \((\d+) tokens\)/;
const RE_GEN_GRAPH = /POST \/api\/generate_graph.*Response: 200/;
const RE_PALETTE_START = /POST \/thinking_mode\/node_palette\/start.*Response: 200/;

function stripAnsi(line) {
  return line.replace(/\u001b\[[0-9;]*m/g, '');
}

function median(arr) {
  if (!arr.length) return 0;
  const s = [...arr].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : Math.round((s[m - 1] + s[m]) / 2);
}

function avg(arr) {
  if (!arr.length) return 0;
  return Math.round(arr.reduce((a, b) => a + b, 0) / arr.length);
}

function stats(arr) {
  if (!arr.length) return null;
  return {
    n: arr.length,
    avg: avg(arr),
    median: median(arr),
    min: Math.min(...arr),
    max: Math.max(...arr),
    sum: arr.reduce((a, b) => a + b, 0),
  };
}

function pct(arr, p) {
  if (!arr.length) return 0;
  const s = [...arr].sort((a, b) => a - b);
  const idx = Math.min(s.length - 1, Math.floor((p / 100) * s.length));
  return s[idx];
}

function parseTimestamp(line) {
  const m = line.match(/\[(\d{2}:\d{2}:\d{2})\]/);
  return m ? m[1] : null;
}

function tsToSec(ts) {
  if (!ts) return null;
  const [h, m, s] = ts.split(':').map(Number);
  return h * 3600 + m * 60 + s;
}

function listLogFiles(dir) {
  return fs.readdirSync(dir)
    .filter((f) => /^app(\.|$)/.test(f))
    .map((f) => path.join(dir, f))
    .filter((p) => fs.statSync(p).isFile());
}

function parseFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split('\n').map(stripAnsi);

  /** @type {Array<{sec:number, worker:string, kind:string, tokens?:number, records?:number, input?:number, output?:number}>} */
  const events = [];

  for (const line of lines) {
    const ts = parseTimestamp(line);
    const sec = tsToSec(ts);
    const workerMatch = line.match(/\|\s+\[(\d+)\]/);
    const worker = workerMatch ? workerMatch[1] : '';

    const dify = line.match(RE_DIFY);
    if (dify) {
      events.push({
        sec,
        worker,
        kind: 'mindmate',
        input: +dify[1],
        output: +dify[2],
        tokens: +dify[3],
      });
      continue;
    }

    const tb = line.match(RE_TOKEN_BUFFER);
    if (tb) {
      events.push({
        sec,
        worker,
        kind: 'token_buffer',
        records: +tb[1],
        tokens: +tb[2],
      });
      continue;
    }

    if (RE_GEN_GRAPH.test(line)) {
      events.push({ sec, worker, kind: 'gen_graph' });
      continue;
    }

    if (RE_PALETTE_START.test(line)) {
      events.push({ sec, worker, kind: 'palette_start' });
    }
  }

  return events;
}

function findNextBuffer(events, startIdx, worker, maxSec = 120, recordFilter = null) {
  const start = events[startIdx];
  if (!start || start.sec == null) return null;
  for (let i = startIdx + 1; i < events.length; i++) {
    const e = events[i];
    if (e.sec - start.sec > maxSec) break;
    if (e.kind !== 'token_buffer') continue;
    if (worker && e.worker !== worker) continue;
    if (recordFilter && !recordFilter(e.records)) continue;
    return e;
  }
  return null;
}

function filterOutliers(arr, max = 20000) {
  return arr.filter((v) => v > 0 && v <= max);
}

function main() {
  if (!fs.existsSync(logsDir)) {
    console.error('Logs directory not found:', logsDir);
    process.exit(1);
  }

  const files = listLogFiles(logsDir);
  let allEvents = [];
  for (const f of files) {
    try {
      allEvents = allEvents.concat(parseFile(f));
    } catch (e) {
      console.error('Failed', f, e.message);
    }
  }

  const mindmateTotals = allEvents.filter((e) => e.kind === 'mindmate').map((e) => e.tokens);
  const mindmateClean = filterOutliers(mindmateTotals, 50000);

  // Correlate generate_graph -> next token_buffer (2-6 records, typical diagram flow)
  const genGraphTokens = [];
  for (let i = 0; i < allEvents.length; i++) {
    if (allEvents[i].kind !== 'gen_graph') continue;
    const buf = findNextBuffer(allEvents, i, allEvents[i].worker, 90, (r) => r >= 1 && r <= 6);
    if (buf && buf.tokens <= 20000) genGraphTokens.push(buf.tokens);
  }

  // Also: 2-4 record batches globally (diagram-like)
  const diagramLikeBatches = allEvents
    .filter((e) => e.kind === 'token_buffer' && e.records >= 2 && e.records <= 4 && e.tokens <= 15000)
    .map((e) => e.tokens);

  // Correlate palette_start -> next 3-record buffer
  const paletteTokens = [];
  for (let i = 0; i < allEvents.length; i++) {
    if (allEvents[i].kind !== 'palette_start') continue;
    const buf = findNextBuffer(allEvents, i, allEvents[i].worker, 60, (r) => r === 3);
    if (buf && buf.tokens <= 10000) paletteTokens.push(buf.tokens);
  }

  // Fallback: all 3-record buffers under 10k
  const paletteTriple = allEvents
    .filter((e) => e.kind === 'token_buffer' && e.records === 3 && e.tokens <= 10000)
    .map((e) => e.tokens);

  const paletteUsed = paletteTokens.length >= 20 ? paletteTokens : paletteTriple;

  // MindMate 10-round: group consecutive mindmate events (gap <= 30 min)
  const mmEvents = allEvents.filter((e) => e.kind === 'mindmate' && e.tokens > 0);
  const mmConversations = [];
  let current = [];
  let lastSec = null;
  for (const e of mmEvents) {
    if (lastSec != null && e.sec - lastSec > 1800) {
      if (current.length >= 10) mmConversations.push([...current]);
      current = [];
    }
    current.push(e.tokens);
    lastSec = e.sec;
  }
  if (current.length >= 10) mmConversations.push(current);

  const mm10Totals = mmConversations.map((c) => c.slice(0, 10).reduce((a, b) => a + b, 0));
  const mm10Clean = filterOutliers(mm10Totals, 300000);

  // Round-by-round from conversations with 10+ rounds
  const roundVals = Array.from({ length: 10 }, () => []);
  for (const conv of mmConversations) {
    for (let r = 0; r < 10 && r < conv.length; r++) {
      if (conv[r] <= 50000) roundVals[r].push(conv[r]);
    }
  }
  const roundStats = roundVals.map((vals, i) => ({ round: i + 1, ...stats(vals) })).filter((r) => r.n);

  const genUsed = genGraphTokens.length >= 30 ? genGraphTokens : diagramLikeBatches;
  const genClean = filterOutliers(genUsed, 15000);
  const paletteClean = filterOutliers(paletteUsed, 10000);

  const genPer = stats(genClean);
  const palPer = stats(paletteClean);
  const mmPer = stats(mindmateClean);
  const mm10 = stats(mm10Clean);

  const mm10ByRoundMedian = roundStats.reduce((s, r) => s + (r.median || 0), 0);

  const report = {
    source: logsDir,
    filesParsed: files.length,
    sampleSizes: {
      mindmateRounds: mindmateClean.length,
      generateGraphHttp: allEvents.filter((e) => e.kind === 'gen_graph').length,
      generateGraphCorrelated: genGraphTokens.length,
      paletteStarts: allEvents.filter((e) => e.kind === 'palette_start').length,
      paletteCorrelated: paletteTokens.length,
      mindmateConversations10Plus: mmConversations.length,
    },
    perUnit: {
      diagramGeneration: genPer,
      nodePaletteClick: palPer,
      mindmateRound: mmPer,
      mindmateRoundByRound: roundStats,
    },
    scenarios: {
      diagram20: {
        median: (genPer?.median || 0) * 20,
        avg: (genPer?.avg || 0) * 20,
        p75: Math.round((pct(genClean, 75) || 0) * 20),
      },
      palette10: {
        median: (palPer?.median || 0) * 10,
        avg: (palPer?.avg || 0) * 10,
        p75: Math.round((pct(paletteClean, 75) || 0) * 10),
      },
      mindmate10: {
        median: mm10?.median || mm10ByRoundMedian,
        avg: mm10?.avg || roundStats.reduce((s, r) => s + (r.avg || 0), 0),
        byRoundMedianSum: mm10ByRoundMedian,
      },
      grandTotal: {
        median:
          (genPer?.median || 0) * 20 +
          (palPer?.median || 0) * 10 +
          (mm10?.median || mm10ByRoundMedian),
        avg:
          (genPer?.avg || 0) * 20 +
          (palPer?.avg || 0) * 10 +
          (mm10?.avg || roundStats.reduce((s, r) => s + (r.avg || 0), 0)),
      },
    },
  };

  console.log(JSON.stringify(report, null, 2));
}

main();
