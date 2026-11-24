import { useEffect, useState } from 'react'
import Templates from './pages/Templates'
import Upload from './pages/Upload'
import Verification from './pages/Verification'
import Exports from './pages/Exports'
import Records from './pages/Records'
import Settings from './pages/Settings'
import './App.css'

type Health = { status: string; service: string }
type DashboardStats = { uploaded_forms: number; processed_forms: number; verified_forms: number; pending_review: number; failed_forms: number; student_records: number; templates: number }
type RecentBatch = { id: string; name: string; total_documents: number; processed_documents: number; failed_documents: number; created_at: string }

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState('')
  const [page, setPage] = useState<'dashboard' | 'templates' | 'upload' | 'verification' | 'records' | 'exports' | 'settings'>('dashboard')
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [recentBatches, setRecentBatches] = useState<RecentBatch[]>([])

  useEffect(() => {
    fetch('/api/health')
      .then((response) => {
        if (!response.ok) throw new Error(`API returned ${response.status}`)
        return response.json() as Promise<Health>
      })
      .then(setHealth)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'API unavailable'))
    const refresh = () => {
      fetch('/api/dashboard/stats').then(response => { if (!response.ok) throw new Error('Could not load workspace statistics'); return response.json() as Promise<DashboardStats> }).then(setStats).catch(() => setStats(null))
      fetch('/api/dashboard/batches').then(response => response.ok ? response.json() as Promise<RecentBatch[]> : []).then(setRecentBatches).catch(() => setRecentBatches([]))
    }
    refresh()
    const interval = window.setInterval(refresh, 5000)
    return () => window.clearInterval(interval)
  }, [])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark">SF</div>
        <div className="brand-copy"><strong>Student Forms</strong><span>Digitizer</span></div>
        <div className="nav-label">WORKSPACE</div>
        <button className={`nav-item ${page === 'dashboard' ? 'active' : ''}`} onClick={() => setPage('dashboard')}><span>▦</span> Dashboard</button>
        <button className={`nav-item ${page === 'templates' ? 'active' : ''}`} onClick={() => setPage('templates')}><span>▤</span> Form templates</button>
        <button className={`nav-item ${page === 'upload' ? 'active' : ''}`} onClick={() => setPage('upload')}><span>⇧</span> Upload documents</button>
        <button className={`nav-item ${page === 'verification' ? 'active' : ''}`} onClick={() => setPage('verification')}><span>✓</span> Verification</button>
        <button className={`nav-item ${page === 'records' ? 'active' : ''}`} onClick={() => setPage('records')}><span>☷</span> Student records</button>
        <button className={`nav-item ${page === 'exports' ? 'active' : ''}`} onClick={() => setPage('exports')}><span>⇩</span> Excel exports</button>
        <button className={`nav-item ${page === 'settings' ? 'active' : ''}`} onClick={() => setPage('settings')}><span>⚙</span> Settings</button>
        <div className="sidebar-bottom"><span className="local-dot" /> Local workspace<br /><small>Data stays on this device</small></div>
      </aside>

      <main className="main-content" id="dashboard">
        <header className="topbar"><span>Workspace <b>/</b> {page[0].toUpperCase() + page.slice(1)}</span><span className="local-badge"><i /> Running locally</span></header>
        {page === 'templates' ? <Templates /> : page === 'upload' ? <Upload /> : page === 'verification' ? <Verification /> : page === 'records' ? <Records /> : page === 'exports' ? <Exports /> : page === 'settings' ? <Settings /> : <>
        <section className="welcome">
          <div><p className="eyebrow">STUDENT FORM DIGITIZER</p><h1>Local form workspace</h1><p className="subtitle">Upload, process, review, and export student forms from this device.</p></div>
          <div className="date-chip">OFFLINE · CPU OCR</div>
        </section>

        <section className="status-banner">
          <div className="status-icon">✦</div>
          <div className="status-text"><strong>Local services</strong><span>Frontend connected to the local API and SQLite foundation.</span></div>
          <span className={`connection ${health ? 'connected' : error ? 'failed' : ''}`}><i />{health ? 'Connected' : error ? 'Unavailable' : 'Connecting'}</span>
        </section>

        <section className="metrics" aria-label="Workspace metrics">
          <article className="metric-card"><div className="metric-head"><span>Uploaded forms</span><span className="metric-icon blue">▤</span></div><strong>{stats?.uploaded_forms ?? '—'}</strong><small>Stored on this device</small></article>
          <article className="metric-card"><div className="metric-head"><span>Processed forms</span><span className="metric-icon green">✓</span></div><strong>{stats?.processed_forms ?? '—'}</strong><small>OCR extraction complete</small></article>
          <article className="metric-card"><div className="metric-head"><span>Pending review</span><span className="metric-icon amber">◷</span></div><strong>{stats?.pending_review ?? '—'}</strong><small>Answers to verify</small></article>
          <article className="metric-card"><div className="metric-head"><span>Failed forms</span><span className="metric-icon violet">!</span></div><strong>{stats?.failed_forms ?? '—'}</strong><small>Can be retried</small></article>
          <article className="metric-card"><div className="metric-head"><span>Student records</span><span className="metric-icon green">♙</span></div><strong>{stats?.student_records ?? '—'}</strong><small>Local student records</small></article>
          <article className="metric-card"><div className="metric-head"><span>Templates</span><span className="metric-icon violet">▧</span></div><strong>{stats?.templates ?? '—'}</strong><small>Questionnaires configured</small></article>
        </section>

        <section className="content-grid">
          <article className="panel getting-started"><div className="panel-title"><div><p className="eyebrow">QUICK ACTIONS</p><h2>Continue your workflow</h2></div></div>
            <div className="quick-actions"><button onClick={() => setPage('templates')}>Create or edit a template</button><button onClick={() => setPage('upload')}>Upload and process a batch</button><button onClick={() => setPage('verification')}>Review recognized answers</button><button onClick={() => setPage('exports')}>Export records to Excel</button></div>
          </article>
          <article className="panel activity"><div className="panel-title"><div><p className="eyebrow">SYSTEM</p><h2>Service status</h2></div><span className="pulse" /></div>
            <div className="service-row"><span className="service-symbol">API</span><div><strong>Local API</strong><small>127.0.0.1:8000</small></div><span className={`service-state ${health ? 'ok' : error ? 'bad' : ''}`}>{health ? 'Online' : error ? 'Offline' : 'Checking'}</span></div>
            <div className="service-row"><span className="service-symbol db">DB</span><div><strong>SQLite database</strong><small>local_data/database</small></div><span className="service-state">Ready</span></div>
            <div className="privacy-note"><span>◈</span><p><strong>Private by design</strong><br />Your files and records remain on this computer.</p></div>
            <div className="recent-batches"><strong>Recent batches</strong>{recentBatches.length ? recentBatches.slice(0,4).map(batch => <div key={batch.id}><span>{batch.name}<small>{batch.processed_documents}/{batch.total_documents} processed · {batch.failed_documents} failed</small></span><i>{new Date(batch.created_at).toLocaleDateString()}</i></div>) : <small>No batches yet.</small>}</div>
            {error && <p className="error-message">API connection failed: {error}</p>}
          </article>
        </section>
        <footer>Student Form Digitizer <span>•</span> Local workspace <span>•</span> English handwriting OCR</footer>
        </>}
      </main>
    </div>
  )
}

export default App
