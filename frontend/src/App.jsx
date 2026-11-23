import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Buyers from './pages/Buyers.jsx'
import Dashboard from './pages/Dashboard.jsx'
import InvoiceDetail from './pages/InvoiceDetail.jsx'
import NewPackage from './pages/NewPackage.jsx'
import NotFound from './pages/NotFound.jsx'

// The four pages of BUILD_SPEC §13.
export default function App() {
  return (
    <BrowserRouter>
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
