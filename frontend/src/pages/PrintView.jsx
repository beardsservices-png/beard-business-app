import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'

export default function PrintView() {
  const { jobId } = useParams()
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const printRef = useRef(null)

  useEffect(() => {
    fetch(`/api/filing-cabinet/${jobId}`)
      .then(r => r.json())
      .then(data => { setJob(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [jobId])

  function handlePrint() {
    window.print()
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-500">Loading...</div>
  )
  if (error) return (
    <div className="text-red-600 p-6">Error: {error}</div>
  )
  if (!job) return (
    <div className="text-gray-500 p-6">Job not found</div>
  )

  const fmt = (n) => `$${(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  const isEstimate = job.status === 'estimate'
  const docType = isEstimate ? 'ESTIMATE' : 'INVOICE'
  const docNumber = job.invoice_id || `JOB-${job.id}`

  const services = job.services || []
  const laborLines = services.filter(s => s.service_type === 'labor')
  const materialLines = services.filter(s => s.service_type !== 'labor')
  const totalLabor = laborLines.reduce((s, i) => s + (parseFloat(i.amount) || 0), 0)
  const totalMaterials = materialLines.reduce((s, i) => s + (parseFloat(i.amount) || 0), 0)
  const grandTotal = totalLabor + totalMaterials

  return (
    <div>
      {/* Screen-only controls */}
      <div className="print:hidden flex items-center gap-3 mb-6">
        <Link
          to={`/filing-cabinet?job=${jobId}`}
          className="text-sm text-gray-600 hover:text-gray-900"
        >
          &larr; Back to Filing Cabinet
        </Link>
        <button
          onClick={handlePrint}
          className="ml-auto bg-blue-600 text-white px-5 py-2 rounded-lg text-sm hover:bg-blue-700"
        >
          Print / Save as PDF
        </button>
      </div>

      {/* Printable document */}
      <div ref={printRef} className="bg-white max-w-3xl mx-auto rounded-xl border border-gray-200 print:border-0 print:max-w-full print:rounded-none p-10 print:p-8">

        {/* Header — business card style */}
        <div className="bg-gradient-to-r from-blue-700 to-blue-900 text-white rounded-xl p-8 mb-8 print:rounded-none">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 bg-white rounded-xl flex items-center justify-center text-blue-800 font-black text-xl shrink-0">
                BHS
              </div>
              <div>
                <h1 className="text-2xl font-bold">Beard&apos;s Home Services</h1>
                <p className="text-blue-200 text-sm">Mountain Home, AR 72653</p>
                <p className="text-blue-200 text-sm">Licensed &amp; Insured</p>
              </div>
            </div>
            <div className="text-right">
              <div className={`text-3xl font-black ${isEstimate ? 'text-yellow-300' : 'text-green-300'}`}>
                {docType}
              </div>
              <div className="text-xl font-bold mt-1">{docNumber}</div>
              <div className="text-blue-200 text-sm mt-1">Date: {job.start_date || '\u2014'}</div>
            </div>
          </div>
        </div>

        {/* Bill To */}
        <div className="bg-gray-50 rounded-lg border border-gray-200 p-4 mb-8">
          <div className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Bill To</div>
          <div className="text-lg font-bold text-gray-900">{job.customer_name}</div>
          {job.customer_address && (
            <div className="text-gray-600 text-sm mt-0.5">{job.customer_address}</div>
          )}
        </div>

        {/* Line Items */}
        <table className="w-full mb-8">
          <thead>
            <tr className="border-b-2 border-gray-300 bg-gray-50">
              <th className="text-left py-3 px-3 text-sm font-semibold text-gray-700 w-3/5 rounded-tl-lg">Description</th>
              <th className="text-left py-3 px-3 text-sm font-semibold text-gray-700 w-1/5">Type</th>
              <th className="text-right py-3 px-3 text-sm font-semibold text-gray-700 w-1/5 rounded-tr-lg">Amount</th>
            </tr>
          </thead>
          <tbody>
            {services.map((svc, idx) => (
              <tr key={idx} className={`border-b border-gray-100 ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                <td className="py-2.5 px-3 text-sm text-gray-800 pr-4">
                  {svc.standardized_description || svc.original_description}
                </td>
                <td className="py-2.5 px-3 text-sm text-gray-500 capitalize">{svc.service_type || 'labor'}</td>
                <td className="py-2.5 px-3 text-sm font-medium text-gray-900 text-right">{fmt(svc.amount)}</td>
              </tr>
            ))}
            {services.length === 0 && (
              <tr>
                <td colSpan={3} className="py-4 text-center text-gray-400 text-sm">No line items</td>
              </tr>
            )}
          </tbody>
        </table>

        {/* Totals */}
        <div className="flex justify-end mb-10">
          <div className="w-72 bg-gray-50 rounded-xl border border-gray-200 p-4 space-y-2">
            {totalLabor > 0 && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Labor Subtotal</span>
                <span className="font-medium">{fmt(totalLabor)}</span>
              </div>
            )}
            {totalMaterials > 0 && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Materials Subtotal</span>
                <span className="font-medium">{fmt(totalMaterials)}</span>
              </div>
            )}
            <div className="flex justify-between text-xl font-black text-blue-800 pt-3 border-t-2 border-blue-800">
              <span>Total {isEstimate ? 'Estimate' : 'Due'}</span>
              <span>{fmt(grandTotal)}</span>
            </div>
          </div>
        </div>

        {/* Notes */}
        {job.notes && (
          <div className="mb-8 bg-gray-50 rounded-lg border border-gray-200 p-4">
            <div className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Notes</div>
            <div className="text-sm text-gray-700">{job.notes}</div>
          </div>
        )}

        {/* Footer */}
        <div className="border-t-2 border-gray-200 pt-6 text-center">
          {isEstimate ? (
            <div className="text-sm font-medium text-gray-600">
              Thank you for considering Beard&apos;s Home Services! This estimate is valid for 30 days.
            </div>
          ) : (
            <div className="text-sm font-medium text-gray-600">
              Thank you for your business! We appreciate you choosing Beard&apos;s Home Services.
            </div>
          )}
          <div className="text-xs text-gray-400 mt-2">
            Beard&apos;s Home Services &middot; Mountain Home, AR 72653 &middot; Licensed &amp; Insured
          </div>
        </div>
      </div>

      {/* Print styles injected via style tag */}
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .print\\:hidden { display: none !important; }
          [ref="printRef"], [ref="printRef"] * { visibility: visible; }
          body { margin: 0; padding: 0; }
        }
      `}</style>
    </div>
  )
}
