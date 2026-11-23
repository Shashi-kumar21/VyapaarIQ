import { date, inr, pct } from '../lib/format.js'

// Extracted fields per document (task T2.15). Every field shows value, confidence and page.
// Below the configured threshold (health.uncertain_below) the row is amber: "needs human check".

const DOC_LABEL = {
  invoice: 'Tax invoice', po: 'Purchase order', challan: 'Delivery challan / LR', eway: 'E-way bill',
  grn: 'GRN / acceptance', contract: 'Contract / terms', other: 'Other document',
}
const META = new Set(['doc_type', 'filename', 'page_count', 'extractor', 'fallback'])
const AMOUNTS = new Set(['taxable_value', 'cgst', 'sgst', 'igst', 'total', 'po_total', 'value'])

function label(key) {
  return key.replace(/_/g, ' ').replace(/\bno\b/, 'no.').replace(/^\w/, (c) => c.toUpperCase())
}

function show(key, value) {
  if (value === null || value === undefined) return <span className="text-slate-400">not found</span>
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (AMOUNTS.has(key)) return inr(value, { paise: true })
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) return date(value)
  if (Array.isArray(value)) {
    return (
      <table className="text-xs mt-1">
        <tbody>
          {value.map((it, i) => (
            <tr key={i}>
              <td className="pr-3">{it.desc || '—'}</td>
              {['qty', 'qty_received', 'qty_accepted'].filter((k) => it[k] != null).map((k) => (
                <td key={k} className="pr-3 text-slate-600">{k.replace('_', ' ')} {it[k]}</td>
              ))}
              {it.rate != null && <td className="pr-3 text-slate-600">@ {inr(it.rate, { paise: true })}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    )
  }
  return String(value)
}

function isUnsure(field, threshold) {
  return !!field && typeof field === 'object' && (field.confidence ?? 0) < threshold
}

export default function DocumentFields({ documents, threshold }) {
  if (!documents?.length) return <p className="text-sm text-slate-500">No documents.</p>
  return (
    <div className="space-y-4">
      {documents.map((d) => {
        const fields = Object.entries(d.fields || {}).filter(([k, v]) => !META.has(k) && v && typeof v === 'object')
        const unsure = fields.filter(([, f]) => isUnsure(f, threshold)).length
        return (
          <section key={d.id} className="border border-slate-200 rounded-lg bg-white">
            <header className="flex flex-wrap items-center gap-2 px-3 py-2 border-b border-slate-100 text-sm">
              <b>{DOC_LABEL[d.doc_type] || d.doc_type}</b>
              <span className="text-slate-500 truncate max-w-64" title={d.filename}>{d.filename}</span>
              {d.extractor && <span className="text-xs text-slate-500">· {d.extractor} · conf {pct(d.extraction_conf)}</span>}
              {d.fallback && (
                <span className="px-2 py-0.5 rounded-full text-xs bg-purple-100 text-purple-800">demo fallback</span>
              )}
              {unsure > 0 && (
                <span className="px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-900">
                  {unsure} field(s) need human check
                </span>
              )}
            </header>
            {d.error ? (
              <p className="px-3 py-2 text-sm text-red-700">{d.error}</p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {fields.map(([k, f]) => {
                    const amber = isUnsure(f, threshold)
                    return (
                      <tr key={k} className={`border-b border-slate-50 last:border-0 align-top ${amber ? 'bg-amber-50' : ''}`}
                          data-unsure={amber || undefined}>
                        <td className="px-3 py-1.5 text-slate-500 w-48">{label(k)}</td>
                        <td className="py-1.5">{show(k, f.value)}</td>
                        <td className={`px-3 py-1.5 text-right whitespace-nowrap text-xs ${amber ? 'text-amber-800 font-medium' : 'text-slate-400'}`}>
                          {amber ? `needs human check · ${pct(f.confidence)}` : pct(f.confidence)}
                          {f.source_page ? ` · p${f.source_page}` : ''}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </section>
        )
      })}
    </div>
  )
}
