import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ToastProvider } from './components/Toast'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import HealthPage from './pages/HealthPage'
import ObservabilityPage from './pages/ObservabilityPage'

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard"     element={<DashboardPage />} />
            <Route path="observability" element={<ObservabilityPage />} />
            <Route path="health"        element={<HealthPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  )
}
