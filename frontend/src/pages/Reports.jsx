import { useState, useEffect, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'

const API = '/api'

const fmt  = n => `$${(n || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
const fmtD = n => `$${(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const fmtH = n => `${(n || 0).toFixed(1)}h`
const fmtPct = n => `${(n || 0).toFixed(1)}%`

function pad(n) { return String(n).padStart(2, '0') }
function fmtDate(d) { return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}` }

function getPresetRange(preset) {
  const now = new Date()
  if (preset === 'month') {
    return { start: `${now.getFullYear()}-${pad(now.getMonth()+1)}-01`, end: fmtDate(now) }
  }
  if (preset === 'quarter') {
    const q = Math.floor(now.getMonth() / 3)
    return { start: fmtDate(new Date(now.getFullYear(), q * 3, 1)), end: fmtDate(now) }
  }
  if (preset === 'year') {
    return { start: `${now.getFullYear()}-01-01`, end: fmtDate(now) }
  }
  return { start: '', end: '' }
}

const PRESETS = [
  { key: 'month',   label: 'This Month' },
  { key: 'quarter', label: 'This Quarter' },
  { key: 'year',    label: 'This Year' },
  { key: 'all',     label: 'All Time' },
]

const INPUT = 'border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white'

export default function Reports() {
  const [data, setData]               = useState(null)
  const [loading, setLoading]         = useState(false)
  const [customers, setCustomers]     = useState([])
  const [activePreset, setActivePreset] = useState('year')
  const [startDate, setStartDate]     = useState(() => getPresetRange('year').start)
  const [endDate, setEndDate]         = useState(() => getPresetRange('year').end)
  const [customerFilter, setCustomerFilter] = useState('')

  useEffect(() => {
    fetch(`${API}/customers`).then(r => r.json()).then(d => {
      setCustomers(Array.isArray(d) ? d : (d.customers || []))
    }).catch(() => {})
  }, [])

  const fetchReport = useCallback((start, end, custId) => {
    setLoading(true)
    const params = new URLSearchParams()
    if (start) params.set('start', start)
    if (end)   params.set('end', end)
    if (custId) params.set('customer_id', custId)
    fetch(`${API}/reports/pl?${params}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    const r = getPresetRange('year')
    fetchReport(r.start, r.end, '')
  }, [fetchReport])

  function handlePreset(preset) {
    setActivePreset(preset)
    const r = getPresetRange(preset)
    setStartDate(r.start)
    setEndDate(r.end)
    fetchReport(r.start, r.end, customerFilter)
  }

  function handleApply() {
    setActivePreset('custom')
    fetchReport(startDate, endDate, customerFilter)
  }

  const s = data?.summary || {}
  const byMonth   = data?.by_month || []
  const byCust    = (data?.by_customer || []).slice().sort((a, b) => b.revenue - a.revenue)
  const byCat     = (data?.by_category || []).slice().sort((a, b) => b.revenue - a.revenue)
  const expByCat  = (data?.expenses_by_category || []).slice().sort((a, b) => b.total - a.total)
  const waste     = data?.waste_indicators || {}

  const netColor  = s.net_profit >= 0 ? 'text-green-700' : 'text-red-600'
  const netBg     = s.net_profit >= 0 ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'

  return (
    <div className="space-y-6">

      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Reports &amp; P&amp;L</h1>
        <p className="text-sm text-gray-500 mt-1">Profit &amp; Loss — see what's working, what's costing you.</p>
      </div>

      {/* Filter Bar */}
      <div className="bg-white rounded-xl border border-gray-200 px-4 py-3 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 flex-wrap">
          {PRESETS.map(p => (
            <button
              key={p.key}
              onClick={() => handlePreset(p.key)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                activePreset === p.key
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2 ml-auto">
          <input
            type="date"
            value={startDate}
            onChange={e => setStartDate(e.target.value)}
            className={INPUT}
          />
          <span className="text-gray-400 text-sm">to</span>
          <input
            type="date"
            value={endDate}
            onChange={e => setEndDate(e.target.value)}
            className={INPUT}
          />
          <select
            value={customerFilter}
            onChange={e => setCustomerFilter(e.target.value)}
            className={INPUT}
          >
            <option value="">All Customers</option>
            {customers.filter(c => !c.name.startsWith('_')).map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <button
            onClick={handleApply}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            Apply
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center h-48 text-gray-400">Loading report...</div>
      )}

      {!loading && data && (
        <>
          {/* Primary KPI Banner */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className={`rounded-xl border p-5 ${netBg}`}>
              <div className={`text-3xl font-bold ${netColor}`}>{fmtD(s.net_profit)}</div>
              <div className="text-sm font-medium text-gray-600 mt-1">Net Profit</div>
              {s.total_revenue > 0 && (
                <div className={`text-xs mt-1 ${netColor} opacity-75`}>
                  {fmtPct((s.net_profit / s.total_revenue) * 100)} margin
                </div>
              )}
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="text-3xl font-bold text-gray-900">{fmtD(s.total_revenue)}</div>
              <div className="text-sm font-medium text-gray-500 mt-1">Total Revenue</div>
              <div className="text-xs text-gray-400 mt-1">{s.job_count} jobs</div>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="text-3xl font-bold text-rose-600">{fmtD(s.total_expenses)}</div>
              <div className="text-sm font-medium text-gray-500 mt-1">Total Expenses</div>
              <div className="text-xs text-gray-400 mt-1">overhead + job costs</div>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="text-3xl font-bold text-blue-700">{fmtD(s.effective_hourly_rate)}</div>
              <div className="text-sm font-medium text-gray-500 mt-1">Effective $/Hour</div>
              <div className="text-xs text-gray-400 mt-1">{fmtH(s.total_hours)} tracked</div>
            </div>
          </div>

          {/* Secondary Stats Row */}
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
            <div className="bg-gray-50 rounded-xl p-3 text-center">
              <div className="text-lg font-bold text-gray-900">{fmtD(s.total_labor_revenue)}</div>
              <div className="text-xs text-gray-500 mt-0.5">Labor Revenue</div>
            </div>
            <div className="bg-gray-50 rounded-xl p-3 text-center">
              <div className="text-lg font-bold text-gray-900">{fmtD(s.total_materials_revenue)}</div>
              <div className="text-xs text-gray-500 mt-0.5">Materials Revenue</div>
            </div>
            <div className="bg-gray-50 rounded-xl p-3 text-center">
              <div className="text-lg font-bold text-rose-600">{fmtD(s.total_overhead)}</div>
              <div className="text-xs text-gray-500 mt-0.5">Overhead</div>
            </div>
            <div className="bg-gray-50 rounded-xl p-3 text-center">
              <div className="text-lg font-bold text-orange-600">{fmtD(s.total_job_expenses)}</div>
              <div className="text-xs text-gray-500 mt-0.5">Job Expenses</div>
            </div>
            <div className="bg-gray-50 rounded-xl p-3 text-center">
              <div className="text-lg font-bold text-gray-900">{fmtH(s.total_hours)}</div>
              <div className="text-xs text-gray-500 mt-0.5">Total Hours</div>
            </div>
            <div className="bg-gray-50 rounded-xl p-3 text-center">
              <div className="text-lg font-bold text-gray-900">{fmtD(s.mileage_deduction_estimate)}</div>
              <div className="text-xs text-gray-500 mt-0.5">Mileage Deduction</div>
            </div>
          </div>

          {/* Month-over-Month Chart */}
          {byMonth.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-base font-semibold text-gray-800 mb-4">Month-over-Month</h2>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={byMonth} barGap={3}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis
                    dataKey="month"
                    tick={{ fontSize: 11 }}
                    tickFormatter={v => v.slice(5)}
                  />
                  <YAxis tickFormatter={v => `$${(v/1000).toFixed(0)}k`} tick={{ fontSize: 11 }} width={52} />
                  <Tooltip formatter={v => fmtD(v)} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="revenue"  name="Revenue"  fill="#22c55e" radius={[3,3,0,0]} />
                  <Bar dataKey="expenses" name="Expenses" fill="#f43f5e" radius={[3,3,0,0]} />
                  <Bar dataKey="profit"   name="Profit"   fill="#3b82f6" radius={[3,3,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Two-column: By Customer + By Service Type */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

            {/* By Customer */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100">
                <h2 className="text-base font-semibold text-gray-800">By Customer</h2>
                <p className="text-xs text-gray-400 mt-0.5">Sorted by revenue, highest first</p>
              </div>
              {byCust.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50 border-b border-gray-100">
                        <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500">Customer</th>
                        <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500">Revenue</th>
                        <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500">Profit</th>
                        <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500">Hours</th>
                        <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500">Jobs</th>
                        <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500">Miles</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {byCust.map(c => {
                        const margin = c.revenue > 0 ? (c.profit / c.revenue) * 100 : 0
                        const profitColor = c.profit >= 0 ? 'text-green-700' : 'text-red-600'
                        return (
                          <tr key={c.customer_id} className="hover:bg-gray-50">
                            <td className="px-4 py-2.5 font-medium text-gray-900 truncate max-w-28">{c.customer_name}</td>
                            <td className="px-3 py-2.5 text-right tabular-nums text-gray-700">{fmt(c.revenue)}</td>
                            <td className="px-3 py-2.5 text-right tabular-nums">
                              <span className={profitColor}>{fmt(c.profit)}</span>
                              <span className="text-xs text-gray-400 ml-1">({fmtPct(margin)})</span>
                            </td>
                            <td className="px-3 py-2.5 text-right tabular-nums text-gray-500">{fmtH(c.hours)}</td>
                            <td className="px-3 py-2.5 text-right tabular-nums text-gray-500">{c.job_count}</td>
                            <td className="px-3 py-2.5 text-right tabular-nums text-gray-400">{c.miles ? Math.round(c.miles) : '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="px-5 py-8 text-center text-gray-400 text-sm">No customer data for this period</div>
              )}
            </div>

            {/* By Service Type */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100">
                <h2 className="text-base font-semibold text-gray-800">By Service Type</h2>
                <p className="text-xs text-gray-400 mt-0.5">Sorted by revenue, highest first</p>
              </div>
              {byCat.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50 border-b border-gray-100">
                        <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500">Category</th>
                        <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500">Revenue</th>
                        <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500">Jobs</th>
                        <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500">Avg/Job</th>
                        <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500">Hours</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {byCat.map(c => (
                        <tr key={c.category} className="hover:bg-gray-50">
                          <td className="px-4 py-2.5 font-medium text-gray-900 truncate max-w-32">{c.category || 'Uncategorized'}</td>
                          <td className="px-3 py-2.5 text-right tabular-nums text-gray-700">{fmt(c.revenue)}</td>
                          <td className="px-3 py-2.5 text-right tabular-nums text-gray-500">{c.job_count}</td>
                          <td className="px-3 py-2.5 text-right tabular-nums text-gray-500">{fmt(c.avg_per_job)}</td>
                          <td className="px-3 py-2.5 text-right tabular-nums text-gray-400">{fmtH(c.hours)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="px-5 py-8 text-center text-gray-400 text-sm">No category data for this period</div>
              )}
            </div>
          </div>

          {/* Expense Breakdown */}
          {expByCat.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-base font-semibold text-gray-800 mb-4">Expense Breakdown</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={expByCat} layout="vertical" margin={{ left: 8, right: 16 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                      <XAxis type="number" tickFormatter={v => `$${(v/1000).toFixed(0)}k`} tick={{ fontSize: 10 }} />
                      <YAxis
                        type="category"
                        dataKey="expense_category"
                        tick={{ fontSize: 10 }}
                        width={120}
                        tickFormatter={v => v ? (v.length > 18 ? v.slice(0, 17) + '…' : v) : 'Other'}
                      />
                      <Tooltip formatter={v => fmtD(v)} />
                      <Bar
                        dataKey="total"
                        name="Total"
                        fill="#f97316"
                        radius={[0,3,3,0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-100">
                        <th className="text-left py-2 text-xs font-semibold text-gray-500">Category</th>
                        <th className="text-right py-2 text-xs font-semibold text-gray-500">Total</th>
                        <th className="text-right py-2 text-xs font-semibold text-gray-500">Count</th>
                        <th className="text-right py-2 text-xs font-semibold text-gray-500">Type</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {expByCat.map(e => (
                        <tr key={e.expense_category} className="hover:bg-gray-50">
                          <td className="py-2 font-medium text-gray-800 truncate max-w-36">{e.expense_category || 'Other'}</td>
                          <td className="py-2 text-right tabular-nums text-orange-700 font-semibold">{fmtD(e.total)}</td>
                          <td className="py-2 text-right text-gray-500">{e.count}</td>
                          <td className="py-2 text-right">
                            <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                              e.is_overhead ? 'bg-red-100 text-red-600' : 'bg-orange-100 text-orange-700'
                            }`}>
                              {e.is_overhead ? 'Overhead' : 'Job'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Waste Indicators */}
          {waste.unplanned_supply_trips > 0 && (
            <div className="bg-amber-50 border border-amber-300 rounded-xl p-5">
              <div className="flex items-start gap-3">
                <div className="text-2xl mt-0.5">!</div>
                <div>
                  <h3 className="text-base font-semibold text-amber-900">Waste Indicators</h3>
                  <p className="text-sm text-amber-800 mt-1">
                    <strong>{waste.unplanned_supply_trips}</strong> unplanned supply{' '}
                    {waste.unplanned_supply_trips === 1 ? 'trip' : 'trips'} —{' '}
                    <strong>{waste.unplanned_supply_miles}</strong> extra miles —{' '}
                    estimated <strong>{fmtD(waste.unplanned_trip_cost_estimate)}</strong> in wasted fuel and time.
                  </p>
                  <p className="text-xs text-amber-700 mt-2">
                    Better planning and complete material lists before starting a job could eliminate these extra trips.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Empty state */}
          {!s.job_count && !loading && (
            <div className="bg-white rounded-xl border border-gray-200 py-16 text-center text-gray-400">
              <div className="text-4xl mb-3">📊</div>
              <div className="text-lg font-medium">No data for this period</div>
              <div className="text-sm mt-1">Try a wider date range or All Time</div>
            </div>
          )}
        </>
      )}

      {!loading && !data && (
        <div className="bg-white rounded-xl border border-gray-200 py-16 text-center text-gray-400">
          <div className="text-lg font-medium">No report data yet</div>
          <div className="text-sm mt-1">Set a date range and click Apply</div>
        </div>
      )}

    </div>
  )
}
