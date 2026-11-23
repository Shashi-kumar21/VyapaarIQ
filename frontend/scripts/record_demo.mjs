// Backup screen recording of docs/demo_script.md: a captioned, silent video of the whole flow.
// Manual, not part of `npm test`. Needs the demo setup from docs/demo_script.md running (fixture,
// today 2026-11-23, fresh DB + seed, PKG01 and PKG20 already uploaded) and Playwright:
//
//   cd frontend; npm i --no-save playwright; npx playwright install chromium
//   node scripts/record_demo.mjs        # REC_OUT=<folder> to choose where the .webm goes
//
// Never write the video into the repo (keep it next to the slides, outside git).
import { chromium } from 'playwright'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const UI = process.env.UI_URL || 'http://localhost:5173'
const API = process.env.API_URL || 'http://localhost:8000/api'
const OUT = process.env.REC_OUT || path.join(os.tmpdir(), 'vyapaariq-recording')
const PKG = process.env.PKG_DIR || path.resolve(HERE, '../../samples/out')
const REPORT = process.env.REPORT || path.resolve(HERE, '../../eval/report.md')
fs.mkdirSync(OUT, { recursive: true })
const W = 1366, H = 768
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

const OVERLAY = () => {
  const mk = () => {
    if (document.getElementById('rec-cap')) return
    const cap = document.createElement('div')
    cap.id = 'rec-cap'
    Object.assign(cap.style, { position: 'fixed', left: '50%', bottom: '18px', transform: 'translateX(-50%)', maxWidth: '1100px',
      background: 'rgba(15,23,42,.88)', color: '#fff', font: '500 17px/1.45 system-ui, sans-serif', padding: '10px 18px',
      borderRadius: '10px', zIndex: 99999, pointerEvents: 'none', textAlign: 'center', display: 'none' })
    const cur = document.createElement('div')
    cur.id = 'rec-cur'
    Object.assign(cur.style, { position: 'fixed', width: '18px', height: '18px', borderRadius: '50%', background: 'rgba(239,68,68,.55)',
      border: '2px solid #b91c1c', zIndex: 100000, pointerEvents: 'none', left: '-40px', top: '-40px', transform: 'translate(-50%,-50%)',
      transition: 'transform .12s' })
    document.body.append(cap, cur)
    document.addEventListener('mousemove', (e) => { cur.style.left = e.clientX + 'px'; cur.style.top = e.clientY + 'px' }, true)
    document.addEventListener('mousedown', () => { cur.style.transform = 'translate(-50%,-50%) scale(1.6)' }, true)
    document.addEventListener('mouseup', () => { cur.style.transform = 'translate(-50%,-50%)' }, true)
    let saved = null
    try { saved = sessionStorage.getItem('rec-cap-text') } catch { /* no storage on about:blank */ }
    if (saved) { cap.textContent = saved; cap.style.display = 'block' }
  }
  if (document.body) mk(); else document.addEventListener('DOMContentLoaded', mk)
}

async function main() {
  // The captions quote the script's numbers, so refuse any other setup (same guard as ui_runthrough).
  const health = await (await fetch(`${API}/health`)).json()
  if (health.extractor !== 'fixture' || health.today !== '2026-11-23') {
    console.error('Use the demo setup (EXTRACTOR=fixture, VYAPAARIQ_TODAY=2026-11-23):', health)
    process.exit(2)
  }
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, recordVideo: { dir: OUT, size: { width: W, height: H } },
    acceptDownloads: true })
  await ctx.addInitScript(OVERLAY)
  const page = await ctx.newPage()
  const caption = async (text) => {
    await page.evaluate((t) => {
      try { sessionStorage.setItem('rec-cap-text', t) } catch { /* no storage on about:blank */ }
      const c = document.getElementById('rec-cap'); if (c) { c.textContent = t; c.style.display = t ? 'block' : 'none' }
    }, text)
  }
  const moveTo = async (loc) => {
    await loc.scrollIntoViewIfNeeded()
    const b = await loc.boundingBox()
    if (b) await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 25 })
    await wait(300)
  }
  const click = async (loc) => { await moveTo(loc); await loc.click(); await wait(500) }
  const scroll = async (dy, steps = 8) => { for (let i = 0; i < steps; i++) { await page.mouse.wheel(0, dy / steps); await wait(60) } }

  // 0:00 Dashboard
  await page.goto(UI); await page.getByText('Top actions due').waitFor()
  await caption('VyapaarIQ: MSME suppliers sell on credit and wait. When a buyer stalls, the supplier must prove order, delivery and acceptance.')
  await wait(5000)
  await moveTo(page.getByRole('note').first())
  await caption('Demo with synthetic data only. Risk is illustrative; legal figures are estimates, not legal advice.')
  await wait(5000)

  // 0:30 New package -> PKG07
  await click(page.getByRole('link', { name: 'New package' }))
  await caption("One invoice's paperwork: invoice, PO and delivery challan. Notice there is no GRN.")
  const files = fs.readdirSync(path.join(PKG, 'PKG07')).filter((f) => f.endsWith('.pdf')).map((f) => path.join(PKG, 'PKG07', f))
  await page.setInputFiles('[data-testid="file-input"]', files)
  await wait(4000)
  await click(page.getByText('Process package'))
  await page.waitForURL('**/invoices/*'); await page.locator('[data-check]').first().waitFor()
  await caption('VyapaarIQ reads each document and cross-checks them: PO matched, challan matched, but the GRN link is missing.')
  await wait(3500)
  await click(page.locator('[data-edge="grn"]'))
  await caption('No GRN or written acceptance from the buyer: acceptance can only be deemed, which weakens the payment claim.')
  await wait(5500)

  await scroll(-2000, 4)
  await moveTo(page.getByText('Readiness').first())
  await caption('Readiness is 70, Medium, and every point lost is listed.')
  await wait(2500)
  await click(page.getByRole('tab', { name: 'Actions & score' }))
  await moveTo(page.getByText(/C10 missing \(blocker\)/))
  await caption('C10 missing (blocker): −30. First action: request the GRN or acceptance from the buyer. The payment is already overdue since 13 Oct 2026.')
  await wait(6000)

  // 1:30 Due date + interest
  await scroll(-2000, 4)
  await click(page.getByText('How the due date and interest were worked out'))
  await caption('Statutory due date 13 Oct 2026 (estimated): challan received date + 30 days of written terms. Interest to today ≈ ₹452 at 3 × the 5.75% bank rate, formula shown. Not legal advice.')
  await wait(8000)

  // Follow-ups
  await click(page.getByRole('tab', { name: 'Follow-ups' }))
  await caption('Follow-up drafts for D−7 through D+25, friendly or firm. They are drafts: never sent by the app.')
  await click(page.getByText('Generate drafts'))
  await page.locator('[data-step="D+25"]').waitFor()
  await wait(2000)
  await click(page.getByRole('radio', { name: 'Firm' }))
  await click(page.getByText('Generate drafts'))
  const d10 = page.locator('[data-step="D+10"]')
  await d10.waitFor(); await moveTo(d10)
  await caption('The firm D+10 draft cites the 45-day limit for micro and small suppliers.')
  await wait(5000)
  const copy = d10.getByRole('button', { name: /Copy body/ })
  if (await copy.count()) await click(copy)
  await wait(1500)

  // Dispute pack
  await scroll(-3000, 4)
  await click(page.getByRole('tab', { name: 'Dispute pack' }))
  await page.locator('[aria-label="Pack preview"] h3').first().waitFor()
  await caption('A dispute-ready evidence pack: timeline, document index, checks, due date, interest and missing evidence.')
  const prev = page.locator('[aria-label="Pack preview"]')
  await moveTo(prev)
  for (let i = 0; i < 6; i++) { await prev.evaluate((el) => el.scrollBy({ top: 220, behavior: 'smooth' })); await wait(800) }
  const [dl] = await Promise.all([page.waitForEvent('download'), click(page.getByText('Download PDF'))])
  await dl.saveAs(path.join(OUT, dl.suggestedFilename()))
  await caption('Download as PDF (Markdown fallback if the PDF cannot be built).')
  await wait(3000)

  // 2:15 Dashboard
  await click(page.getByRole('link', { name: 'Dashboard' }))
  await page.getByText('Top actions due').waitFor()
  await caption('Across all open invoices: cash at risk in the next 30 and 60 days, and the top actions to work on first.')
  await moveTo(page.getByText(/Cash at risk · 30 days/))
  await wait(3000)
  await moveTo(page.locator('[data-bucket="overdue"]'))
  await wait(3500)
  await moveTo(page.getByText('Top actions due'))
  await wait(3500)

  // Buyers
  await click(page.getByRole('link', { name: 'Buyers' }))
  await page.getByText('Reliable').first().waitFor()
  await caption("Buyer reliability from this supplier's own history. Seeded demo history, not a credit rating.")
  await moveTo(page.locator('table'))
  await wait(6000)

  // 2:45 Evaluation summary (from eval/report.md)
  const md = fs.readFileSync(REPORT, 'utf8').split('\n')
  const start = md.findIndex((l) => l.startsWith('| ')), rows = []
  for (let i = start; i < md.length && md[i].startsWith('|'); i++) if (!/^\|\s*-/.test(md[i])) rows.push(md[i].split('|').slice(1, -1).map((c) => c.trim()))
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`(.+?)`/g, '<code>$1</code>')
  await page.setContent(`<html><body style="font:15px system-ui;margin:40px 60px;background:#f8fafc;color:#0f172a">
    <h2>eval/report.md: summary (28 synthetic packages)</h2><table style="border-collapse:collapse;background:#fff">
    ${rows.map((r, i) => `<tr>${r.map((c) => `<${i ? 'td' : 'th'} style="border:1px solid #cbd5e1;padding:6px 12px;text-align:left">${esc(c)}</${i ? 'td' : 'th'}>`).join('')}</tr>`).join('')}
    </table></body></html>`)
  await page.evaluate(OVERLAY.toString().replace(/^\(\) => /, '(() => ') + ')()')
  await caption('Measured on 28 synthetic packages: zero confidently wrong fields, 100% precision on defects. Scans need the Claude extractor (not measured yet).')
  await wait(7000)
  await caption('Next: Tally/Zoho sync, WhatsApp sending with consent, and ODR filing support.')
  await wait(5000)

  const video = page.video()
  await ctx.close()
  const src = await video.path()
  const dst = path.join(OUT, 'vyapaariq-demo-backup.webm')
  fs.renameSync(src, dst)
  console.log('video:', dst, Math.round(fs.statSync(dst).size / 1024), 'KB')
  await browser.close()
}
main()
