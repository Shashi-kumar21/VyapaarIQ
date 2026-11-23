import { useState } from 'react'

// Evidence graph (BUILD_SPEC §12, task T2.14): the invoice on the left, each supporting document on
// the right, one edge per relation. Plain SVG so it is predictable in a live demo.

const NODE_STYLE = {
  ok: { fill: '#dcfce7', stroke: '#15803d', icon: '✓', label: 'OK' },
  missing: { fill: '#fee2e2', stroke: '#b91c1c', icon: '?', label: 'Missing', dashed: true },
  mismatch: { fill: '#fee2e2', stroke: '#b91c1c', icon: '✕', label: 'Mismatch' },
  uncertain: { fill: '#fef3c7', stroke: '#d97706', icon: '!', label: 'Needs human check' },
}
const EDGE_STYLE = {
  matched: { stroke: '#15803d' },
  mismatch: { stroke: '#b91c1c' },
  missing: { stroke: '#94a3b8', dashed: true },
  uncertain: { stroke: '#d97706', dashed: true },
}

const W = 760
const NODE_W = 230
const NODE_H = 58
const ROW = 84
const LEFT_X = 20
const RIGHT_X = W - NODE_W - 20

function wrap(text, max = 30) {
  if (!text) return ['']
  if (text.length <= max) return [text]
  const cut = text.lastIndexOf(' ', max)
  const i = cut > 10 ? cut : max
  const rest = text.slice(i).trim()
  return [text.slice(0, i), rest.length > max ? rest.slice(0, max - 1) + '…' : rest]
}

function Node({ node, x, y, selected, onSelect }) {
  const s = NODE_STYLE[node.status] || NODE_STYLE.uncertain
  const lines = wrap(node.label)
  return (
    <g
      role="button" tabIndex={0} aria-label={`${node.label}: ${s.label}`}
      onClick={() => onSelect({ kind: 'node', node })}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect({ kind: 'node', node })}
      className="group cursor-pointer focus:outline-none" data-status={node.status} data-node={node.id}
    >
      <rect x={x} y={y} width={NODE_W} height={NODE_H} rx={10} fill={s.fill} stroke={s.stroke}
            strokeWidth={selected ? 3 : 1.5} strokeDasharray={s.dashed ? '6 4' : undefined}
            className="group-focus-visible:[stroke-width:3]" />
      <circle cx={x + 22} cy={y + NODE_H / 2} r={11} fill={s.stroke} />
      <text x={x + 22} y={y + NODE_H / 2 + 4.5} textAnchor="middle" fontSize="13" fontWeight="700" fill="#fff">
        {s.icon}
      </text>
      {lines.map((l, i) => (
        <text key={i} x={x + 42} y={y + (lines.length === 1 ? 34 : 25 + i * 16)} fontSize="13" fill="#0f172a">
          {l}
        </text>
      ))}
    </g>
  )
}

/** graph = {nodes, edges} from /api/invoices/{id}/graph; checks = analysis.checks (for the detail panel). */
export default function EvidenceGraph({ graph, checks = [] }) {
  const [selected, setSelected] = useState(null)
  const inv = graph.nodes.find((n) => n.id === 'inv')
  const others = graph.nodes.filter((n) => n.id !== 'inv')
  const H = Math.max(NODE_H + 40, others.length * ROW + 20)
  const pos = { inv: { x: LEFT_X, y: H / 2 - NODE_H / 2 } }
  others.forEach((n, i) => { pos[n.id] = { x: RIGHT_X, y: 10 + i * ROW + (ROW - NODE_H) / 2 } })
  const byId = Object.fromEntries(checks.map((c) => [c.check_id, c]))
  const selKey = selected && (selected.kind === 'node' ? `n:${selected.node.id}` : `e:${selected.edge.to}`)

  return (
    <div>
      {/* Desktop-first (§13): below ~640px the graph keeps a readable size and scrolls sideways. */}
      <div className="overflow-x-auto -mx-1 px-1">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[640px] h-auto" role="img"
           aria-label="Evidence graph: the invoice linked to each supporting document">
        {graph.edges.map((e) => {
          const a = pos[e.from]
          const b = pos[e.to]
          if (!a || !b) return null
          const st = EDGE_STYLE[e.status] || EDGE_STYLE.uncertain
          const x1 = a.x + NODE_W
          const y1 = a.y + NODE_H / 2
          const x2 = b.x
          const y2 = b.y + NODE_H / 2
          const mx = (x1 + x2) / 2
          const my = (y1 + y2) / 2
          const isSel = selKey === `e:${e.to}`
          return (
            <g key={`${e.from}-${e.to}`} role="button" tabIndex={0} className="group cursor-pointer focus:outline-none"
               aria-label={`${e.from} to ${e.to}: ${e.status}. ${e.note}`} data-edge={e.to} data-status={e.status}
               onClick={() => setSelected({ kind: 'edge', edge: e })}
               onKeyDown={(ev) => (ev.key === 'Enter' || ev.key === ' ') && setSelected({ kind: 'edge', edge: e })}>
              <path d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} fill="none" stroke={st.stroke}
                    strokeWidth={isSel ? 4 : 2.5} strokeDasharray={st.dashed ? '7 5' : undefined} />
              {/* wide invisible hit area */}
              <path d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} fill="none" stroke="transparent" strokeWidth={14} />
              {/* no browser focus box around the whole curve (B-11); keyboard focus thickens the pill instead */}
              <rect x={mx - 52} y={my - 11} width={104} height={22} rx={11} fill="#fff" stroke={st.stroke}
                    className="group-focus-visible:[stroke-width:3]" />
              <text x={mx} y={my + 4} textAnchor="middle" fontSize="11" fill={st.stroke} fontWeight="600">
                {e.status}{e.check_ids?.length ? ` · ${e.check_ids[0]}${e.check_ids.length > 1 ? '…' : ''}` : ''}
              </text>
            </g>
          )
        })}
        {inv && <Node node={inv} {...pos.inv} selected={selKey === 'n:inv'} onSelect={setSelected} />}
        {others.map((n) => (
          <Node key={n.id} node={n} {...pos[n.id]} selected={selKey === `n:${n.id}`} onSelect={setSelected} />
        ))}
      </svg>
      </div>

      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600 mt-2" aria-label="Legend">
        {Object.entries(NODE_STYLE).map(([k, s]) => (
          <li key={k} className="flex items-center gap-1">
            <span className="inline-flex w-4 h-4 rounded-full text-white text-[10px] items-center justify-center"
                  style={{ background: s.stroke }}>{s.icon}</span>{s.label}
          </li>
        ))}
        <li className="text-slate-400">Click a document or a link for details</li>
      </ul>

      {selected && (
        <div className="mt-3 border border-slate-200 rounded-lg p-3 text-sm bg-slate-50" aria-live="polite">
          {selected.kind === 'edge' ? (
            <>
              <p className="font-medium">
                Invoice → {graph.nodes.find((n) => n.id === selected.edge.to)?.label}:{' '}
                <span style={{ color: (EDGE_STYLE[selected.edge.status] || EDGE_STYLE.uncertain).stroke }}>
                  {selected.edge.status}
                </span>
              </p>
              <p className="text-slate-600 mt-1">{selected.edge.note}</p>
              <ul className="mt-2 space-y-1">
                {selected.edge.check_ids.map((id) => (
                  <li key={id} className="text-xs">
                    <b>{id}</b> {byId[id]?.name} — {byId[id]?.status}: {byId[id]?.detail}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <>
              <p className="font-medium">{selected.node.label}</p>
              <p className="text-slate-600 mt-1">
                Status: {(NODE_STYLE[selected.node.status] || NODE_STYLE.uncertain).label}
                {selected.node.doc_no ? ` · No. ${selected.node.doc_no}` : ''}
              </p>
            </>
          )}
        </div>
      )}
    </div>
  )
}
