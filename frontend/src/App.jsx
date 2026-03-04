import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Jobs from './pages/Jobs'
import Customers from './pages/Customers'
import TimeEntry from './pages/TimeEntry'
import FilingCabinet from './pages/FilingCabinet'
import PrintView from './pages/PrintView'
import Estimate from './pages/Estimate'
import Expenses from './pages/Expenses'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50">
        <nav className="bg-white shadow-sm border-b border-slate-200 print:hidden">
          <div className="max-w-7xl mx-auto px-4">
            <div className="flex justify-between h-16">
              <div className="flex items-center">
                <span className="text-xl font-bold text-slate-800">Beard's Home Services</span>
              </div>
              <div className="flex items-center space-x-1">
                <NavLink to="/" className={({ isActive }) =>
                  `px-4 py-2 rounded-lg font-medium transition-colors ${isActive ? 'bg-blue-100 text-blue-700' : 'text-slate-600 hover:bg-slate-100'}`}>
                  Dashboard
                </NavLink>
                <NavLink to="/filing-cabinet" className={({ isActive }) =>
                  `px-4 py-2 rounded-lg font-medium transition-colors ${isActive ? 'bg-blue-100 text-blue-700' : 'text-slate-600 hover:bg-slate-100'}`}>
                  Filing Cabinet
                </NavLink>
                <NavLink to="/jobs" className={({ isActive }) =>
                  `px-4 py-2 rounded-lg font-medium transition-colors ${isActive ? 'bg-blue-100 text-blue-700' : 'text-slate-600 hover:bg-slate-100'}`}>
                  Jobs
                </NavLink>
                <NavLink to="/customers" className={({ isActive }) =>
                  `px-4 py-2 rounded-lg font-medium transition-colors ${isActive ? 'bg-blue-100 text-blue-700' : 'text-slate-600 hover:bg-slate-100'}`}>
                  Customers
                </NavLink>
                <NavLink to="/time" className={({ isActive }) =>
                  `px-4 py-2 rounded-lg font-medium transition-colors ${isActive ? 'bg-green-100 text-green-700' : 'text-slate-600 hover:bg-slate-100'}`}>
                  + Time Entry
                </NavLink>
                <NavLink to="/estimate" className={({ isActive }) =>
                  `px-4 py-2 rounded-lg font-medium transition-colors ${isActive ? 'bg-blue-100 text-blue-700' : 'text-slate-600 hover:bg-slate-100'}`}>
                  + Estimate
                </NavLink>
                <NavLink to="/expenses" className={({ isActive }) =>
                  `px-4 py-2 rounded-lg font-medium transition-colors ${isActive ? 'bg-orange-100 text-orange-700' : 'text-slate-600 hover:bg-slate-100'}`}>
                  Expenses
                </NavLink>
              </div>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/filing-cabinet" element={<FilingCabinet />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/customers" element={<Customers />} />
            <Route path="/time" element={<TimeEntry />} />
            <Route path="/estimate" element={<Estimate />} />
            <Route path="/print/:jobId" element={<PrintView />} />
            <Route path="/expenses" element={<Expenses />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
