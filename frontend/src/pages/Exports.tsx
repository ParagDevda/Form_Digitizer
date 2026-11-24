import { useEffect, useState } from 'react'

type Template = { id: string; name: string }
type Batch = { id: string; name: string; total_documents: number }

export default function Exports() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [batches, setBatches] = useState<Batch[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [batchId, setBatchId] = useState('')
  const [verifiedOnly, setVerifiedOnly] = useState(false)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    Promise.all([fetch('/api/templates'), fetch('/api/batches')]).then(async ([templateResponse, batchResponse]) => {
      if (templateResponse.ok) setTemplates(await templateResponse.json())
      if (batchResponse.ok) setBatches(await batchResponse.json())
    }).catch(() => setMessage('Could not load export options.'))
  }, [])

  async function exportWorkbook() {
    setBusy(true); setMessage('Preparing workbook…')
    try {
      const response = await fetch('/api/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ template_ids: selected.length ? selected : null, batch_id: batchId || null, verified_only: verifiedOnly }) })
      if (!response.ok) throw new Error((await response.json()).detail ?? 'Export failed')
      const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement('a')
      link.href = url; link.download = response.headers.get('content-disposition')?.match(/filename="?([^";]+)"?/)?.[1] ?? 'student-records.xlsx'; link.click(); URL.revokeObjectURL(url)
      setMessage('Workbook downloaded.')
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Export failed') } finally { setBusy(false) }
  }

  return <section className="template-page"><div className="page-heading"><p className="eyebrow">SPREADSHEET OUTPUT</p><h1>Excel exports</h1><p className="subtitle">Generate dynamic, question-wise workbooks from your local student records.</p></div>
    <div className="panel export-panel"><h2>Choose records to include</h2><p>Each selected template gets its own worksheet. Corrected answers are used when available; blank answers stay blank.</p>
      <label>Batch<select value={batchId} onChange={e => setBatchId(e.target.value)}><option value="">All batches</option>{batches.map(batch => <option key={batch.id} value={batch.id}>{batch.name} · {batch.total_documents} forms</option>)}</select></label>
      <label className="export-toggle"><input type="checkbox" checked={verifiedOnly} onChange={e => setVerifiedOnly(e.target.checked)} /><span>Verified records only</span></label>
      <div className="export-templates"><h3>Templates</h3>{templates.length ? templates.map(template => <label className="export-choice" key={template.id}><input type="checkbox" checked={selected.includes(template.id)} onChange={e => setSelected(e.target.checked ? [...selected, template.id] : selected.filter(id => id !== template.id))} /><span><strong>{template.name}</strong><small>Answers grouped by configured questions</small></span></label>) : <p className="empty-note">Create a form template before exporting.</p>}</div>
      <button className="primary-button" disabled={busy || !templates.length} onClick={() => void exportWorkbook()}>{busy ? 'Preparing…' : 'Download Excel workbook'}</button>{message && <p className="upload-message" role="status">{message}</p>}
    </div>
  </section>
}
