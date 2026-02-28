import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

const EMPTY_SERVICE = () => ({
  original_description: '',
  standardized_description: '',
  category: '',
  service_type: 'labor',
  amount: '',
})

const INPUT = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'
const INPUT_SM = 'w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500'
const fmt = n => `$${(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export default function Estimate() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [customers, setCustomers]   = useState([])
  const [categories, setCategories] = useState([])
  const [pricingHints, setPricingHints] = useState({})  // category -> {avg_price, avg_days, ...}
  const [saving, setSaving]         = useState(false)

  const [form, setForm] = useState({
    customer_id:    searchParams.get('customer') || '',
    invoice_number: '',
    start_date:     new Date().toISOString().slice(0, 10),
    status:         'estimate',
    estimated_days: '',
    notes:          '',
    services:       [EMPTY_SERVICE()],
  })

  useEffect(() => {
    Promise.all([
      fetch('/api/customers').then(r => r.json()),
      fetch('/api/service-categories').then(r => r.json()),
      fetch('/api/pricing/suggest-all').then(r => r.json()),
    ]).then(([custData, catData, priceData]) => {
      setCustomers((Array.isArray(custData) ? custData : []).filter(c => !c.name.startsWith('_')))
      setCategories(Array.isArray(catData) ? catData : [])
      setPricingHints(priceData || {})
    })
  }, [])

  function updateForm(field, value) {
    setForm(f => ({ ...f, [field]: value }))
  }

  function updateService(idx, field, value) {
    setForm(f => {
      const services = [...f.services]
      services[idx] = { ...services[idx], [field]: value }
      // When category changes, auto-suggest price and days if not already filled
      if (field === 'category' && value && pricingHints[value]) {
        const hint = pricingHints[value]
        if (!services[idx].amount) {
          services[idx].amount = hint.avg_price || ''
        }
      }
      return { ...f, services }
    })
  }

  function addService() {
    setForm(f => ({ ...f, services: [...f.services, EMPTY_SERVICE()] }))
  }

  function removeService(idx) {
    if (form.services.length === 1) return
    setForm(f => ({ ...f, services: f.services.filter((_, i) => i !== idx) }))
  }

  // Auto-suggest estimated days based on selected categories
  function suggestDays() {
    const dayHints = form.services
      .map(s => pricingHints[s.category]?.avg_days)
      .filter(Boolean)
    if (dayHints.length === 0) return null
    return Math.ceil(Math.max(...dayHints))
  }

  async function handleSave(andConvert = false) {
    if (!form.customer_id) {
      alert('Please select a customer.')
      return
    }
    const services = form.services.filter(s => s.original_description.trim())
    if (services.length === 0) {
      alert('Add at least one service line item.')
      return
    }

    setSaving(true)
    try {
      const payload = {
        customer_id:    parseInt(form.customer_id),
        invoice_number: form.invoice_number || undefined,
        start_date:     form.start_date,
        status:         andConvert ? 'completed' : 'estimate',
        notes:          form.notes,
        estimated_days: form.estimated_days ? parseInt(form.estimated_days) : null,
        services: services.map(s => ({
          original_description:     s.original_description,
          standardized_description: s.original_description,
          category:                 s.category,
          service_type:             s.service_type,
          amount:                   parseFloat(s.amount) || 0,
        })),
      }

      const r = await fetch('/api/filing-cabinet/new', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      })

      if (!r.ok) throw new Error((await r.json()).error || 'Save failed')
      const saved = await r.json()
      navigate(`/filing-cabinet?job=${saved.job_id}`)
    } catch (e) {
      alert('Error saving: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  const totalLabor     = form.services.filter(s => s.service_type === 'labor').reduce((s, i) => s + (parseFloat(i.amount) || 0), 0)
  const totalMaterials = form.services.filter(s => s.service_type !== 'labor').reduce((s, i) => s + (parseFloat(i.amount) || 0), 0)
  const daySuggestion  = suggestDays()

  return (
    <div className="max-w-4xl mx-auto space-y-5 pb-10">

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">New Estimate</h1>
        <div className="flex gap-3">
          <button
            onClick={() => handleSave(false)}
            disabled={saving}
            className="bg-white border border-gray-200 text-gray-700 px-4 py-2 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50 font-medium"
          >
            {saving ? 'Saving...' : 'Save as Estimate'}
          </button>
          <button
            onClick={() => handleSave(true)}
            disabled={saving}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 font-medium"
          >
            Save as Invoice
          </button>
        </div>
      </div>

      {/* Customer + Job Info */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-4">Job Information</h2>
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2 md:col-span-1">
            <label className="block text-xs text-gray-500 mb-1">Customer *</label>
            <select
              value={form.customer_id}
              onChange={e => updateForm('customer_id', e.target.value)}
              className={INPUT}
            >
              <option value="">Select customer...</option>
              {customers.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">Date</label>
            <input
              type="date"
              value={form.start_date}
              onChange={e => updateForm('start_date', e.target.value)}
              className={INPUT}
            />
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">Invoice/Estimate # (optional)</label>
            <input
              type="text"
              value={form.invoice_number}
              onChange={e => updateForm('invoice_number', e.target.value)}
              placeholder="e.g. BHS20260224"
              className={INPUT}
            />
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">
              Estimated days on site
              {daySuggestion && !form.estimated_days && (
                <button
                  onClick={() => updateForm('estimated_days', String(daySuggestion))}
                  className="ml-2 text-blue-600 hover:underline font-normal"
                >
                  Suggest: {daySuggestion} day{daySuggestion !== 1 ? 's' : ''}
                </button>
              )}
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="1"
                max="60"
                value={form.estimated_days}
                onChange={e => updateForm('estimated_days', e.target.value)}
                placeholder="Your guess..."
                className={INPUT}
              />
              {form.estimated_days && (
                <span className="text-xs text-gray-400 whitespace-nowrap">
                  {form.estimated_days} day{form.estimated_days !== '1' ? 's' : ''}
                </span>
              )}
            </div>
          </div>

          <div className="col-span-2">
            <label className="block text-xs text-gray-500 mb-1">Notes</label>
            <textarea
              rows={2}
              value={form.notes}
              onChange={e => updateForm('notes', e.target.value)}
              placeholder="Job notes, special instructions..."
              className={INPUT}
            />
          </div>
        </div>
      </div>

      {/* Line Items */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Services &amp; Line Items</h2>
          <button onClick={addService} className="text-xs text-blue-600 hover:text-blue-800 font-medium">
            + Add Line
          </button>
        </div>

        {/* Headers */}
        <div className="grid gap-2 px-5 py-2 text-xs text-gray-400 font-medium bg-gray-50 border-b border-gray-100"
             style={{gridTemplateColumns: '3fr 2fr 90px 80px 28px'}}>
          <div>Description</div>
          <div>Category</div>
          <div>Type</div>
          <div className="text-right">Amount</div>
          <div></div>
        </div>

        <div className="divide-y divide-gray-50">
          {form.services.map((svc, idx) => {
            const hint = pricingHints[svc.category]
            return (
              <div key={idx}>
                <div className="grid gap-2 px-5 py-2 items-center"
                     style={{gridTemplateColumns: '3fr 2fr 90px 80px 28px'}}>
                  <input
                    type="text"
                    value={svc.original_description}
                    onChange={e => updateService(idx, 'original_description', e.target.value)}
                    placeholder="What was done?"
                    className={INPUT_SM}
                  />
                  <select
                    value={svc.category}
                    onChange={e => updateService(idx, 'category', e.target.value)}
                    className={INPUT_SM}
                  >
                    <option value="">Category...</option>
                    {categories.map(c => (
                      <option key={c.id} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                  <select
                    value={svc.service_type}
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
                    value={svc.amount}
                    onChange={e => updateService(idx, 'amount', e.target.value)}
                    placeholder="0.00"
                    className={`${INPUT_SM} text-right`}
                  />
                  <button
                    onClick={() => removeService(idx)}
                    className="text-gray-300 hover:text-red-500 text-xl leading-none font-light text-center"
                  >
                    ×
                  </button>
                </div>
                {/* Pricing hint row */}
                {hint && svc.service_type === 'labor' && (
                  <div className="px-5 pb-2 flex items-center gap-3 text-xs text-gray-400">
                    <span>Historical avg:</span>
                    <button
                      onClick={() => updateService(idx, 'amount', hint.avg_price)}
                      className="text-blue-500 hover:text-blue-700 font-medium"
                    >
                      {fmt(hint.avg_price)} avg
                    </button>
                    <span className="text-gray-300">|</span>
                    <span>{fmt(hint.min_price)} – {fmt(hint.max_price)}</span>
                    <span className="text-gray-300">|</span>
                    <span>{hint.job_count} past job{hint.job_count !== 1 ? 's' : ''}</span>
                    {hint.avg_days && (
                      <>
                        <span className="text-gray-300">|</span>
                        <span>~{hint.avg_days} day{hint.avg_days !== 1 ? 's' : ''} on site</span>
                      </>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Totals */}
        <div className="border-t border-gray-200 px-5 py-4 bg-gray-50">
          <div className="flex justify-end">
            <div className="w-56 space-y-1.5 text-sm">
              {totalLabor > 0 && (
                <div className="flex justify-between text-gray-600">
                  <span>Labor</span>
                  <span className="font-medium tabular-nums">{fmt(totalLabor)}</span>
                </div>
              )}
              {totalMaterials > 0 && (
                <div className="flex justify-between text-gray-500">
                  <span>Materials</span>
                  <span className="font-medium tabular-nums">{fmt(totalMaterials)}</span>
                </div>
              )}
              <div className="flex justify-between font-bold text-gray-900 text-base pt-1.5 border-t border-gray-300">
                <span>Total</span>
                <span className="tabular-nums">{fmt(totalLabor + totalMaterials)}</span>
              </div>
              {form.estimated_days && (
                <div className="flex justify-between text-xs text-gray-400 pt-1">
                  <span>Est. days on site</span>
                  <span>{form.estimated_days} day{form.estimated_days !== '1' ? 's' : ''}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom actions */}
      <div className="flex justify-end gap-3">
        <button
          onClick={() => handleSave(false)}
          disabled={saving}
          className="bg-white border border-gray-200 text-gray-700 px-6 py-2.5 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50 font-medium"
        >
          Save as Estimate
        </button>
        <button
          onClick={() => handleSave(true)}
          disabled={saving}
          className="bg-blue-600 text-white px-6 py-2.5 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 font-medium"
        >
          Save as Invoice
        </button>
      </div>
    </div>
  )
}
