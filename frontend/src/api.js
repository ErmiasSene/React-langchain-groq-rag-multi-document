// Set VITE_API_URL in .env (local) or in Vercel's project settings (production)
// to your Render backend URL, e.g. https://rag-groq-backend.onrender.com
const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export async function uploadDocuments(files) {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file)
  }

  const res = await fetch(`${API_URL}/upload`, {
    method: 'POST',
    body: formData,
  })

  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || `Upload failed (${res.status})`)
  }
  return data
}

export async function askQuestion(question) {
  const res = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })

  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || `Query failed (${res.status})`)
  }
  return data
}

export async function checkHealth() {
  const res = await fetch(`${API_URL}/health`)
  if (!res.ok) throw new Error('Backend unreachable')
  return res.json()
}
