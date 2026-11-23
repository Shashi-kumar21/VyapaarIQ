import { useParams } from 'react-router-dom'
import Placeholder from '../components/Placeholder.jsx'

export default function InvoiceDetail() {
  const { id } = useParams()
  return (
    <Placeholder title={`Invoice #${id}`} task="T2.13 – T2.15">
      <p className="text-sm">Header, evidence graph, checks, actions, follow-ups and dispute pack.</p>
    </Placeholder>
  )
}
