import { afterEach, describe, expect, it, vi } from 'vitest'
import { API_BASE, ApiError, api, blobText, errorMessage } from './api.js'

afterEach(() => vi.unstubAllGlobals())

describe('errorMessage', () => {
  it('reads the string detail and FastAPI validation lists', () => {
    expect(errorMessage({ detail: 'Invoice not found.' }, 404)).toBe('Invoice not found.')
    expect(errorMessage({ detail: [{ msg: 'bad tone' }, { msg: 'bad channel' }] }, 422)).toBe('bad tone; bad channel')
    expect(errorMessage(null, 500)).toBe('Request failed (500).')
  })
})

describe('api client', () => {
  it('builds URLs with query params and returns JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ days: 60 }) })
    vi.stubGlobal('fetch', fetchMock)
    expect(await api.forecast(60)).toEqual({ days: 60 })
    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/api/forecast?days=60`, { method: 'GET', body: undefined })
    await api.listInvoices({ tier: 'High', buyer_id: null })
    expect(fetchMock.mock.calls[1][0]).toBe(`${API_BASE}/api/invoices?tier=High`)
  })

  it('throws ApiError with the backend message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 404, json: async () => ({ detail: 'Invoice not found.' }),
    }))
    await expect(api.getInvoice(999)).rejects.toMatchObject({ status: 404, message: 'Invoice not found.' })
  })

  it('reports an unreachable backend clearly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const err = await api.health().catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(0)
    expect(err.message).toMatch(/Cannot reach the backend/)
  })

  it('fetches the dispute pack as a blob with the server filename and format', async () => {
    const headers = new Map([
      ['content-disposition', 'attachment; filename="evidence-pack-SPC-26-27-0107.md"'],
      ['x-pack-format', 'md-fallback'],
    ])
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, headers: { get: (k) => headers.get(k) ?? null }, blob: async () => new Blob(['# pack']),
    }))
    const pack = await api.disputePack(61, 'pdf')
    expect(pack.filename).toBe('evidence-pack-SPC-26-27-0107.md')
    expect(pack.format).toBe('md-fallback')
    expect(await blobText(pack.blob)).toBe('# pack')
  })

  it('turns a dispute-pack 409 into a readable error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 409, json: async () => ({ detail: 'Invoice has not been processed yet.' }),
    }))
    await expect(api.disputePack(5)).rejects.toMatchObject({ status: 409, message: 'Invoice has not been processed yet.' })
  })

  it('sends doc_types only when at least one type is chosen', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 1 }) })
    vi.stubGlobal('fetch', fetchMock)
    const f = new File(['%PDF'], 'a.pdf')
    await api.uploadPackage([f], { docTypes: [null] })
    expect(fetchMock.mock.calls[0][1].body.has('doc_types')).toBe(false)
    await api.uploadPackage([f], { docTypes: ['invoice'], buyerName: 'Kaveri' })
    const body = fetchMock.mock.calls[1][1].body
    expect(body.get('doc_types')).toBe('["invoice"]')
    expect(body.get('buyer_name')).toBe('Kaveri')
  })
})
