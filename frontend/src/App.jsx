import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Buyers from './pages/Buyers.jsx'
import Dashboard from './pages/Dashboard.jsx'
import InvoiceDetail from './pages/InvoiceDetail.jsx'
import NewPackage from './pages/NewPackage.jsx'
import NotFound from './pages/NotFound.jsx'

// Opt in to React Router v7 behaviour now (silences the v6 future-flag warnings).
const ROUTER_FUTURE = { v7_startTransition: true, v7_relativeSplatPath: true }

// The four pages of BUILD_SPEC §13.
export default function App() {
  return (
    <BrowserRouter future={ROUTER_FUTURE}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="packages/new" element={<NewPackage />} />
          <Route path="invoices/:id" element={<InvoiceDetail />} />
          <Route path="buyers" element={<Buyers />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
