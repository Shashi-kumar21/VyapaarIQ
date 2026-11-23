import { Link } from 'react-router'

export default function NotFound() {
  return (
    <section>
      <h1 className="text-2xl font-semibold mb-2">Page not found</h1>
      <Link className="text-blue-700 underline" to="/">Back to the dashboard</Link>
    </section>
  )
}
