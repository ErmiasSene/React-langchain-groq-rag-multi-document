import { useEffect, useRef, useState } from 'react'
import { uploadDocuments, askQuestion, checkHealth } from './api.js'

export default function App() {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [stamp, setStamp] = useState(null) // { chunks, count } after a successful ingest
  const [uploadError, setUploadError] = useState('')

  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)

  const [backendOnline, setBackendOnline] = useState(null) // null = checking
  const chatEndRef = useRef(null)

  useEffect(() => {
    checkHealth()
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false))
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, asking])

  async function handleUpload(e) {
    e.preventDefault()
    if (files.length === 0) return
    setUploading(true)
    setUploadError('')
    setStamp(null)
    try {
      const data = await uploadDocuments(files)
      const match = data.message?.match(/(\d+) file.*?(\d+) chunk/)
      setStamp({
        files: match ? match[1] : files.length,
        chunks: match ? match[2] : '—',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      })
      setFiles([])
    } catch (err) {
      setUploadError(err.message)
    } finally {
      setUploading(false)
    }
  }

  async function handleAsk(e) {
    e.preventDefault()
    const q = question.trim()
    if (!q || asking) return

    setMessages((m) => [...m, { role: 'user', content: q }])
    setQuestion('')
    setAsking(true)

    try {
      const data = await askQuestion(q)
      setMessages((m) => [...m, { role: 'assistant', content: data.answer }])
    } catch (err) {
      setMessages((m) => [...m, { role: 'error', content: err.message }])
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="page">
      <header className="masthead">
        <div className="masthead-title">
          <span className="eyebrow">Document Assistant</span>
          <h1>The Reading Room</h1>
        </div>
        <div className={`status status--${backendOnline === null ? 'pending' : backendOnline ? 'up' : 'down'}`}>
          <span className="status-dot" />
          {backendOnline === null ? 'checking service…' : backendOnline ? 'service online' : 'service unreachable'}
        </div>
      </header>

      <main className="layout">
        <section className="tray-panel" aria-label="Document intake">
          <h2>Intake Tray</h2>
          <p className="hint">Deposit PDFs here. They're indexed before you can ask anything about them.</p>

          <form onSubmit={handleUpload} className="tray">
            <label className="dropzone">
              <input
                type="file"
                accept="application/pdf"
                multiple
                onChange={(e) => setFiles(Array.from(e.target.files))}
              />
              <span className="dropzone-mark">＋</span>
              <span>{files.length > 0 ? `${files.length} file(s) selected` : 'Choose PDFs'}</span>
            </label>

            {files.length > 0 && (
              <ul className="file-list">
                {files.map((f, i) => (
                  <li key={i}>{f.name}</li>
                ))}
              </ul>
            )}

            <button type="submit" disabled={files.length === 0 || uploading} className="btn-primary">
              {uploading ? 'Filing into the archive…' : 'Ingest documents'}
            </button>
          </form>

          {uploadError && <p className="error-text">{uploadError}</p>}

          {stamp && (
            <div className="stamp">
              <div className="stamp-inner">
                <span className="stamp-label">Filed</span>
                <span className="stamp-detail">{stamp.files} doc(s) · {stamp.chunks} chunks</span>
                <span className="stamp-time">{stamp.time}</span>
              </div>
            </div>
          )}
        </section>

        <section className="chat-panel" aria-label="Ask questions about your documents">
          <h2>Marginalia</h2>
          <p className="hint">Ask about anything in the ingested documents.</p>

          <div className="chat-log">
            {messages.length === 0 && (
              <p className="empty-note">No notes yet — ingest a document, then ask your first question.</p>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`entry entry--${m.role}`}>
                <span className="entry-index">{String(i + 1).padStart(2, '0')}</span>
                <div className="entry-body">
                  <span className="entry-role">
                    {m.role === 'user' ? 'You' : m.role === 'assistant' ? 'Assistant' : 'Error'}
                  </span>
                  <p>{m.content}</p>
                </div>
              </div>
            ))}
            {asking && (
              <div className="entry entry--assistant entry--pending">
                <span className="entry-index">…</span>
                <div className="entry-body">
                  <span className="entry-role">Assistant</span>
                  <p className="pending-text">reading the archive…</p>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <form onSubmit={handleAsk} className="ask-form">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="What does the document say about…"
            />
            <button type="submit" disabled={!question.trim() || asking} className="btn-primary">
              Ask
            </button>
          </form>
        </section>
      </main>
    </div>
  )
}
