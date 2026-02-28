import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'

const API = '/api'
const fmt = n => `$${(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const fmtHours = h => `${(h || 0).toFixed(1)}h`

// Format a start_time like "2024-03-21 07:30:00" -> "7:30 AM"
function fmtTime(ts) {
  if (!ts) return null
  const m = ts.match(/(\d{2}):(\d{2})/)
  if (!m) return null
  let h = parseInt(m[1], 10)
  const min = m[2]
  const ampm = h >= 12 ? 'PM' : 'AM'
  if (h > 12) h -= 12
  if (h === 0) h = 12
  return `${h}:${min} ${ampm}`
}

const STATUS_COLORS = {
  completed: 'bg-green-100 text-green-700',
  paid:      'bg-green-100 text-green-700',
  pending:   'bg-yellow-100 text-yellow-700',
  estimate:  'bg-blue-100 text-blue-700',
}
function StatusBadge({ status }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[status] || 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  )
}

const INPUT = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white'
const INPUT_SM = 'w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white'

// ─────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────
export default function FilingCabinet() {
  const [jobs, setJobs]               = useState([])
  const [categories, setCategories]   = useState([])
  const [selectedId, setSelectedId]   = useState(null)
  const [detail, setDetail]           = useState(null)
  const [loading, setLoading]         = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [search, setSearch]           = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [saving, setSaving]           = useState(false)
  const [converting, setConverting]   = useState(false)
  const [edited, setEdited]           = useState(false)

  // Load sidebar + categories on mount
  useEffect(() => {
    Promise.all([
      fetch(`${API}/filing-cabinet`).then(r => r.json()),
      fetch(`${API}/service-categories`).then(r => r.json()),
    ]).then(([jobData, catData]) => {
      setJobs(jobData.jobs || jobData || [])
      setCategories(catData || [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  // Load detail when a job is selected
  useEffect(() => {
    if (!selectedId) return
    setDetailLoading(true)
    setEdited(false)
    fetch(`${API}/filing-cabinet/${selectedId}`)
      .then(r => r.json())
      .then(data => { setDetail(data); setDetailLoading(false) })
      .catch(() => setDetailLoading(false))
  }, [selectedId])

  const refreshList = useCallback(async () => {
    const r = await fetch(`${API}/filing-cabinet`)
    const data = await r.json()
    setJobs(data.jobs || data || [])
  }, [])

  // Filtered sidebar list
  const filtered = jobs.filter(j => {
    const q = search.toLowerCase()
    const matchSearch = !q ||
      (j.customer || '').toLowerCase().includes(q) ||
      (j.invoice_number || '').toLowerCase().includes(q)
    const matchStatus = statusFilter === 'all' || j.status === statusFilter
    return matchSearch && matchStatus
  })

  // ── Save ──────────────────────────────────────────────────────
  async function handleSave() {
    if (!detail) return
    setSaving(true)
    try {
      const payload = {
        customer_id: detail.customer_id,
        notes: detail.notes,
        status: detail.status,
        services: detail.services,
        time_entries: detail.time_entries,
        customer: {
          name:    detail.customer_name,
          phone:   detail.customer_phone,
          email:   detail.customer_email,
          address: detail.customer_address,
        },
      }
      const res = await fetch(`${API}/filing-cabinet/${detail.job_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error('Save failed')
      setEdited(false)
      await refreshList()
    } catch {
      alert('Error saving changes')
    } finally {
      setSaving(false)
    }
  }

  // ── Claim unlinked time entry ─────────────────────────────────
  async function handleClaim(teId) {
    if (!detail) return
    try {
      await fetch(`${API}/filing-cabinet/${detail.job_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_id: detail.customer_id,
          notes: detail.notes,
          services: detail.services,
          time_entries: detail.time_entries,
          claim_time_entry_ids: [teId],
        }),
      })
      // Refresh detail
      const r = await fetch(`${API}/filing-cabinet/${detail.job_id}`)
      setDetail(await r.json())
    } catch {
      alert('Error claiming time entry')
    }
  }

  // ── Reassign time entry to a different invoice ────────────────
  async function handleReassign(teId, newJobId) {
    try {
      await fetch(`${API}/time-entries/${teId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: newJobId }),
      })
      // Refresh current job detail and sidebar
      const r = await fetch(`${API}/filing-cabinet/${detail.job_id}`)
      setDetail(await r.json())
      await refreshList()
    } catch {
      alert('Error reassigning time entry')
    }
  }

  // ── Convert estimate -> invoice ───────────────────────────────
  async function handleConvert() {
    if (!detail) return
    if (!confirm('Mark this estimate as a completed, paid invoice?')) return
    setConverting(true)
    try {
      await fetch(`${API}/jobs/${detail.job_id}/convert`, { method: 'POST' })
      const r = await fetch(`${API}/filing-cabinet/${detail.job_id}`)
      setDetail(await r.json())
      await refreshList()
    } catch {
      alert('Error converting estimate')
    } finally {
      setConverting(false)
    }
  }

  // ── Helpers to mutate detail state ───────────────────────────
  function setField(key, value) {
    setEdited(true)
    setDetail(prev => ({ ...prev, [key]: value }))
  }

  function updateService(idx, field, value) {
    setEdited(true)
    setDetail(prev => {
      const services = [...(prev.services || [])]
      services[idx] = { ...services[idx], [field]: value }
      return { ...prev, services }
    })
  }

  function addService() {
    setEdited(true)
    setDetail(prev => ({
      ...prev,
      services: [...(prev.services || []), {
        id: null,
        original_description: '',
        standardized_description: '',
        category: '',
        amount: 0,
        service_type: 'labor',
      }],
    }))
  }

  function removeService(idx) {
    setEdited(true)
    setDetail(prev => ({
      ...prev,
      services: (prev.services || []).filter((_, i) => i !== idx),
    }))
  }

  // Computed totals
  const totalLabor     = (detail?.services || []).filter(s => s.service_type === 'labor').reduce((s, i) => s + (parseFloat(i.amount) || 0), 0)
  const totalMaterials = (detail?.services || []).filter(s => s.service_type !== 'labor').reduce((s, i) => s + (parseFloat(i.amount) || 0), 0)
  const totalHours     = (detail?.time_entries || []).reduce((s, t) => s + (t.hours || 0), 0)

  // ── Category options for dropdown ────────────────────────────
  const catOptions = categories.map(c => c.name).sort()

  // ─────────────────────────────────────────────────────────────
  return (
    <div className="flex h-full gap-0 -m-6">

      {/* ══ LEFT SIDEBAR ══════════════════════════════════════════ */}
      <div className="w-72 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-lg font-bold text-gray-900">Filing Cabinet</h1>
            <Link
              to="/estimate"
              className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 font-medium"
            >
              + New
            </Link>
          </div>
          <input
            type="text"
            placeholder="Search customer or invoice..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-2"
          />
          <div className="flex gap-1">
            {['all', 'estimate', 'completed'].map(s => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`flex-1 py-1 text-xs rounded-md font-medium transition-colors ${
                  statusFilter === s ? 'bg-blue-100 text-blue-700' : 'text-gray-500 hover:bg-gray-100'
                }`}
              >
                {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-y-auto flex-1">
          {loading && <div className="p-4 text-gray-400 text-sm text-center">Loading...</div>}
          {filtered.map(job => {
            const isSelected = selectedId === job.job_id
            return (
              <button
                key={job.job_id}
                onClick={() => setSelectedId(job.job_id)}
                className={`w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors ${
                  isSelected ? 'bg-blue-50 border-l-4 border-l-blue-500' : ''
                }`}
              >
                <div className="flex items-center justify-between mb-0.5">
                  <div className="font-medium text-gray-900 text-sm truncate flex-1 mr-2">
                    {job.customer || 'Unknown'}
                  </div>
                  <StatusBadge status={job.status} />
                </div>
                <div className="flex items-center justify-between">
                  <div className="text-xs text-gray-500">{job.invoice_number || `#${job.job_id}`}</div>
                  <div className="text-xs font-semibold text-gray-700">{fmt(job.total_amount)}</div>
                </div>
                <div className="flex items-center justify-between mt-0.5">
                  <div className="text-xs text-gray-400">{job.start_date || ''}</div>
                  {job.total_hours > 0 && (
                    <div className="text-xs text-gray-400">{fmtHours(job.total_hours)}</div>
                  )}
                </div>
              </button>
            )
          })}
          {!loading && filtered.length === 0 && (
            <div className="p-6 text-center text-gray-400 text-sm">No jobs found</div>
          )}
        </div>

        <div className="p-3 border-t border-gray-100 text-xs text-gray-400 text-center">
          {filtered.length} of {jobs.length} jobs
        </div>
      </div>

      {/* ══ RIGHT DOSSIER PANEL ═══════════════════════════════════ */}
      <div className="flex-1 overflow-y-auto bg-gray-50">

        {/* Empty state */}
        {!selectedId && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <div className="text-5xl mb-4">🗂</div>
            <div className="text-xl font-medium">Select a job</div>
            <div className="text-sm mt-1">or create a new estimate</div>
          </div>
        )}

        {selectedId && detailLoading && (
          <div className="flex items-center justify-center h-64 text-gray-400">Loading...</div>
        )}

        {selectedId && detail && !detailLoading && (
          <div className="p-6 space-y-4 max-w-4xl">

            {/* ── TOOLBAR ────────────────────────────────────────── */}
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">{detail.customer_name}</h2>
                <div className="text-sm text-gray-500 mt-0.5 flex items-center gap-2">
                  <span className="font-mono">{detail.invoice_number}</span>
                  <span>·</span>
                  <span>{detail.invoice_date || detail.start_date}</span>
                  <span>·</span>
                  <StatusBadge status={detail.status} />
                </div>
              </div>
              <div className="flex gap-2 flex-shrink-0">
                {detail.status === 'estimate' && (
                  <button
                    onClick={handleConvert}
                    disabled={converting}
                    className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50 font-medium"
                  >
                    {converting ? 'Converting...' : 'Mark as Paid'}
                  </button>
                )}
                <Link
                  to={`/print/${detail.job_id}`}
                  className="bg-white border border-gray-200 text-gray-700 px-4 py-2 rounded-lg text-sm hover:bg-gray-50 font-medium"
                >
                  Print
                </Link>
                {edited && (
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 font-medium"
                  >
                    {saving ? 'Saving...' : 'Save Changes'}
                  </button>
                )}
              </div>
            </div>

            {/* ── CUSTOMER CARD ──────────────────────────────────── */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Customer</h3>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Name</label>
                  <input
                    type="text"
                    value={detail.customer_name || ''}
                    onChange={e => setField('customer_name', e.target.value)}
                    className={INPUT}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Phone</label>
                  <input
                    type="text"
                    value={detail.customer_phone || ''}
                    onChange={e => setField('customer_phone', e.target.value)}
                    placeholder="(870) 555-1234"
                    className={INPUT}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Email</label>
                  <input
                    type="email"
                    value={detail.customer_email || ''}
                    onChange={e => setField('customer_email', e.target.value)}
                    placeholder="email@example.com"
                    className={INPUT}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Address</label>
                  <input
                    type="text"
                    value={detail.customer_address || ''}
                    onChange={e => setField('customer_address', e.target.value)}
                    placeholder="123 Main St, Mountain Home AR 72653"
                    className={INPUT}
                  />
                </div>
              </div>
            </div>

            {/* ── INVOICE DETAILS ────────────────────────────────── */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Invoice Details</h3>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Invoice #</label>
                  <input
                    type="text"
                    value={detail.invoice_number || ''}
                    readOnly
                    className={`${INPUT} bg-gray-50 text-gray-500 cursor-default`}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Date</label>
                  <input
                    type="date"
                    value={detail.invoice_date || detail.start_date || ''}
                    onChange={e => setField('invoice_date', e.target.value)}
                    className={INPUT}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Status</label>
                  <select
                    value={detail.status || 'completed'}
                    onChange={e => setField('status', e.target.value)}
                    className={INPUT}
                  >
                    <option value="estimate">Estimate</option>
                    <option value="pending">Pending</option>
                    <option value="completed">Completed</option>
                    <option value="paid">Paid</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Estimated days on site</label>
                  <input
                    type="number"
                    min="1"
                    max="60"
                    value={detail.estimated_days || ''}
                    onChange={e => setField('estimated_days', e.target.value ? parseInt(e.target.value) : null)}
                    placeholder="Your guess"
                    className={INPUT}
                  />
                </div>
                <div className="col-span-3">
                  <label className="block text-xs text-gray-400 mb-1">Notes</label>
                  <textarea
                    rows={2}
                    value={detail.notes || ''}
                    onChange={e => setField('notes', e.target.value)}
                    placeholder="Job notes..."
                    className={INPUT}
                  />
                </div>
              </div>
            </div>

            {/* ── SERVICES TABLE ─────────────────────────────────── */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Services &amp; Line Items
                </h3>
                <button
                  onClick={addService}
                  className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                >
                  + Add Line
                </button>
              </div>

              {/* Column headers */}
              <div className="grid gap-2 px-5 py-2 text-xs text-gray-400 font-medium bg-gray-50 border-b border-gray-100"
                   style={{gridTemplateColumns: '3fr 2fr 90px 80px 28px'}}>
                <div>Description</div>
                <div>Category</div>
                <div>Type</div>
                <div className="text-right">Amount</div>
                <div></div>
              </div>

              <div className="divide-y divide-gray-50">
                {(detail.services || []).map((svc, idx) => (
                  <div key={idx}
                       className="grid gap-2 px-5 py-2 items-center"
                       style={{gridTemplateColumns: '3fr 2fr 90px 80px 28px'}}>
                    <input
                      type="text"
                      value={svc.standardized_description || svc.original_description || ''}
                      onChange={e => {
                        updateService(idx, 'standardized_description', e.target.value)
                        updateService(idx, 'original_description', e.target.value)
                      }}
                      placeholder="Service description"
                      className={INPUT_SM}
                    />
                    <select
                      value={svc.category || ''}
                      onChange={e => updateService(idx, 'category', e.target.value)}
                      className={INPUT_SM}
                    >
                      <option value="">-- category --</option>
                      {catOptions.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <select
                      value={svc.service_type || 'labor'}
                      onChange={e => updateService(idx, 'service_type', e.target.value)}
                      className={INPUT_SM}
                    >
                      <option value="labor">Labor</option>
                      <option value="materials">Materials</option>
                    </select>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={svc.amount || ''}
                      onChange={e => updateService(idx, 'amount', parseFloat(e.target.value) || 0)}
                      className={`${INPUT_SM} text-right`}
                    />
                    <button
                      onClick={() => removeService(idx)}
                      className="text-gray-300 hover:text-red-500 text-xl leading-none font-light text-center"
                    >
                      ×
                    </button>
                  </div>
                ))}
                {(!detail.services || detail.services.length === 0) && (
                  <div className="px-5 py-6 text-center text-gray-400 text-sm">
                    No services —{' '}
                    <button onClick={addService} className="text-blue-600 hover:underline">add one</button>
                  </div>
                )}
              </div>

              {/* Totals footer */}
              <div className="border-t border-gray-200 px-5 py-4 bg-gray-50">
                <div className="flex justify-end">
                  <div className="space-y-1 text-sm min-w-52">
                    <div className="flex justify-between text-gray-600">
                      <span>Labor</span>
                      <span className="tabular-nums">{fmt(totalLabor)}</span>
                    </div>
                    {totalMaterials > 0 && (
                      <div className="flex justify-between text-gray-500">
                        <span>Materials (passthrough)</span>
                        <span className="tabular-nums">{fmt(totalMaterials)}</span>
                      </div>
                    )}
                    <div className="flex justify-between font-bold text-gray-900 text-base pt-1 border-t border-gray-200">
                      <span>Total</span>
                      <span className="tabular-nums">{fmt(totalLabor + totalMaterials)}</span>
                    </div>
                    {totalHours > 0 && totalLabor > 0 && (
                      <div className="flex justify-between text-xs text-gray-400 pt-1">
                        <span>{fmtHours(totalHours)} logged</span>
                        <span>{fmt(totalLabor / totalHours)}/hr</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* ── DAYS ON SITE + TIME ENTRIES ────────────────────── */}
            {(detail.time_entries?.length > 0 || detail.unlinked_time_entries?.length > 0) && (
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">

                {/* Header with days comparison */}
                <div className="px-5 py-3 border-b border-gray-100">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      Time on Site
                    </h3>
                    <div className="flex items-center gap-4 text-sm">
                      {totalHours > 0 && (
                        <span className="text-gray-500">{fmtHours(totalHours)} total</span>
                      )}
                      {detail.actual_days > 0 && totalHours > 0 && (
                        <span className="text-gray-400 text-xs">
                          {(totalHours / detail.actual_days).toFixed(1)}h/day avg
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Estimated vs Actual pill */}
                  {(detail.actual_days > 0 || detail.estimated_days) && (
                    <DaysComparison
                      estimated={detail.estimated_days}
                      actual={detail.actual_days}
                    />
                  )}
                </div>

                {/* Day-by-day breakdown */}
                {detail.days_on_site?.length > 0 && (
                  <div className="px-5 py-3 border-b border-gray-100 bg-gray-50">
                    <div className="flex flex-wrap gap-2">
                      {detail.days_on_site.map((day, i) => (
                        <div key={day.date} className="flex items-center gap-1.5 bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-xs">
                          <span className="font-semibold text-gray-500">Day {i + 1}</span>
                          <span className="text-gray-400">·</span>
                          <span className="text-gray-700">{day.date}</span>
                          <span className="text-gray-400">·</span>
                          <span className="font-medium text-gray-800">{day.hours.toFixed(1)}h</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Linked entries */}
                {detail.time_entries?.length > 0 && (
                  <div className="divide-y divide-gray-50">
                    {detail.time_entries.map(t => (
                      <TimeEntryRow
                        key={t.id}
                        entry={t}
                        customerJobs={detail.customer_jobs}
                        currentJobId={detail.job_id}
                        onReassign={handleReassign}
                      />
                    ))}
                  </div>
                )}

                {/* Unlinked entries for this customer */}
                {detail.unlinked_time_entries?.length > 0 && (
                  <>
                    <div className="px-5 py-2 bg-amber-50 border-t border-amber-100">
                      <span className="text-xs font-medium text-amber-700">
                        {detail.unlinked_time_entries.length} unlinked {detail.unlinked_time_entries.length === 1 ? 'entry' : 'entries'} for this customer
                        {(detail.customer_jobs?.length ?? 0) > 1
                          ? ' — use the dropdown to assign'
                          : ' — click Claim to attach'}
                      </span>
                    </div>
                    <div className="divide-y divide-gray-50">
                      {detail.unlinked_time_entries.map(t => (
                        <TimeEntryRow
                          key={t.id}
                          entry={t}
                          unlinked
                          onClaim={() => handleClaim(t.id)}
                          customerJobs={detail.customer_jobs}
                          currentJobId={detail.job_id}
                          onReassign={handleReassign}
                        />
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}

          </div>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Days Comparison: Estimated vs Actual
// ─────────────────────────────────────────────────────────────────
function DaysComparison({ estimated, actual }) {
  if (!estimated && !actual) return null

  const diff = actual && estimated ? actual - estimated : null
  const onTime = diff !== null && diff <= 0
  const over = diff !== null && diff > 0
  const noEstimate = !estimated && actual > 0

  return (
    <div className="flex items-center gap-3 mt-2 flex-wrap">
      {estimated && (
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-gray-400">Estimated:</span>
          <span className="font-semibold text-gray-700">{estimated} day{estimated !== 1 ? 's' : ''}</span>
        </div>
      )}
      {actual > 0 && (
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-gray-400">Actual:</span>
          <span className="font-semibold text-gray-700">{actual} day{actual !== 1 ? 's' : ''}</span>
        </div>
      )}
      {diff !== null && (
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
          onTime ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
        }`}>
          {onTime ? (diff === 0 ? 'On estimate' : `${Math.abs(diff)} day${Math.abs(diff) !== 1 ? 's' : ''} under`) : `${diff} day${diff !== 1 ? 's' : ''} over`}
        </span>
      )}
      {noEstimate && (
        <span className="text-xs text-gray-400 italic">No estimate was set</span>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Time Entry Row
// ─────────────────────────────────────────────────────────────────
function TimeEntryRow({ entry, unlinked, onClaim, customerJobs, currentJobId, onReassign }) {
  const startTime = fmtTime(entry.start_time)
  const endTime   = fmtTime(entry.end_time)
  const timeRange = startTime && endTime ? `${startTime} – ${endTime}` : null
  const multiJob  = customerJobs && customerJobs.length > 1

  return (
    <div className={`px-5 py-3 flex items-center justify-between gap-4 ${unlinked ? 'bg-amber-50/40' : ''}`}>
      <div className="flex-1 min-w-0">
        <div className="text-sm text-gray-800 truncate">
          {entry.description || 'No description'}
        </div>
        <div className="text-xs text-gray-400 mt-0.5 flex items-center gap-2 flex-wrap">
          <span>{entry.entry_date}</span>
          {timeRange && <span>{timeRange}</span>}
          {entry.cost_code && (
            <span className="bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded text-xs">
              {entry.cost_code}
            </span>
          )}
          <span className={`px-1.5 py-0.5 rounded text-xs ${
            entry.source === 'busybusy' ? 'bg-purple-100 text-purple-600' : 'bg-gray-100 text-gray-500'
          }`}>
            {entry.source || 'manual'}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <div className="text-sm font-semibold text-gray-700 tabular-nums">
          {(entry.hours || 0).toFixed(2)}h
        </div>

        {/* Invoice reassignment dropdown — appears when customer has multiple jobs */}
        {multiJob && onReassign && (
          <select
            value={unlinked ? '' : String(currentJobId)}
            onChange={e => e.target.value !== '' && onReassign(entry.id, parseInt(e.target.value))}
            className="text-xs border border-gray-200 rounded px-1.5 py-1 text-gray-500 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400 max-w-36"
            title="Move to a different invoice"
          >
            {unlinked && <option value="">— assign to —</option>}
            {customerJobs.map(j => (
              <option key={j.job_id} value={String(j.job_id)}>
                {j.invoice_number}
              </option>
            ))}
          </select>
        )}

        {/* Claim button — only for unlinked entries when customer has just one job */}
        {unlinked && !multiJob && onClaim && (
          <button
            onClick={onClaim}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium border border-blue-200 rounded px-2 py-1 hover:bg-blue-50"
          >
            Claim
          </button>
        )}
      </div>
    </div>
  )
}
