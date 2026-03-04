import { useState, useEffect } from 'react'

const fmt = n => `$${(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const INPUT = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white'

const PAYMENT_METHODS = ['Cash', 'Check', 'Credit Card', 'Debit Card', 'Venmo', 'Zelle', 'PayPal', 'Account/Net30', 'Other']

const EMPTY_FORM = () => ({
  description: '',
  cost: '',
  vendor: '',
  expense_date: new Date().toISOString().slice(0, 10),
  expense_category: 'Materials & Supplies',
  is_overhead: false,
  job_id: '',
  payment_method: '',
  notes: '',
})

export default function Expenses() {
  const [expenses, setExpenses]     = useState([])
  const [categories, setCategories] = useState([])
  const [jobs, setJobs]             = useState([])
  const [summary, setSummary]       = useState(null)
  const [loading, setLoading]       = useState(true)
  const [saving, setSaving]         = useState(false)

  const [showForm, setShowForm]     = useState(false)
  const [form, setForm]             = useState(EMPTY_FORM())
  const [editId, setEditId]         = useState(null)

  // Filters
  const [filterCat, setFilterCat]   = useState('')
  const [filterType, setFilterType] = useState('all') // all | overhead | job
  const [search, setSearch]         = useState('')
  const [dateFrom, setDateFrom]     = useState('')
  const [dateTo, setDateTo]         = useState('')

  useEffect(() => {
    Promise.all([
      fetch('/api/expenses/categories').then(r => r.json()),
      fetch('/api/jobs').then(r => r.json()),
    ]).then(([cats, jobsData]) => {
      setCategories(cats || [])
      setJobs(Array.isArray(jobsData) ? jobsData : [])
    })
    loadExpenses()
  }, [])

  async function loadExpenses() {
    setLoading(true)
    try {
      const [expData, sumData] = await Promise.all([
        fetch('/api/expenses').then(r => r.json()),
        fetch('/api/expenses/summary').then(r => r.json()),
      ])
      setExpenses(expData || [])
      setSummary(sumData || null)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!form.description.trim() || !form.cost) return
    setSaving(true)
    try {
      const url    = editId ? `/api/expenses/${editId}` : '/api/expenses'
      const method = editId ? 'PUT' : 'POST'
      const r = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...form,
          cost:        parseFloat(form.cost),
          is_overhead: form.is_overhead || !form.job_id,
          job_id:      form.job_id ? parseInt(form.job_id) : null,
        }),
      })
      if (!r.ok) throw new Error((await r.json()).error || 'Failed')
      setForm(EMPTY_FORM())
      setEditId(null)
      setShowForm(false)
      await loadExpenses()
    } catch (e) {
      alert('Error saving: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id) {
    if (!confirm('Delete this expense?')) return
    await fetch(`/api/expenses/${id}`, { method: 'DELETE' })
    await loadExpenses()
  }

  function startEdit(exp) {
    setForm({
      description:      exp.description || '',
      cost:             String(exp.cost || ''),
      vendor:           exp.vendor || '',
      expense_date:     exp.expense_date || new Date().toISOString().slice(0, 10),
      expense_category: exp.expense_category || 'Materials & Supplies',
      is_overhead:      !!exp.is_overhead,
      job_id:           exp.job_id ? String(exp.job_id) : '',
      payment_method:   exp.payment_method || '',
      notes:            exp.notes || '',
    })
    setEditId(exp.id)
    setShowForm(true)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Filtered list
  const filtered = expenses.filter(e => {
    if (filterCat && e.expense_category !== filterCat) return false
    if (filterType === 'overhead' && !e.is_overhead) return false
    if (filterType === 'job' && e.is_overhead) return false
    if (search) {
      const q = search.toLowerCase()
      if (!(e.description || '').toLowerCase().includes(q) &&
          !(e.vendor || '').toLowerCase().includes(q) &&
          !(e.customer_name || '').toLowerCase().includes(q)) return false
    }
    if (dateFrom && e.expense_date < dateFrom) return false
    if (dateTo && e.expense_date > dateTo) return false
    return true
  })

  const filteredTotal = filtered.reduce((s, e) => s + (e.cost || 0), 0)

  return (
    <div className="max-w-5xl mx-auto space-y-5 pb-10">

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Expenses</h1>
        <button
          onClick={() => { setForm(EMPTY_FORM()); setEditId(null); setShowForm(v => !v) }}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 font-medium"
        >
          {showForm && !editId ? '✕ Cancel' : '+ Add Expense'}
        </button>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <div className="text-xl font-bold text-gray-900">{fmt(summary.totals?.total_expenses)}</div>
            <div className="text-xs text-gray-500 mt-1">Total Expenses</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <div className="text-xl font-bold text-orange-600">{fmt(summary.totals?.total_overhead)}</div>
            <div className="text-xs text-gray-500 mt-1">Business Overhead</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <div className="text-xl font-bold text-blue-600">{fmt(summary.totals?.total_job_costs)}</div>
            <div className="text-xs text-gray-500 mt-1">Job-Specific Costs</div>
          </div>
        </div>
      )}

      {/* Add / Edit Form */}
      {showForm && (
        <div className="bg-white rounded-xl border border-blue-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            {editId ? 'Edit Expense' : 'New Expense'}
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-1">Description *</label>
              <input
                type="text"
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                placeholder="What was purchased or paid for?"
                className={INPUT}
                autoFocus
              />
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Category *</label>
              <select
                value={form.expense_category}
                onChange={e => setForm(f => ({ ...f, expense_category: e.target.value }))}
                className={INPUT}
              >
                {categories.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Amount *</label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.cost}
                  onChange={e => setForm(f => ({ ...f, cost: e.target.value }))}
                  placeholder="0.00"
                  className={`${INPUT} pl-7`}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Date</label>
              <input
                type="date"
                value={form.expense_date}
                onChange={e => setForm(f => ({ ...f, expense_date: e.target.value }))}
                className={INPUT}
              />
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Vendor / Paid To</label>
              <input
                type="text"
                value={form.vendor}
                onChange={e => setForm(f => ({ ...f, vendor: e.target.value }))}
                placeholder="Home Depot, Shell, etc."
                className={INPUT}
              />
            </div>

            {/* Overhead toggle */}
            <div className="col-span-2">
              <div className="flex items-center gap-6">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="exptype"
                    checked={!form.is_overhead && !form.job_id}
                    onChange={() => setForm(f => ({ ...f, is_overhead: false }))}
                  />
                  <span className="text-sm text-gray-700">Job-Specific Cost</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="exptype"
                    checked={!!form.is_overhead}
                    onChange={() => setForm(f => ({ ...f, is_overhead: true, job_id: '' }))}
                  />
                  <span className="text-sm text-gray-700">Business Overhead (not tied to a job)</span>
                </label>
              </div>
            </div>

            {/* Job selector — only if job-specific */}
            {!form.is_overhead && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">Assign to Job (optional)</label>
                <select
                  value={form.job_id}
                  onChange={e => setForm(f => ({ ...f, job_id: e.target.value }))}
                  className={INPUT}
                >
                  <option value="">-- select job --</option>
                  {jobs.map(j => (
                    <option key={j.id} value={j.id}>
                      {j.customer} — {j.invoice_id || `#${j.id}`} ({j.start_date})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="block text-xs text-gray-500 mb-1">Payment Method</label>
              <select
                value={form.payment_method}
                onChange={e => setForm(f => ({ ...f, payment_method: e.target.value }))}
                className={INPUT}
              >
                <option value="">-- select --</option>
                {PAYMENT_METHODS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>

            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-1">Notes</label>
              <input
                type="text"
                value={form.notes}
                onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                placeholder="Receipt #, project notes..."
                className={INPUT}
              />
            </div>
          </div>

          <div className="flex gap-3 mt-4">
            <button
              onClick={handleSave}
              disabled={saving || !form.description.trim() || !form.cost}
              className="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 font-medium"
            >
              {saving ? 'Saving...' : editId ? 'Save Changes' : 'Save Expense'}
            </button>
            <button
              onClick={() => { setForm(EMPTY_FORM()); setEditId(null); setShowForm(false) }}
              className="text-gray-600 px-4 py-2 rounded-lg text-sm hover:bg-gray-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <input
            type="text"
            placeholder="Search description, vendor..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className={INPUT}
          />
          <select value={filterCat} onChange={e => setFilterCat(e.target.value)} className={INPUT}>
            <option value="">All Categories</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={filterType} onChange={e => setFilterType(e.target.value)} className={INPUT}>
            <option value="all">All Types</option>
            <option value="overhead">Business Overhead</option>
            <option value="job">Job Costs</option>
          </select>
          <div className="flex gap-2">
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className={INPUT} title="From date" />
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className={INPUT} title="To date" />
          </div>
        </div>
      </div>

      {/* Category breakdown (mini chart) */}
      {summary?.by_category?.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-4">By Category</h3>
          <div className="space-y-2">
            {summary.by_category.map(cat => {
              const pct = summary.totals?.total_expenses > 0
                ? (cat.grand_total / summary.totals.total_expenses) * 100
                : 0
              return (
                <div key={cat.expense_category} className="flex items-center gap-3">
                  <div className="text-xs text-gray-600 w-48 truncate">{cat.expense_category}</div>
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-2 bg-blue-400 rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="text-xs font-semibold text-gray-700 w-20 text-right">{fmt(cat.grand_total)}</div>
                  <div className="text-xs text-gray-400 w-16 text-right">{cat.count} item{cat.count !== 1 ? 's' : ''}</div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Expense list */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Expense Records
          </h3>
          <div className="text-sm font-semibold text-gray-700">
            {filtered.length} items · {fmt(filteredTotal)}
          </div>
        </div>

        {loading && <div className="p-6 text-center text-gray-400 text-sm">Loading...</div>}

        {!loading && filtered.length === 0 && (
          <div className="p-8 text-center text-gray-400 text-sm">
            No expenses found. Click "+ Add Expense" to record one.
          </div>
        )}

        <div className="divide-y divide-gray-50">
          {filtered.map(exp => (
            <div key={exp.id} className="px-5 py-3 flex items-start justify-between gap-3 hover:bg-gray-50">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-gray-900">{exp.description}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                    exp.is_overhead
                      ? 'bg-orange-100 text-orange-700'
                      : 'bg-blue-100 text-blue-700'
                  }`}>
                    {exp.is_overhead ? 'Overhead' : 'Job Cost'}
                  </span>
                  {exp.expense_category && (
                    <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                      {exp.expense_category}
                    </span>
                  )}
                </div>
                <div className="text-xs text-gray-400 mt-0.5 flex items-center gap-2 flex-wrap">
                  <span>{exp.expense_date}</span>
                  {exp.vendor && <><span>·</span><span>{exp.vendor}</span></>}
                  {exp.payment_method && <><span>·</span><span>{exp.payment_method}</span></>}
                  {exp.invoice_number && <><span>·</span><span className="text-blue-500">{exp.invoice_number}</span></>}
                  {exp.customer_name && !exp.is_overhead && <><span>·</span><span>{exp.customer_name}</span></>}
                  {exp.notes && <><span>·</span><span className="italic">{exp.notes}</span></>}
                </div>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <div className="text-sm font-semibold text-gray-800 tabular-nums">{fmt(exp.cost)}</div>
                <button
                  onClick={() => startEdit(exp)}
                  className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDelete(exp.id)}
                  className="text-gray-300 hover:text-red-500 text-lg leading-none"
                >
                  ×
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
