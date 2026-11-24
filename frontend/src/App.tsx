import { useEffect, useState } from 'react'
import Templates from './pages/Templates'
import './App.css'

type Health = { status: string; service: string }

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState('')
  const [page, setPage] = useState<'dashboard' | 'templates'>('dashboard')

  useEffect(() => {
    fetch('/api/health')
      .then((response) => {
        if (!response.ok) throw new Error(`API returned ${response.status}`)
        return response.json() as Promise<Health>
      })
      .then(setHealth)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'API unavailable'))
  }, [])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark">SF</div>
        <div className="brand-copy"><strong>Student Forms</strong><span>Digitizer</span></div>
        <div className="nav-label">WORKSPACE</div>
        <button className={`nav-item ${page === 'dashboard' ? 'active' : ''}`} onClick={() => setPage('dashboard')}><span>▦</span> Dashboard</button>
        <button className={`nav-item ${page === 'templates' ? 'active' : ''}`} onClick={() => setPage('templates')}><span>▤</span> Form templates</button>
        <a className="nav-item disabled" href="#upload"><span>⇧</span> Upload documents</a>
        <a className="nav-item disabled" href="#verification"><span>✓</span> Verification</a>
        <a className="nav-item disabled" href="#records"><span>☷</span> Student records</a>
        <a className="nav-item disabled" href="#exports"><span>⇩</span> Excel exports</a>
        <div className="sidebar-bottom"><span className="local-dot" /> Local workspace<br /><small>Data stays on this device</small></div>
      </aside>

      <main className="main-content" id="dashboard">
        <header className="topbar"><span>Workspace <b>/</b> Dashboard</span><span className="local-badge"><i /> Running locally</span></header>
        {page === 'templates' ? <Templates /> : <>
        <section className="welcome">
          <div><p className="eyebrow">STUDENT FORM DIGITIZER</p><h1>Good day.</h1><p className="subtitle">Your local workspace is ready to set up.</p></div>
          <div className="date-chip">PHASE 1 · FOUNDATION</div>
        </section>

        <section className="status-banner">
          <div className="status-icon">✦</div>
          <div className="status-text"><strong>Local services</strong><span>Frontend connected to the local API and SQLite foundation.</span></div>
          <span className={`connection ${health ? 'connected' : error ? 'failed' : ''}`}><i />{health ? 'Connected' : error ? 'Unavailable' : 'Connecting'}</span>
        </section>

        <section className="metrics" aria-label="Workspace metrics">
          <article className="metric-card"><div className="metric-head"><span>Uploaded forms</span><span className="metric-icon blue">▤</span></div><strong>—</strong><small>Ready when you are</small></article>
          <article className="metric-card"><div className="metric-head"><span>Pending review</span><span className="metric-icon amber">◷</span></div><strong>—</strong><small>Nothing waiting</small></article>
          <article className="metric-card"><div className="metric-head"><span>Student records</span><span className="metric-icon green">♙</span></div><strong>—</strong><small>Stored on this device</small></article>
          <article className="metric-card"><div className="metric-head"><span>Templates</span><span className="metric-icon violet">▧</span></div><strong>—</strong><small>Questionnaires you create</small></article>
        </section>

        <section className="content-grid">
          <article className="panel getting-started"><div className="panel-title"><div><p className="eyebrow">GETTING STARTED</p><h2>Your workflow, in a few steps</h2></div><span className="step-count">01 / 04</span></div>
            <div className="workflow-step"><span className="step-number current">01</span><div><strong>Create a form template</strong><p>Define questions and map them to your paper form.</p></div><span className="step-state">NEXT UP</span></div>
            <div className="workflow-step muted"><span className="step-number">02</span><div><strong>Upload student forms</strong><p>Add scans or photos and choose a template.</p></div><span className="lock">⌑</span></div>
            <div className="workflow-step muted"><span className="step-number">03</span><div><strong>Review recognized answers</strong><p>Check every answer and make corrections.</p></div><span className="lock">⌑</span></div>
            <div className="workflow-step muted"><span className="step-number">04</span><div><strong>Export to Excel</strong><p>Download organized student records.</p></div><span className="lock">⌑</span></div>
          </article>
          <article className="panel activity"><div className="panel-title"><div><p className="eyebrow">SYSTEM</p><h2>Service status</h2></div><span className="pulse" /></div>
            <div className="service-row"><span className="service-symbol">API</span><div><strong>Local API</strong><small>127.0.0.1:8000</small></div><span className={`service-state ${health ? 'ok' : error ? 'bad' : ''}`}>{health ? 'Online' : error ? 'Offline' : 'Checking'}</span></div>
            <div className="service-row"><span className="service-symbol db">DB</span><div><strong>SQLite database</strong><small>local_data/database</small></div><span className="service-state">Ready</span></div>
            <div className="privacy-note"><span>◈</span><p><strong>Private by design</strong><br />Your files and records remain on this computer.</p></div>
            {error && <p className="error-message">API connection failed: {error}</p>}
          </article>
        </section>
        <footer>Student Form Digitizer <span>•</span> Local workspace <span>•</span> Phase 1</footer>
        </>}
      </main>
    </div>
  )
}

export default App
