import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

const fmt  = n => `$${(n || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
const fmtD = n => `$${(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const fmtH = n => `${(n || 0).toFixed(1)}h`

export default function Dashboard() {
  const [stats, setStats]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  useEffect(() => {
    fetch('/api/dashboard')
      .then(r => r.json())
      .then(data => { setStats(data); setLoading(false) })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-500">Loading dashboard...</div>
  )
  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">Error: {error}</div>
  )

  const est = stats?.estimation_accuracy || {}

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="text-sm text-gray-500">Beard's Home Services</div>
      </div>

      {/* Primary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Labor Revenue"  value={fmt(stats?.total_labor)}     color="green" />
        <StatCard label="Avg $/Hour"     value={fmtD(stats?.avg_hourly_rate)} color="blue"  />
        <StatCard label="Hours Tracked"  value={fmtH(stats?.total_hours)}    color="purple"/>
        <StatCard label="Avg Days / Job" value={`${stats?.avg_days_per_job || 0} days`} color="amber" />
      </div>

      {/* Secondary counters */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Customers"     value={stats?.customer_count || 0}  small />
        <StatCard label="Jobs"          value={stats?.job_count || 0}        small />
        <StatCard label="Invoices"      value={stats?.invoice_count || 0}    small />
        <StatCard label="Materials"     value={fmt(stats?.total_materials)}  small />
      </div>

      {/* Estimation accuracy banner (only shows once you have jobs with estimates) */}
      {est.jobs_with_estimates > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-blue-900 mb-3">Estimation Accuracy</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-blue-800">{est.jobs_with_estimates}</div>
              <div className="text-xs text-blue-600 mt-0.5">Jobs with estimates</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-blue-800">
                {est.jobs_with_estimates > 0
                  ? `${Math.round((est.on_time / est.jobs_with_estimates) * 100)}%`
                  : '—'}
              </div>
              <div className="text-xs text-blue-600 mt-0.5">On or under estimate</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-blue-800">{est.avg_estimated_days ?? '—'}</div>
              <div className="text-xs text-blue-600 mt-0.5">Avg estimated days</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-blue-800">{est.avg_actual_days ?? '—'}</div>
              <div className="text-xs text-blue-600 mt-0.5">Avg actual days</div>
            </div>
          </div>
        </div>
      )}

      {/* Revenue by year chart */}
      {stats?.revenue_by_year?.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Revenue by Year</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stats.revenue_by_year} barGap={4}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="year" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={v => `$${(v/1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={v => fmtD(v)} />
              <Bar dataKey="total_labor"     name="Labor"     fill="#22c55e" radius={[4,4,0,0]} />
              <Bar dataKey="total_materials" name="Materials" fill="#e5e7eb" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Two-column: Recent jobs + Top customers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

        {/* Recent jobs */}
        <div className="bg-white rounded-xl border border-gray-200">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h2 className="text-base font-semibold text-gray-800">Recent Jobs</h2>
            <Link to="/filing-cabinet" className="text-sm text-blue-600 hover:text-blue-800">View all →</Link>
          </div>
          <div className="divide-y divide-gray-50">
            {(stats?.recent_jobs || []).slice(0, 8).map(job => (
              <Link
                key={job.id}
                to={`/filing-cabinet?job=${job.id}`}
                className="flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors"
              >
                <div className="min-w-0">
                  <div className="font-medium text-gray-900 text-sm truncate">{job.customer_name}</div>
                  <div className="text-xs text-gray-400 flex items-center gap-2 mt-0.5">
                    <span>{job.start_date}</span>
                    {job.actual_days > 0 && <span>· {job.actual_days}d on site</span>}
                  </div>
                </div>
                <div className="text-right flex-shrink-0 ml-3">
                  <div className="text-sm font-semibold text-gray-900">{fmt(job.total_labor)}</div>
                  <StatusBadge status={job.status} />
                </div>
              </Link>
            ))}
            {(!stats?.recent_jobs || stats.recent_jobs.length === 0) && (
              <div className="px-5 py-8 text-center text-gray-400 text-sm">No jobs yet</div>
            )}
          </div>
        </div>

        {/* Top customers */}
        <div className="bg-white rounded-xl border border-gray-200">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h2 className="text-base font-semibold text-gray-800">Top Customers</h2>
            <Link to="/customers" className="text-sm text-blue-600 hover:text-blue-800">View all →</Link>
          </div>
          <div className="divide-y divide-gray-50">
            {(stats?.top_customers || []).map((c, i) => (
              <div key={c.id} className="flex items-center justify-between px-5 py-3 hover:bg-gray-50">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-xs font-bold text-gray-300 w-4">{i + 1}</span>
                  <div className="min-w-0">
                    <div className="font-medium text-gray-900 text-sm truncate">{c.name}</div>
                    <div className="text-xs text-gray-400">
                      {c.job_count} job{c.job_count !== 1 ? 's' : ''}
                      {c.total_hours > 0 && ` · ${fmtH(c.total_hours)}`}
                    </div>
                  </div>
                </div>
                <div className="text-sm font-semibold text-gray-900 flex-shrink-0 ml-3">
                  {fmt(c.total_revenue)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Revenue by service category */}
      {stats?.revenue_by_category?.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-base font-semibold text-gray-800">Revenue by Service Type</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {stats.revenue_by_category.map(cat => {
              const pct = stats.total_labor > 0
                ? Math.round((cat.total_revenue / stats.total_labor) * 100)
                : 0
              return (
                <div key={cat.category} className="px-5 py-3 flex items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-gray-800 truncate">{cat.category}</span>
                      <div className="flex items-center gap-3 flex-shrink-0 ml-3 text-xs text-gray-500">
                        <span>{cat.job_count} job{cat.job_count !== 1 ? 's' : ''}</span>
                        <span className="font-semibold text-gray-900">{fmt(cat.total_revenue)}</span>
                      </div>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-1.5">
                      <div
                        className="bg-blue-500 h-1.5 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, color = 'gray', small = false }) {
  const colors = {
    blue:   'bg-blue-50 text-blue-700',
    green:  'bg-green-50 text-green-700',
    purple: 'bg-purple-50 text-purple-700',
    amber:  'bg-amber-50 text-amber-700',
    gray:   'bg-gray-50 text-gray-700',
  }
  return (
    <div className={`rounded-xl p-4 ${small ? 'bg-gray-50' : colors[color] || colors.gray}`}>
      <div className={`font-bold ${small ? 'text-xl text-gray-900' : 'text-2xl'}`}>{value}</div>
      <div className={`text-xs mt-1 ${small ? 'text-gray-500' : 'opacity-75'}`}>{label}</div>
    </div>
  )
}

function StatusBadge({ status }) {
  const map = {
    completed: 'bg-green-100 text-green-700',
    paid:      'bg-green-100 text-green-700',
    pending:   'bg-yellow-100 text-yellow-700',
    estimate:  'bg-blue-100 text-blue-700',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium mt-0.5 inline-block ${map[status] || 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  )
}
