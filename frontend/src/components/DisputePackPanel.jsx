import { useState } from 'react'
import { api, blobText } from '../lib/api.js'
import { parseMarkdown } from '../lib/markdown.js'
import { useApi } from '../lib/useApi.js'
import { ErrorBox, Loading } from './ui.jsx'

// Dispute evidence pack tab (BUILD_SPEC §11, task T4.10): preview + download.
// Downloads go through fetch, so a 409/404 shows a readable message instead of a raw JSON page.

async function loadPreview(id) {
  const pack = await api.disputePack(id, 'md')
  return parseMarkdown(await blobText(pack.blob))
}

function Block({ b }) {
  switch (b.type) {
    case 'h1': return <h2 className="text-xl font-semibold">{b.text}</h2>
    case 'h2': return <h3 className="font-semibold mt-4 mb-1">{b.text}</h3>
    case 'em': return <p className="text-sm italic text-slate-500">{b.text}</p>
    case 'hr': return <hr className="my-3 border-slate-200" />
    case 'table':
      return (
        <div className="overflow-x-auto">
          <table className="text-xs w-full border border-slate-200 my-1">
            <thead className="bg-slate-50">
              <tr>{b.head.map((h, i) => <th key={i} className="text-left px-2 py-1 border-b border-slate-200">{h}</th>)}</tr>
            </thead>
            <tbody>
              {b.rows.map((r, i) => (
                <tr key={i} className="border-b border-slate-100 last:border-0 align-top">
                  {r.map((c, j) => (
                    <td key={j} className={`px-2 py-1 ${c.includes('[to be verified]') ? 'text-amber-800 bg-amber-50' : ''}`}>{c}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    default: return <p className="text-sm">{b.text}</p>
  }
}

export default function DisputePackPanel({ invoiceId }) {
  const preview = useApi(() => loadPreview(invoiceId), [invoiceId])
  const [busy, setBusy] = useState(null)
  const [dlError, setDlError] = useState(null)
  const [notice, setNotice] = useState(null)

  async function download(format) {
    setBusy(format)
    setDlError(null)
    setNotice(null)
    try {
      const pack = await api.disputePack(invoiceId, format)
      const url = URL.createObjectURL(pack.blob)
      const a = document.createElement('a')
      a.href = url
      a.download = pack.filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      if (pack.format === 'md-fallback') setNotice('The PDF could not be generated, so the Markdown version was downloaded instead.')
    } catch (e) {
      setDlError(e)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => download('pdf')} disabled={!!busy}
                className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-40">
          {busy === 'pdf' ? 'Preparing…' : 'Download PDF'}
        </button>
        <button type="button" onClick={() => download('md')} disabled={!!busy}
                className="px-3 py-1.5 rounded-md border border-slate-300 text-sm disabled:opacity-40">
          {busy === 'md' ? 'Preparing…' : 'Download Markdown'}
        </button>
        <span className="text-xs text-slate-500">
          For a delayed-payment reference (MSME ODR portal; verify the current process). Not legal advice.
        </span>
      </div>
      {notice && <p role="status" className="text-sm text-amber-800 bg-amber-50 rounded p-2">{notice}</p>}
      {dlError && <ErrorBox error={dlError} />}

      <div className="border border-slate-200 rounded-lg p-4 bg-white max-h-[36rem] overflow-y-auto" aria-label="Pack preview">
        {preview.loading && <Loading label="Building preview…" />}
        {preview.error && <ErrorBox error={preview.error} onRetry={preview.reload} />}
        {preview.data && preview.data.map((b, i) => <Block key={i} b={b} />)}
      </div>
    </div>
  )
}
