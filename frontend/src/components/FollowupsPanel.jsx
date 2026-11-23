import { useState } from 'react'
import { api } from '../lib/api.js'
import { splitDraft, splitEmail } from '../lib/drafts.js'
import { date } from '../lib/format.js'
import { useApi } from '../lib/useApi.js'
import { ErrorBox, Loading } from './ui.jsx'

// Follow-up drafts tab (BUILD_SPEC §10, task T4.9). Drafts only: nothing is ever sent.

const TONES = [['friendly', 'Friendly'], ['firm', 'Firm']]
const CHANNELS = [['email', 'Email'], ['whatsapp', 'WhatsApp']]

function Toggle({ label, options, value, onChange, disabled }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border border-slate-300 overflow-hidden text-sm">
      {options.map(([v, text]) => (
        <button key={v} type="button" role="radio" aria-checked={value === v} disabled={disabled}
                onClick={() => onChange(v)}
                className={`px-3 py-1.5 ${value === v ? 'bg-slate-900 text-white' : 'bg-white hover:bg-slate-50'}`}>
          {text}
        </button>
      ))}
    </div>
  )
}

/** Reviewer notes are shown apart from the message itself; VERIFY notes are amber. */
function DraftText({ text }) {
  const { notes, body } = splitDraft(text)
  return (
    <>
      {notes.map((n) => (
        <p key={n} className={`text-xs mb-1 ${n.startsWith('VERIFY') ? 'text-amber-800 bg-amber-50 rounded px-2 py-1' : 'text-slate-500'}`}>
          {n}
        </p>
      ))}
      <pre className="whitespace-pre-wrap font-sans text-sm mt-2">{body}</pre>
    </>
  )
}

function CopyButton({ text, label = 'Copy' }) {
  const [state, setState] = useState('idle')
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setState('copied')
    } catch {
      setState('failed')
    }
    setTimeout(() => setState('idle'), 2000)
  }
  return (
    <button type="button" onClick={copy} className="text-xs px-2 py-1 rounded border border-slate-300 hover:bg-slate-50">
      {state === 'copied' ? 'Copied ✓' : state === 'failed' ? 'Copy failed' : label}
    </button>
  )
}

export default function FollowupsPanel({ invoiceId }) {
  const [tone, setTone] = useState('friendly')
  const [channel, setChannel] = useState('email')
  const [busy, setBusy] = useState(false)
  const [genError, setGenError] = useState(null)
  const { data, error, loading, reload } = useApi(() => api.listFollowups(invoiceId), [invoiceId])

  async function generate() {
    setBusy(true)
    setGenError(null)
    try {
      await api.generateFollowups(invoiceId, { tone, channel })
      reload()
    } catch (e) {
      setGenError(e)
    } finally {
      setBusy(false)
    }
  }

  const drafts = (data || []).filter((d) => d.tone === tone && d.channel === channel)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Toggle label="Tone" options={TONES} value={tone} onChange={setTone} disabled={busy} />
        <Toggle label="Channel" options={CHANNELS} value={channel} onChange={setChannel} disabled={busy} />
        <button type="button" onClick={generate} disabled={busy}
                className="px-3 py-1.5 rounded-md bg-slate-900 text-white text-sm disabled:opacity-40">
          {busy ? 'Generating…' : drafts.length ? 'Regenerate drafts' : 'Generate drafts'}
        </button>
        <span className="text-xs text-slate-500">Drafts only. Nothing is sent from VyapaarIQ.</span>
      </div>

      {genError && <ErrorBox error={genError} />}
      {loading && <Loading label="Loading drafts…" />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {!loading && !error && drafts.length === 0 && (
        <p className="text-sm text-slate-500">
          No {tone} {channel === 'whatsapp' ? 'WhatsApp' : 'email'} drafts yet. Generate them for the
          D−7, D−1, D+3, D+10 and D+25 schedule.
        </p>
      )}

      <ol className="space-y-3">
        {drafts.map((d) => (
          <li key={d.id} className={`border rounded-lg p-3 ${d.past ? 'border-slate-200 bg-slate-50' : 'border-slate-300 bg-white'}`}
              data-step={d.step_label}>
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <b>{d.step_label}</b>
              <span className="text-sm text-slate-600">send on {date(d.send_on)}</span>
              {d.past && <span className="px-2 py-0.5 rounded-full text-xs bg-slate-200 text-slate-700">date passed</span>}
              <span className="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-800">draft, not sent</span>
              <span className="ml-auto flex gap-2">
                {(() => {
                  const msg = splitDraft(d.draft_text).body
                  const email = d.channel === 'email' ? splitEmail(msg) : null
                  // email: subject and body go into different fields of the mail client
                  return email && email.subject !== null ? (
                    <>
                      <CopyButton text={email.subject} label="Copy subject" />
                      <CopyButton text={email.body} label="Copy body" />
                    </>
                  ) : <CopyButton text={msg} />
                })()}
              </span>
            </div>
            <DraftText text={d.draft_text} />
          </li>
        ))}
      </ol>
    </div>
  )
}
