import { useEffect, useRef, useState } from 'react'

type Region = { x: number; y: number; width: number; height: number }
type Question = { id: string; question_number: number; question_text: string; answer_type: string; is_required: boolean; display_order: number; page_number: number; region_x: number | null; region_y: number | null; region_width: number | null; region_height: number | null }
type Template = { id: string; name: string; description: string; version: string; page_count: number; questions: Question[] }

const emptyQuestion = { question_number: 1, question_text: '', answer_type: 'short_text', is_required: false, display_order: 0, page_number: 1, region_x: null as number | null, region_y: null as number | null, region_width: null as number | null, region_height: null as number | null }

export default function Templates() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [selected, setSelected] = useState<Template | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [question, setQuestion] = useState(emptyQuestion)
  const [activeQuestion, setActiveQuestion] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [error, setError] = useState('')
  const canvas = useRef<HTMLDivElement>(null)
  const drawing = useRef<{ x: number; y: number } | null>(null)
  const [draftRegion, setDraftRegion] = useState<Region | null>(null)

  async function load() {
    const response = await fetch('/api/templates')
    if (!response.ok) throw new Error('Could not load templates')
    setTemplates(await response.json())
  }
  useEffect(() => { void load().catch((e: Error) => setError(e.message)) }, [])
  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl) }, [imageUrl])

  async function createTemplate(event: React.FormEvent) {
    event.preventDefault(); setError('')
    try {
      const response = await fetch('/api/templates', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, description, version: '1.0', page_count: 1 }) })
      if (!response.ok) throw new Error((await response.json()).detail ?? 'Could not create template')
      const created = await response.json() as Template
      await load(); setSelected(created); setName(''); setDescription('')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create template') }
  }
  async function refreshSelected(id: string) {
    await load()
    const response = await fetch(`/api/templates/${id}`)
    if (response.ok) setSelected(await response.json())
  }
  async function addQuestion(event: React.FormEvent) {
    event.preventDefault(); if (!selected) return
    setError('')
    try {
      const response = await fetch(`/api/templates/${selected.id}/questions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...question, question_number: selected.questions.length + 1, display_order: selected.questions.length }) })
      if (!response.ok) throw new Error((await response.json()).detail ?? 'Could not save question')
      setQuestion({ ...emptyQuestion, question_number: selected.questions.length + 2, display_order: selected.questions.length + 1 })
      await refreshSelected(selected.id)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save question') }
  }
  async function deleteQuestion(id: string) {
    if (!selected) return
    const response = await fetch(`/api/templates/questions/${id}`, { method: 'DELETE' })
    if (response.ok) await refreshSelected(selected.id)
  }
  async function deleteTemplate(id: string) {
    if (!window.confirm('Delete this template and its questions?')) return
    const response = await fetch(`/api/templates/${id}`, { method: 'DELETE' })
    if (response.ok) { if (selected?.id === id) setSelected(null); await load() }
  }
  function coordinates(event: React.PointerEvent) {
    const rect = canvas.current?.getBoundingClientRect()
    if (!rect) return null
    return { x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)) }
  }
  function beginDraw(event: React.PointerEvent) { const point = coordinates(event); if (!point) return; drawing.current = point; event.currentTarget.setPointerCapture(event.pointerId); setDraftRegion({ ...point, width: 0, height: 0 }) }
  function moveDraw(event: React.PointerEvent) { if (!drawing.current) return; const point = coordinates(event); if (!point) return; const start = drawing.current; setDraftRegion({ x: Math.min(start.x, point.x), y: Math.min(start.y, point.y), width: Math.abs(point.x - start.x), height: Math.abs(point.y - start.y) }) }
  async function endDraw() {
    drawing.current = null
    if (!draftRegion || !selected || !activeQuestion || draftRegion.width < .01 || draftRegion.height < .01) return
    const item = selected.questions.find(q => q.id === activeQuestion)
    if (!item) return
    const response = await fetch(`/api/templates/questions/${item.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ region_x: draftRegion.x, region_y: draftRegion.y, region_width: draftRegion.width, region_height: draftRegion.height }) })
    if (response.ok) await refreshSelected(selected.id)
  }

  return <section className="template-page">
    <div className="page-heading"><div><p className="eyebrow">QUESTIONNAIRE SETUP</p><h1>Form templates</h1><p className="subtitle">Create reusable questionnaires and map answer areas on a sample form.</p></div></div>
    {error && <p className="template-error" role="alert">{error}</p>}
    <div className="template-layout">
      <aside className="panel template-list"><h2>Your templates <span>{templates.length}</span></h2>
        <form className="template-create" onSubmit={createTemplate}><label>Template name<input required maxLength={160} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Student wellbeing form" /></label><label>Description<textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="Optional details" /></label><button className="primary-button">Create template</button></form>
        {templates.map(t => <div key={t.id} className={`template-row ${selected?.id === t.id ? 'chosen' : ''}`}><button onClick={() => setSelected(t)}><strong>{t.name}</strong><small>{t.questions.length} questions · v{t.version}</small></button><button className="delete-button" title="Delete template" onClick={() => void deleteTemplate(t.id)}>×</button></div>)}
        {!templates.length && <p className="empty-note">Templates you create will appear here.</p>}
      </aside>
      <div className="template-editor">
        {!selected ? <div className="panel editor-empty"><div className="empty-symbol">▧</div><h2>Select or create a template</h2><p>Question setup and region mapping will appear here.</p></div> : <>
          <div className="panel question-panel"><div className="panel-title"><div><p className="eyebrow">{selected.version} · {selected.page_count} PAGE</p><h2>{selected.name}</h2></div><span className="step-count">{selected.questions.length} QUESTIONS</span></div>
            <div className="question-list">{selected.questions.map(q => <div key={q.id} className={`question-row ${activeQuestion === q.id ? 'selected' : ''}`}><button className="question-select" onClick={() => setActiveQuestion(q.id)}><span className="question-number">{q.question_number}</span><span><strong>{q.question_text}</strong><small>{q.answer_type.replace('_',' ')} · Page {q.page_number}{q.region_x === null ? ' · Region not mapped' : ' · Region mapped'}</small></span></button><button className="delete-button" onClick={() => void deleteQuestion(q.id)} aria-label="Delete question">×</button></div>)}</div>
            <form className="question-form" onSubmit={addQuestion}><h3>Add a question</h3><input required maxLength={4000} value={question.question_text} onChange={e => setQuestion({ ...question, question_text: e.target.value })} placeholder="Enter the question text" /><div className="question-controls"><select value={question.answer_type} onChange={e => setQuestion({ ...question, answer_type: e.target.value })}><option value="short_text">Short text</option><option value="long_text">Long text</option><option value="number">Number</option><option value="date">Date</option><option value="multiple_choice">Multiple choice</option><option value="yes_no">Yes / No</option><option value="custom_text">Custom text</option></select><label className="check-label"><input type="checkbox" checked={question.is_required} onChange={e => setQuestion({ ...question, is_required: e.target.checked })} /> Required</label><button className="primary-button">Add question</button></div></form>
          </div>
          <div className="panel mapping-panel"><div className="panel-title"><div><p className="eyebrow">VISUAL REGION MAPPING</p><h2>Map answer areas</h2></div><label className="upload-sample">Choose sample<input type="file" accept="image/*" onChange={e => { const file = e.target.files?.[0]; if (file) setImageUrl(URL.createObjectURL(file)) }} /></label></div>
            {imageUrl ? <div ref={canvas} className="sample-canvas" onPointerDown={beginDraw} onPointerMove={moveDraw} onPointerUp={() => void endDraw()}><img src={imageUrl} alt="Blank sample form" draggable={false} />{selected.questions.filter(q => q.region_x !== null).map(q => <div key={q.id} className={`region-box ${activeQuestion === q.id ? 'focused' : ''}`} style={{ left: `${q.region_x! * 100}%`, top: `${q.region_y! * 100}%`, width: `${q.region_width! * 100}%`, height: `${q.region_height! * 100}%` }}><span>Q{q.question_number}</span></div>)}{draftRegion && <div className="region-box draft" style={{ left: `${draftRegion.x * 100}%`, top: `${draftRegion.y * 100}%`, width: `${draftRegion.width * 100}%`, height: `${draftRegion.height * 100}%` }} />}</div> : <div className="sample-empty"><span>▧</span><strong>Upload a blank sample page</strong><small>Choose a question above, then drag over its handwritten answer area.</small></div>}
            <p className="mapping-hint">{!activeQuestion ? 'Select a question before drawing a region.' : 'Drag across the sample to map the selected question.'} Coordinates are stored relative to the page.</p>
          </div>
        </>}
      </div>
    </div>
  </section>
}
