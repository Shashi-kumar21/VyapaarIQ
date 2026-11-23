/** Temporary page body until the page's task lands; says which task fills it. */
export default function Placeholder({ title, task, children }) {
  return (
    <section>
      <h1 className="text-2xl font-semibold mb-2">{title}</h1>
      <p className="text-slate-500 text-sm mb-4">Coming in {task}.</p>
      {children}
    </section>
  )
}
