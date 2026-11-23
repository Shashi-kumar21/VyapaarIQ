// Thin client for the VyapaarIQ API. Contract: docs/api_contract.md.
// Base URL from VITE_API_BASE (see .env.example); defaults to the local backend. Use "/" for a
// build served by the backend itself (same origin, docs/deploy.md).

export const API_BASE = (import.meta.env.VITE_API_BASE || 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

/** Turn `{detail: "..."}` or a FastAPI validation list into one readable message. */
export function errorMessage(body, status) {
  const d = body && body.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((e) => e.msg || JSON.stringify(e)).join('; ')
  return `Request failed (${status}).`
}

async function request(path, { method = 'GET', body, raw = false } = {}) {
  let res
  try {
    res = await fetch(`${API_BASE}/api${path}`, { method, body })
  } catch {
    throw new ApiError(0, `Cannot reach the backend at ${API_BASE || window.location.origin}. Is uvicorn running?`)
  }
  if (!res.ok) {
    let payload = null
    try {
      payload = await res.json()
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, errorMessage(payload, res.status))
  }
  return raw ? res : res.json()
}

/** Blob -> string; uses FileReader where Blob.text() is missing (older engines, jsdom). */
export function blobText(blob) {
  if (typeof blob.text === 'function') return blob.text()
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result)
    r.onerror = () => reject(r.error)
    r.readAsText(blob)
  })
}

function qs(params) {
  const p = new URLSearchParams()
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') p.set(k, v)
  })
  const s = p.toString()
  return s ? `?${s}` : ''
}

export const api = {
  health: () => request('/health'),

  /** files: File[]; docTypes: (string|null)[] same order as files. */
  uploadPackage(files, { buyerName, docTypes } = {}) {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    if (buyerName) form.append('buyer_name', buyerName)
    if (docTypes && docTypes.some((t) => t)) form.append('doc_types', JSON.stringify(docTypes))
    return request('/packages', { method: 'POST', body: form })
  },
  processPackage: (id) => request(`/packages/${id}/process`, { method: 'POST' }),
  getPackage: (id) => request(`/packages/${id}`),

  listInvoices: (filters) => request(`/invoices${qs(filters)}`),
  getInvoice: (id) => request(`/invoices/${id}`),
  getGraph: (id) => request(`/invoices/${id}/graph`),
  topActions: (limit = 5) => request(`/actions${qs({ limit })}`),

  generateFollowups: (id, { tone = 'friendly', channel = 'email' } = {}) =>
    request(`/invoices/${id}/followups/generate${qs({ tone, channel })}`, { method: 'POST' }),
  listFollowups: (id, filters) => request(`/invoices/${id}/followups${qs(filters)}`),
  /** URL of the dispute pack (PDF by default, or format="md"). */
  disputePackUrl: (id, format = 'pdf') => `${API_BASE}/api/invoices/${id}/dispute-pack${qs({ format })}`,
  /**
   * Fetch the dispute pack as {blob, filename, format}. Errors (404/409) become ApiError with the
   * backend message instead of a raw JSON page. format: what the server actually sent
   * ("pdf", "md" or "md-fallback" when the PDF render failed).
   */
  async disputePack(id, format = 'pdf') {
    const res = await request(`/invoices/${id}/dispute-pack${qs({ format })}`, { raw: true })
    const cd = res.headers.get('content-disposition') || ''
    const filename = (/filename="([^"]+)"/.exec(cd) || [])[1] || `evidence-pack-${id}.${format}`
    return { blob: await res.blob(), filename, format: res.headers.get('x-pack-format') || format }
  },

  listBuyers: () => request('/buyers'),
  buyerProfile: (id) => request(`/buyers/${id}/profile`),
  forecast: (days = 30) => request(`/forecast${qs({ days })}`),
}
