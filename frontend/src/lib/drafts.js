// Follow-up draft text = reviewer notes in [brackets] at the top, then the message itself.
// The notes ("[DRAFT…]", "[VERIFY…]", "[Scheduled…]") are for the user, never for the buyer.

/** Split a draft into {notes: string[] (without brackets), body: string}. */
export function splitDraft(text) {
  const lines = (text || '').split('\n')
  let i = 0
  while (i < lines.length && /^\[.*\]$/.test(lines[i])) i += 1
  return {
    notes: lines.slice(0, i).map((n) => n.slice(1, -1)),
    body: lines.slice(i).join('\n').replace(/^\n+/, ''),
  }
}

/** Email message -> {subject, body}; subject is null when the message has no "Subject:" line. */
export function splitEmail(message) {
  const m = /^Subject: (.*)\n\n?([\s\S]*)$/.exec(message || '')
  return m ? { subject: m[1], body: m[2] } : { subject: null, body: message || '' }
}
