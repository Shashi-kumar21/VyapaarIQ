import { useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { Card } from '../components/ui.jsx'
import { api } from '../lib/api.js'
import { ALLOWED, DOC_TYPES, fileProblem } from '../lib/upload.js'

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
    <section className="space-y-4 max-w-3xl">
      <h1 className="text-2xl font-semibold">New package</h1>
      <p className="text-sm text-slate-600">
        Add every document for one invoice: invoice, PO, delivery challan / LR, e-way bill, GRN and any
        contract. The type of each file is detected automatically; change it if it is wrong.
      </p>

      <div
        role="button"
        tabIndex={0}
        aria-label="Drop files here or click to choose"
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && !busy && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); if (!busy) addFiles(e.dataTransfer.files) }}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition ${
          dragging ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-white hover:bg-slate-50'}`}
      >
        <p className="font-medium">Drop PDF / PNG / JPG files here</p>
        <p className="text-xs text-slate-500 mt-1">or click to choose · max 15 MB each</p>
        <input
          ref={inputRef} type="file" multiple accept={ALLOWED.join(',')} className="hidden"
          data-testid="file-input" onChange={(e) => { addFiles(e.target.files); e.target.value = '' }}
        />
      </div>

      {problems.length > 0 && (
        <ul role="alert" className="text-sm text-red-700 list-disc pl-5">
          {problems.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}

      {items.length > 0 && (
        <Card title={`Files (${items.length})`}>
          <ul className="divide-y divide-slate-100">
            {items.map((it, idx) => (
              <li key={`${it.file.name}-${idx}`} className="py-2 flex flex-wrap items-center gap-3 text-sm">
                <span className="flex-1 min-w-40 truncate" title={it.file.name}>{it.file.name}</span>
                <span className="text-xs text-slate-500">{Math.max(1, Math.round(it.file.size / 1024))} KB</span>
                <select
                  aria-label={`Document type for ${it.file.name}`}
                  value={it.docType}
                  disabled={busy}
                  onChange={(e) => { setUploadedId(null); setItems((cur) => cur.map((c, j) => (j === idx ? { ...c, docType: e.target.value } : c))) }}
                  className="border border-slate-300 rounded-md px-2 py-1"
                >
                  {DOC_TYPES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
                </select>
                <button
                  type="button" disabled={busy} aria-label={`Remove ${it.file.name}`}
                  onClick={() => { setUploadedId(null); setItems((cur) => cur.filter((_, j) => j !== idx)) }}
                  className="text-slate-500 hover:text-red-700 px-2"
                >✕</button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <label className="block text-sm">
        <span className="text-slate-700">Buyer name (optional)</span>
        <input
          value={buyerName} disabled={busy} onChange={(e) => { setUploadedId(null); setBuyerName(e.target.value) }}
          placeholder="Used only if the buyer cannot be read reliably from the invoice"
          className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2"
        />
      </label>

      <div className="flex items-center gap-4">
        <button
          type="button" onClick={process} disabled={busy || items.length === 0}
          className="px-4 py-2 rounded-md bg-slate-900 text-white disabled:opacity-40"
        >
          {busy ? 'Processing…' : uploadedId !== null ? 'Retry processing' : 'Process package'}
        </button>
        {stage && stage !== 'failed' && (
          <span role="status" className="text-sm text-slate-600">{STAGES[stage]}</span>
        )}
      </div>

      {error && (
        <div role="alert" className="border border-red-200 bg-red-50 text-red-800 rounded-lg p-3 text-sm">
          {error}
        </div>
      )}
    </section>
  )
}
