import { ArrowLeft, Compass } from 'lucide-react'
import { Link } from 'react-router'
import { Empty } from '../components/ui.jsx'
import { btn } from '../lib/styles.js'

export default function NotFound() {
  return (
    <section>
      <h1 className="sr-only">Page not found</h1>
      <Empty title="Page not found" icon={Compass}
             action={<Link className={btn.secondary} to="/"><ArrowLeft aria-hidden="true" className="size-4" />Back to the dashboard</Link>}>
        The address may be mistyped, or the page may have moved.
      </Empty>
    </section>
  )
}
