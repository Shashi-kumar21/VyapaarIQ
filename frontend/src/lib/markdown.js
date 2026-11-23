// Minimal parser for the dispute-pack Markdown (backend app/dispute/pack.py to_markdown):
// "# h1", "## h2", "---", "_italic line_", pipe tables and paragraphs. Returns plain data that
// React renders as text, so nothing from the document is ever injected as HTML.

function cells(line) {
  // split on | that is not escaped as \|
  const parts = line.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/)
  return parts.map((c) => c.trim().replace(/\\\|/g, '|'))
}

/** -> [{type: 'h1'|'h2'|'p'|'em'|'hr', text} | {type: 'table', head: string[], rows: string[][]}] */
export function parseMarkdown(md) {
  const lines = (md || '').replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    if (!line.trim()) continue
    if (line.startsWith('# ')) blocks.push({ type: 'h1', text: line.slice(2).trim() })
    else if (line.startsWith('## ')) blocks.push({ type: 'h2', text: line.slice(3).trim() })
    else if (/^-{3,}\s*$/.test(line)) blocks.push({ type: 'hr' })
    else if (line.startsWith('|') && /^\|[\s|:-]+\|?\s*$/.test(lines[i + 1] || '')) {
      const head = cells(line)
      const rows = []
      i += 2
      while (i < lines.length && lines[i].startsWith('|')) {
        rows.push(cells(lines[i]))
        i += 1
      }
      i -= 1
      blocks.push({ type: 'table', head, rows })
    } else if (/^_.*_$/.test(line.trim())) blocks.push({ type: 'em', text: line.trim().slice(1, -1) })
    else blocks.push({ type: 'p', text: line.trim() })
  }
  return blocks
}
