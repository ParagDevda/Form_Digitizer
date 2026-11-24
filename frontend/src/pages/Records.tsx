import { useCallback, useEffect, useState } from 'react'

type RecordRow = { id: string; document_id: string; filename: string | null; batch_name: string | null; template_id: string; template_name: string | null; student_name: string | null; student_identifier: string | null; document_status: string; verification_status: string; answer_count: number; created_at: string }
type RecordDetail = { id: string; document_id: string; filename: string | null; batch_name: string | null; template_name: string | null; student_name: string | null; student_identifier: string | null; verification_status: string; answers: { id: string; question_number: number; question_text: string; page_number: number; normalized_ocr_text: string; corrected_text: string | null; verification_status: string }[] }

export default function Records() {
  const [rows, setRows] = useState<RecordRow[]>([])
  const [selected, setSelected] = useState<RecordDetail | null>(null)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState('newest')
  const [templateId, setTemplateId] = useState('')
  const [templates, setTemplates] = useState<{ id: string; name: string }[]>([])
  const [name, setName] = useState('')
  const [identifier, setIdentifier] = useState('')
  const [message, setMessage] = useState('')

  const load = useCallback(async () => {
    const params = new URLSearchParams()
    if (search.trim()) params.set('q', search.trim())
    if (status) params.set('status', status)
    if (templateId) params.set('template_id', templateId)
    const response = await fetch(`/api/records?${params}`)
    if (response.ok) setRows(await response.json())
  }, [search, status, templateId])
  async function open(id: string) {
    const response = await fetch(`/api/records/${id}`)
    if (!response.ok) return
    const detail = await response.json() as RecordDetail
    setSelected(detail); setName(detail.student_name ?? ''); setIdentifier(detail.student_identifier ?? ''); setMessage('')
  }
  useEffect(() => { void fetch('/api/templates').then(r => r.json()).then(setTemplates).catch(() => setMessage('Could not load templates.')) }, [])
  useEffect(() => { const timer = window.setTimeout(() => void load(), 200); return () => window.clearTimeout(timer) }, [load])
  const orderedRows = [...rows].sort((left, right) => sort === 'name' ? (left.student_name ?? '').localeCompare(right.student_name ?? '') : sort === 'status' ? left.verification_status.localeCompare(right.verification_status) : right.created_at.localeCompare(left.created_at))

  async function save() {
    if (!selected) return
    const response = await fetch(`/api/records/${selected.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ student_name: name, student_identifier: identifier }) })
    setMessage(response.ok ? 'Student details saved.' : 'Could not save student details.')
    if (response.ok) { await load(); await open(selected.id) }
  }
  async function remove() {
    if (!selected || !window.confirm('Delete this student record and its original uploaded document?')) return
    const response = await fetch(`/api/records/${selected.id}`, { method: 'DELETE' })
    if (!response.ok) { setMessage((await response.json()).detail ?? 'Could not delete record'); return }
    setSelected(null); setMessage('Record and source document deleted.'); await load()
  }

  return <section className="template-page"><div className="page-heading"><p className="eyebrow">LOCAL STUDENT DATA</p><h1>Student records</h1><p className="subtitle">Search, filter, review, and maintain the records stored on this computer.</p></div>
    <div className="records-layout"><div className="panel records-panel"><div className="records-filters"><input aria-label="Search records" placeholder="Search student, ID, or filename" value={search} onChange={e => setSearch(e.target.value)} /><select aria-label="Filter by verification status" value={status} onChange={e => setStatus(e.target.value)}><option value="">All verification states</option><option value="pending">Pending</option><option value="verified">Verified</option></select><select aria-label="Filter by template" value={templateId} onChange={e => setTemplateId(e.target.value)}><option value="">All templates</option>{templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select><select aria-label="Sort records" value={sort} onChange={e => setSort(e.target.value)}><option value="newest">Newest first</option><option value="name">Student name</option><option value="status">Verification state</option></select></div>
      <div className="records-table-wrap"><table className="records-table"><thead><tr><th>Student</th><th>Template and batch</th><th>Document</th><th>Status</th><th>Created</th></tr></thead><tbody>{orderedRows.map(row => <tr key={row.id} className={selected?.id === row.id ? 'selected' : ''} onClick={() => void open(row.id)}><td><strong>{row.student_name || 'Unnamed student'}</strong><small>{row.student_identifier || 'No student ID'}</small></td><td>{row.template_name || 'Template removed'}<small>{row.batch_name || 'Batch'}</small></td><td>{row.filename || 'Source unavailable'}<small>{row.answer_count} answers</small></td><td><span className={`doc-status ${row.verification_status}`}>{row.verification_status.replace('_', ' ')}</span></td><td>{new Date(row.created_at).toLocaleDateString()}</td></tr>)}</tbody></table>{!rows.length && <p className="empty-note">No records match these filters. Process a batch to create student records.</p>}</div>
    </div>{selected ? <aside className="panel record-detail"><div className="record-detail-head"><div><p className="eyebrow">RECORD DETAILS</p><h2>{selected.filename ?? 'Student record'}</h2><small>{selected.template_name} · {selected.batch_name}</small></div><button className="delete-button" aria-label="Delete student record" onClick={() => void remove()}>×</button></div><a className="source-link" href={`/api/documents/${selected.document_id}/file?page=1`} target="_blank" rel="noreferrer">View original document</a><label>Student name<input value={name} onChange={e => setName(e.target.value)} maxLength={250} /></label><label>Student ID<input value={identifier} onChange={e => setIdentifier(e.target.value)} maxLength={160} /></label><button className="secondary-button" onClick={() => void save()}>Save student details</button><h3>Answers</h3><div className="record-answers">{selected.answers.map(answer => <article key={answer.id}><strong>Q{answer.question_number}: {answer.question_text}</strong><p>{(answer.corrected_text ?? answer.normalized_ocr_text) || 'No answer recorded'}</p><small>{answer.verification_status.replace('_', ' ')}</small></article>)}</div>{message && <p className="upload-message" role="status">{message}</p>}</aside> : <aside className="panel editor-empty"><h2>Choose a record</h2><p>Student details, answers, and source document will appear here.</p></aside>}</div>
  </section>
}
