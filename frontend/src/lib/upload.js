// Upload rules shared by the New package page and its tests.
// Same limits as the backend (backend/app/services.py) so problems show before uploading.

export const ALLOWED = ['.pdf', '.png', '.jpg', '.jpeg']
export const MAX_BYTES = 15 * 1024 * 1024

export const DOC_TYPES = [
  ['', 'Auto-detect'], ['invoice', 'Invoice'], ['po', 'Purchase order'], ['challan', 'Delivery challan / LR'],
  ['eway', 'E-way bill'], ['grn', 'GRN / acceptance'], ['contract', 'Contract / terms'], ['other', 'Other'],
]

/** Returns an error message for a file the backend would reject, else null. */
export function fileProblem(file) {
  const name = file.name.toLowerCase()
  if (!ALLOWED.some((ext) => name.endsWith(ext))) return `${file.name}: unsupported type (use PDF, PNG or JPG).`
  if (file.size === 0) return `${file.name} is empty.`
  if (file.size > MAX_BYTES) return `${file.name} is larger than 15 MB.`
  return null
}
