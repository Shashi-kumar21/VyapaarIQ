// T4.13 manual UI run-through (see docs/bugs.md). Not part of `npm test`: it needs the demo
// servers running and Playwright installed.
//
//   # terminal 1, repo root: demo setup from docs/demo_script.md (fixture extractor, today
//   #   2026-11-23, fresh DB + seed), then uvicorn on :8000
//   # terminal 2: cd frontend; npm run dev
//   # terminal 3:
//   cd frontend; npm i --no-save playwright; npx playwright install chromium
//   node scripts/ui_runthrough.mjs            # ONLY=PKG07,PKG27 to run a subset
//
// It uploads every package through the New package page in order (so C14 duplicates work),
// compares checks / due date / basis with samples/ground_truth.json, opens all five tabs,
// generates drafts, downloads the dispute-pack PDF, then screenshots Dashboard and Buyers at
// desktop and phone width. Screenshots + results.json go to RT_OUT (default: OS temp dir).
// Exit code 1 if any package has an issue.
import { chromium } from 'playwright'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const UI = process.env.UI_URL || 'http://localhost:5173'
const API = process.env.API_URL || 'http://localhost:8000/api'
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../samples')
const OUT = process.env.RT_OUT || path.join(os.tmpdir(), 'vyapaariq-runthrough')
fs.mkdirSync(OUT, { recursive: true })
const GT = JSON.parse(fs.readFileSync(path.join(ROOT, 'ground_truth.json'), 'utf8'))
const ONLY = process.env.ONLY ? process.env.ONLY.split(',') : null

async function main() {
  for (let i = 0; i < 60; i++) {
    try { const [a, b] = await Promise.all([fetch(`${API}/health`), fetch(UI)]); if (a.ok && b.ok) break } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  const health = await (await fetch(`${API}/health`)).json()
  if (health.extractor !== 'fixture' || health.today !== '2026-11-23') {
    console.error('Use the demo setup (EXTRACTOR=fixture, VYAPAARIQ_TODAY=2026-11-23):', health)
    process.exit(2)
  }
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 }, acceptDownloads: true });
  const page = await ctx.newPage();
  const results = [];
  let errors = [];
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  page.on('pageerror', (e) => errors.push(e.message));

  for (const pkg of GT.packages) {
    if (ONLY && !ONLY.includes(pkg.package_id)) continue;
    errors = [];
    const r = { pkg: pkg.package_id, defects: pkg.defects, issues: [] };
    try {
      await page.goto(`${UI}/packages/new`);
      const dir = path.join(ROOT, 'out', pkg.package_id);
      await page.setInputFiles('[data-testid="file-input"]', fs.readdirSync(dir).filter((f) => f.endsWith('.pdf')).map((f) => path.join(dir, f)));
      await page.getByText('Process package').click();
      await page.waitForURL('**/invoices/*', { timeout: 60000 });
      const id = page.url().split('/').pop();
      r.id = id;
      const inv = await (await fetch(`${API}/invoices/${id}`)).json();
      const a = inv.analysis;
      const exp = pkg.expected;
      // checks vs ground truth
      const got = Object.fromEntries(a.checks.map((c) => [c.check_id, c.status]));
      for (const [k, v] of Object.entries(exp.checks)) if (got[k] !== v) r.issues.push(`${k}: expected ${v}, got ${got[k]}`);
      if (a.due.due_date !== exp.due_date) r.issues.push(`due: expected ${exp.due_date}, got ${a.due.due_date}`);
      if (a.due.acceptance_basis !== exp.acceptance_basis) r.issues.push(`basis: expected ${exp.acceptance_basis}, got ${a.due.acceptance_basis}`);
      r.score = a.score?.score ?? inv.readiness_score; r.tier = inv.risk_tier; r.due = a.due.due_date;
      r.interest = a.interest.computable ? a.interest.interest : a.interest.reason || 'n/a';

      // UI: Checks tab rows agree with API
      await page.locator('[data-check]').first().waitFor({ timeout: 10000 })
      const uiRows = await page.locator('[data-check]').evaluateAll((els) => els.map((e) => [e.dataset.check, e.innerText]));
      if (uiRows.length !== a.checks.length) r.issues.push(`UI shows ${uiRows.length} checks, API ${a.checks.length}`);
      r.attention = await page.getByText(/checks need attention/).textContent();
      // graph rendered
      if ((await page.locator('[data-node]').count()) === 0) r.issues.push('evidence graph empty');
      await page.screenshot({ path: `${OUT}/${pkg.package_id}-checks.png`, fullPage: true });

      for (const tab of ['Actions & score', 'Documents', 'Follow-ups', 'Dispute pack']) {
        await page.getByRole('tab', { name: tab }).click();
        await page.waitForTimeout(300);
        if (tab === 'Follow-ups') {
          await page.getByText('Generate drafts').click();
          await page.locator('[data-step]').first().waitFor({ timeout: 10000 });
          r.drafts = await page.locator('[data-step]').count();
        }
        if (tab === 'Dispute pack') {
          await page.locator('[aria-label="Pack preview"] h3').first().waitFor({ timeout: 10000 });
          const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 15000 }), page.getByText('Download PDF').click()]);
          const f = `${OUT}/${dl.suggestedFilename()}`;
          await dl.saveAs(f);
          const head = fs.readFileSync(f).slice(0, 4).toString();
          if (head !== '%PDF') r.issues.push(`pack download is not a PDF (${dl.suggestedFilename()})`);
          r.pack = dl.suggestedFilename();
        }
        if (await page.getByRole('alert').count()) r.issues.push(`${tab}: error box: ${await page.getByRole('alert').first().innerText()}`);
        await page.screenshot({ path: `${OUT}/${pkg.package_id}-${tab.split(' ')[0].toLowerCase()}.png`, fullPage: true });
      }
    } catch (e) {
      r.issues.push(`FAILED: ${e.message.split('\n')[0]}`);
      await page.screenshot({ path: `${OUT}/${pkg.package_id}-failure.png`, fullPage: true });
    }
    if (errors.length) r.issues.push(`console: ${errors.join(' | ')}`);
    results.push(r);
    console.log(r.pkg, r.defects.join('+') || 'clean', `score ${r.score} ${r.tier} due ${r.due} int ${r.interest} drafts ${r.drafts}`, r.issues.length ? `ISSUES: ${r.issues.join('; ')}` : 'OK');
  }

  // dashboard + buyers, desktop and phone
  errors = [];
  for (const [name, url, wait] of [['dashboard', UI, 'Top actions due'], ['buyers', `${UI}/buyers`, 'Reliable']]) {
    for (const [vw, w, h] of [['desktop', 1366, 900], ['phone', 375, 800]]) {
      await page.setViewportSize({ width: w, height: h });
      await page.goto(url);
      await page.getByText(wait).first().waitFor();
      await page.waitForTimeout(500);
      await page.screenshot({ path: `${OUT}/${name}-${vw}.png`, fullPage: true });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      console.log(name, vw, 'horizontal overflow px:', overflow);
    }
  }
  const stats = await (await fetch(`${API}/forecast?days=30`)).json();
  console.log('forecast totals', JSON.stringify(stats.totals));
  console.log('dashboard console errors:', errors.length ? errors : 'none');
  fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 1));
  await browser.close();
  const bad = results.filter((r) => r.issues.length)
  console.log(`${results.length - bad.length}/${results.length} packages OK; output in ${OUT}`)
  process.exitCode = bad.length ? 1 : 0
}

main()
