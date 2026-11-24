import { useState } from 'react'

export default function Settings() {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  async function backup() {
    setBusy(true); setMessage('Preparing a local backup…')
    try {
      const response = await fetch('/api/settings/backup', { method: 'POST' })
      if (!response.ok) throw new Error('Backup could not be created.')
      const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement('a')
      link.href = url; link.download = response.headers.get('content-disposition')?.match(/filename="?([^";]+)"?/)?.[1] ?? 'student-form-backup.zip'; link.click(); URL.revokeObjectURL(url)
      setMessage('Backup downloaded. A local copy is also stored in local_data/backups.')
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Backup failed.') } finally { setBusy(false) }
  }
  return <section className="template-page"><div className="page-heading"><p className="eyebrow">DEVICE AND DATA</p><h1>Settings</h1><p className="subtitle">Manage local data protection for this offline workspace.</p></div><div className="panel settings-panel"><h2>Local backup</h2><p>Create a ZIP archive containing the SQLite database, original documents, template samples, processed files, and Excel exports. The OCR model is kept separately.</p><button className="primary-button" disabled={busy} onClick={() => void backup()}>{busy ? 'Creating backup…' : 'Create and download backup'}</button>{message && <p className="upload-message" role="status">{message}</p>}<div className="privacy-note"><span>◈</span><p><strong>Stored on this computer</strong><br />Student forms and backup archives are not sent to an external service.</p></div></div></section>
}
