import { FileText, Loader2, Play, RotateCcw, UploadCloud, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { Card, PageHeader } from '../components/ui.jsx'
import { api } from '../lib/api.js'
import { ALLOWED, DOC_TYPES, fileProblem } from '../lib/upload.js'
import { btn } from '../lib/styles.js'

const STAGES = {
  uploading: 'Uploading files…',
  processing: 'Extracting fields and running checks…',
  done: 'Done. Opening the invoice…',
}

/** New package (BUILD_SPEC §13.2): drag-and-drop, per-file doc type, Process with progress. */
export default function NewPackage() {
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const [items, setItems] = useState([]) // {file, docType}
  const [buyerName, setBuyerName] = useState('')
  const [problems, setProblems] = useState([])
  const [stage, setStage] = useState(null) // uploading | processing | done | failed
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  // Package already uploaded for the current inputs. A retry after a failed /process re-runs only
  // /process; re-uploading would create a second invoice that C14 flags as a duplicate.
  const [uploadedId, setUploadedId] = useState(null)
  const busy = stage === 'uploading' || stage === 'processing' || stage === 'done'

  function addFiles(list) {
    const files = Array.from(list || [])
    const bad = files.map(fileProblem).filter(Boolean)
    const good = files.filter((f) => !fileProblem(f))
    setProblems(bad)
    if (good.length) setUploadedId(null)
    setItems((cur) => [
      ...cur,
      ...good.filter((f) => !cur.some((c) => c.file.name === f.name && c.file.size === f.size))
        .map((file) => ({ file, docType: '' })),
    ])
  }

  async function process() {
    setError(null)
    let pkgId = uploadedId
    try {
      if (pkgId === null) {
        setStage('uploading')
        const pkg = await api.uploadPackage(items.map((i) => i.file), {
          buyerName: buyerName.trim() || undefined,
          docTypes: items.map((i) => i.docType || null),
        })
        pkgId = pkg.id
        setUploadedId(pkgId)
      }
      setStage('processing')
      const res = await api.processPackage(pkgId)
      setStage('done')
      navigate(`/invoices/${res.invoice_id}`)
    } catch (e) {
      setStage('failed')
      setError(pkgId !== null
        ? `Package #${pkgId} was uploaded but processing failed: ${e.message} Retrying re-runs processing only.`
        : e.message)
    }
  }

  return (
    <section className="max-w-3xl space-y-5">
      <PageHeader title="New package" tool="upload">
        Add every document for one invoice: invoice, PO, delivery challan / LR, e-way bill, GRN and any
        contract. The type of each file is detected automatically; change it if it is wrong.
      </PageHeader>

      <div
        role="button"
        tabIndex={0}
        aria-label="Drop files here or click to choose"
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && !busy && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); if (!busy) addFiles(e.dataTransfer.files) }}
        className={`flex cursor-pointer flex-col items-center rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${
          dragging ? 'border-accent bg-accent-soft' : 'border-line bg-surface hover:border-accent/50 hover:bg-paper'}`}
      >
        <span className="flex size-12 items-center justify-center rounded-full bg-accent-soft text-accent">
          <UploadCloud aria-hidden="true" className="size-6" />
        </span>
        <p className="mt-3 font-display font-semibold text-ink">Drop PDF / PNG / JPG files here</p>
        <p className="mt-1 text-xs text-muted">or click to choose · max 15 MB each</p>
        <input
          ref={inputRef} type="file" multiple accept={ALLOWED.join(',')} className="hidden"
          data-testid="file-input" onChange={(e) => { addFiles(e.target.files); e.target.value = '' }}
        />
      </div>

      {problems.length > 0 && (
        <ul role="alert" className="list-disc rounded-xl border border-red-200 bg-red-50 py-2 pl-8 pr-4 text-sm text-red-800">
          {problems.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}

      {items.length > 0 && (
        <Card title={`Files (${items.length})`}>
          <ul className="divide-y divide-line">
            {items.map((it, idx) => (
              <li key={`${it.file.name}-${idx}`} className="flex flex-wrap items-center gap-3 py-2.5 text-sm">
                <FileText aria-hidden="true" className="size-4 shrink-0 text-muted" />
                <span className="min-w-40 flex-1 truncate" title={it.file.name}>{it.file.name}</span>
                <span className="text-xs tabular-nums text-muted">{Math.max(1, Math.round(it.file.size / 1024))} KB</span>
                <select
                  aria-label={`Document type for ${it.file.name}`}
                  value={it.docType}
                  disabled={busy}
                  onChange={(e) => { setUploadedId(null); setItems((cur) => cur.map((c, j) => (j === idx ? { ...c, docType: e.target.value } : c))) }}
                  className="rounded-lg border border-line bg-surface px-2 py-1.5"
                >
                  {DOC_TYPES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
                </select>
                <button
                  type="button" disabled={busy} aria-label={`Remove ${it.file.name}`}
                  onClick={() => { setUploadedId(null); setItems((cur) => cur.filter((_, j) => j !== idx)) }}
                  className="rounded-md p-1.5 text-muted hover:bg-red-50 hover:text-bad"
                ><X aria-hidden="true" className="size-4" /></button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <label className="block text-sm">
        <span className="font-medium text-ink">Buyer name (optional)</span>
        <input
          value={buyerName} disabled={busy} onChange={(e) => { setUploadedId(null); setBuyerName(e.target.value) }}
          placeholder="Used only if the buyer cannot be read reliably from the invoice"
          className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 placeholder:text-muted/70"
        />
      </label>

      <div className="flex items-center gap-4">
        <button
          type="button" onClick={process} disabled={busy || items.length === 0}
          className={btn.primary}
        >
          {busy ? <Loader2 aria-hidden="true" className="size-4 animate-spin" />
            : uploadedId !== null ? <RotateCcw aria-hidden="true" className="size-4" /> : <Play aria-hidden="true" className="size-4" />}
          {busy ? 'Processing…' : uploadedId !== null ? 'Retry processing' : 'Process package'}
        </button>
        {stage && stage !== 'failed' && (
          <span role="status" className="text-sm text-muted">{STAGES[stage]}</span>
        )}
      </div>

      {error && (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}
    </section>
  )
}
