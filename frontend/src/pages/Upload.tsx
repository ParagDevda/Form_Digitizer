import { useCallback, useEffect, useRef, useState } from 'react'

type Template = { id: string; name: string }
type Batch = { id: string; batch_name: string; total_documents: number; processed_documents: number; failed_documents: number; documents: { id: string; filename: string; status: string; error: string | null }[] }
type BatchHeader={id:string;name:string;total_documents:number;processed_documents:number;failed_documents:number}

export default function Upload() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [batches, setBatches] = useState<Batch[]>([])
  const [templateId, setTemplateId] = useState('')
  const [batchName, setBatchName] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [previews, setPreviews] = useState<Record<string, string>>({})
  const picker = useRef<HTMLInputElement>(null)

  const refresh = useCallback(async () => {
    const [templateResponse, documentsResponse, batchResponse] = await Promise.all([fetch('/api/templates'), fetch('/api/documents'), fetch('/api/dashboard/batches')])
    if (templateResponse.ok) { const data = await templateResponse.json() as Template[]; setTemplates(data); if (!templateId && data.length) setTemplateId(data[0].id) }
    if (documentsResponse.ok) {
      const docs = await documentsResponse.json() as { id: string; batch_id: string; filename: string; status: string; error_message: string | null }[]
      const headers = batchResponse.ok ? await batchResponse.json() as BatchHeader[] : []
      const names = new Map(headers.map(item=>[item.id,item.name]))
      const grouped = new Map<string, Batch>()
      docs.forEach(d => { if (!grouped.has(d.batch_id)) grouped.set(d.batch_id, { id:d.batch_id,batch_name:names.get(d.batch_id)??d.batch_id.slice(0,8),total_documents:0,processed_documents:0,failed_documents:0,documents:[] }); const b=grouped.get(d.batch_id)!; b.total_documents++; if(d.status==='pending_review'||d.status==='verified')b.processed_documents++;if(d.status==='failed')b.failed_documents++;b.documents.push({id:d.id,filename:d.filename,status:d.status,error:d.error_message}) })
      setBatches([...grouped.values()])
    }
  }, [templateId])
  // eslint-disable-next-line react/set-state-in-effect -- synchronize the batch and template list with the API.
  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => { const timer = window.setInterval(() => void refresh(), 2500); return () => window.clearInterval(timer) }, [refresh])
  useEffect(() => {
    const urls: Record<string, string> = {}
    files.forEach(file => { if (file.type.startsWith('image/')) urls[`${file.name}-${file.size}-${file.lastModified}`] = URL.createObjectURL(file) })
    // eslint-disable-next-line react/set-state-in-effect -- refresh object URLs when the selected file collection changes.
    setPreviews(urls)
    return () => Object.values(urls).forEach(URL.revokeObjectURL)
  }, [files])
  function selectFiles(list: FileList | null) {
    if (!list) return
    const selected = Array.from(list)
    const unsupported = selected.find(f => !/\.(jpe?g|png|webp|pdf)$/i.test(f.name))
    if (unsupported) { setMessage(`${unsupported.name} is not a supported image or PDF.`); return }
    const oversized = selected.find(f => f.size > 25 * 1024 * 1024)
    if (oversized) { setMessage(`${oversized.name} exceeds the 25 MB limit.`); return }
    setFiles(selected); setMessage('')
  }
  async function upload() {
    if (!files.length || !templateId || !batchName.trim()) { setMessage('Enter a batch name, choose a template, and select files.'); return }
    if (files.length > 500) { setMessage('A batch can contain at most 500 forms.'); return }
    setBusy(true); setMessage('Creating batch…')
    try {
      const form = new FormData(); form.set('batch_name',batchName.trim()); form.set('template_id',templateId)
      const created = await fetch('/api/batches',{method:'POST',body:form}); if(!created.ok)throw new Error((await created.json()).detail ?? 'Could not create batch')
      const batch = await created.json() as {id:string}
      const uploadForm = new FormData(); uploadForm.set('batch_id',batch.id); files.forEach(file => uploadForm.append('files',file))
      const response = await new Promise<{ok:boolean;detail?:string}>((resolve,reject)=>{const request=new XMLHttpRequest();request.open('POST','/api/documents/upload');request.upload.onprogress=event=>{if(event.lengthComputable)setUploadProgress(Math.round(event.loaded/event.total*100))};request.onerror=()=>reject(new Error('Upload connection failed'));request.onload=()=>{let data:{detail?:string}={};try{data=JSON.parse(request.responseText) as {detail?:string}}catch{};resolve({ok:request.status>=200&&request.status<300,detail:data.detail})};request.send(uploadForm)}); if(!response.ok)throw new Error(response.detail ?? 'Upload failed')
      setMessage(`${files.length} form(s) uploaded. Processing starts when you select Process batch.`); setFiles([]);setBatchName('');await refresh()
    } catch(e) {setMessage(e instanceof Error?e.message:'Upload failed')} finally {setBusy(false)}
  }
  async function process(id:string) { setMessage('Queueing batch…'); const r=await fetch(`/api/batches/${id}/process`,{method:'POST'});setMessage(r.ok?'Batch queued for sequential processing.':(await r.json()).detail); await refresh() }
  async function retry(id:string) { const r=await fetch(`/api/documents/${id}/retry`,{method:'POST'});setMessage(r.ok?'Document queued for retry.':(await r.json()).detail);await refresh() }

  return <section className="template-page"><div className="page-heading"><p className="eyebrow">DOCUMENT INTAKE</p><h1>Upload forms</h1><p className="subtitle">Add photos, scans, or PDFs to a template batch.</p></div>
    <div className="template-layout upload-layout"><div className="panel upload-panel"><h2>New batch</h2><label>Batch name<input value={batchName} onChange={e=>setBatchName(e.target.value)} placeholder="e.g. Grade 8 · November" /></label><label>Form template<select value={templateId} onChange={e=>setTemplateId(e.target.value)}><option value="">Choose a template</option>{templates.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
      <div className="drop-area" onClick={()=>picker.current?.click()} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();selectFiles(e.dataTransfer.files)}}><span>⇧</span><strong>Drop forms here, or browse files</strong><small>JPG, PNG, WEBP or PDF · up to 25 MB each · max 500 per batch</small><input ref={picker} type="file" multiple accept=".jpg,.jpeg,.png,.webp,.pdf" onChange={e=>selectFiles(e.target.files)} /></div>
      {!!files.length&&<div className="picked-files">{files.map(f=><div className="picked-file" key={`${f.name}-${f.size}-${f.lastModified}`}>{previews[`${f.name}-${f.size}-${f.lastModified}`]?<img src={previews[`${f.name}-${f.size}-${f.lastModified}`]} alt={`Preview of ${f.name}`}/>:<span className="pdf-preview">PDF</span>}<span className="picked-file-name">{f.name}<small>{(f.size/1024/1024).toFixed(1)} MB</small></span><button onClick={()=>setFiles(files.filter(item=>item!==f))} aria-label={`Remove ${f.name}`}>×</button></div>)}</div>}
      <button className="primary-button" disabled={busy} onClick={()=>void upload()}>{busy?`Uploading · ${uploadProgress}%`:`Upload ${files.length||''} form${files.length===1?'':'s'}`}</button>{message&&<p className="upload-message" role="status">{message}</p>}
    </div><div className="panel batch-panel"><h2>Recent batches <span>{batches.length}</span></h2>{!batches.length&&<p className="empty-note">Uploaded batches will show their processing status here.</p>}{batches.map(b=><article className="batch-card" key={b.id}><div className="batch-head"><span><strong>{b.batch_name}</strong><small>{b.total_documents} forms · {b.processed_documents} ready · {b.failed_documents} failed</small></span><button className="primary-button" onClick={()=>void process(b.id)}>Process batch</button></div>{b.documents.map(d=><div className="batch-document" key={d.id}><span>{d.filename}</span><span className={`doc-status ${d.status}`}>{d.status.replace('_',' ')}</span>{d.status==='failed'&&<button onClick={()=>void retry(d.id)}>Retry</button>}</div>)}</article>)}</div></div>
  </section>
}
