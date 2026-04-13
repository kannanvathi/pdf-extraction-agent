/**
 * Pinia store — manages provider selection, upload, SSE streaming,
 * extraction results, and user history.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

export const useExtractionStore = defineStore('extraction', () => {
  // ── Provider state ────────────────────────────────────────────────────
  const providers      = ref([])
  const activeProvider = ref('openai')
  const activeModel    = ref('')

  // ── Job state ─────────────────────────────────────────────────────────
  const status        = ref('idle')
  const jobId         = ref(null)
  const progress      = ref([])
  const result        = ref(null)
  const error         = ref(null)
  const pdfUrl        = ref(null)   // blob URL of the most recently uploaded PDF
  const history       = ref([])
  const historyMeta   = ref({ skip: 0, limit: 20, exhausted: false })

  let eventSource  = null

  // ── Computed ──────────────────────────────────────────────────────────
  const isLoading = computed(() =>
    status.value === 'uploading' || status.value === 'streaming'
  )

  const currentProvider = computed(() =>
    providers.value.find(p => p.id === activeProvider.value) || null
  )

  // ── Provider actions ──────────────────────────────────────────────────

  async function fetchProviders() {
    try {
      const res  = await fetch(`${API}/providers`)
      const data = await res.json()
      providers.value      = data.providers
      activeProvider.value = data.active
      const ap = data.providers.find(p => p.id === data.active)
      if (ap) activeModel.value = ap.models[0]
    } catch (err) {
      console.error('fetchProviders failed:', err)
    }
  }

  function setProvider(providerId) {
    activeProvider.value = providerId
    const p = providers.value.find(p => p.id === providerId)
    if (p) activeModel.value = p.models[0]
  }

  // ── Upload + SSE ──────────────────────────────────────────────────────

  async function uploadPdf(file, { userId = null, docType = null } = {}) {
    reset()
    status.value = 'uploading'
    // Store a blob URL so PdfViewer can render the original document
    if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value)
    pdfUrl.value = URL.createObjectURL(file)

    const form = new FormData()
    form.append('file', file)
    if (userId)           form.append('user_id', userId)
    if (docType)          form.append('doc_type', docType)
    form.append('provider', activeProvider.value)
    if (activeModel.value) form.append('model', activeModel.value)

    let res
    try {
      res = await fetch(`${API}/extract`, { method: 'POST', body: form })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `Upload failed: ${res.statusText}`)
      }
    } catch (err) {
      _setError(err.message)
      return
    }

    const json = await res.json()

    if (json.status === 'cached') {
      result.value = json.result
      status.value = 'done'
      return
    }

    jobId.value = json.job_id
    _openStream(json.job_id)
  }

  function _openStream(id) {
    status.value = 'streaming'
    eventSource = new EventSource(`${API}/jobs/${id}/stream`)

    eventSource.addEventListener('started', (e) => {
      const d = JSON.parse(e.data)
      progress.value.push({
        type: 'started',
        message: `Job started · ${d.provider?.toUpperCase()} ${d.model || ''}`
      })
    })

    eventSource.addEventListener('step', (e) => {
      const d = JSON.parse(e.data)
      progress.value.push({ type: 'step', message: d.message })
    })

    eventSource.addEventListener('result', (e) => {
      const d = JSON.parse(e.data)
      result.value = d.envelope
      status.value = 'done'
      _closeStream()
    })

    eventSource.addEventListener('error', (e) => {
      try {
        const d = JSON.parse(e.data)
        _setError(d.reason)
      } catch {
        _setError('Extraction error')
      }
      _closeStream()
    })

    let _retries = 0
    eventSource.onerror = () => {
      if (status.value === 'done') { _closeStream(); return }
      _retries++
      if (_retries >= 3) {
        _setError('SSE connection dropped after retries')
        _closeStream()
      }
    }
  }

  function _closeStream() {
    if (eventSource) { eventSource.close(); eventSource = null }
  }

  // ── History ───────────────────────────────────────────────────────────

  async function fetchHistory(userId, { append = false } = {}) {
    if (historyMeta.value.exhausted && append) return
    const skip  = append ? historyMeta.value.skip : 0
    const limit = historyMeta.value.limit
    try {
      const res  = await fetch(`${API}/history/${userId}?skip=${skip}&limit=${limit}`)
      const data = await res.json()
      history.value = append ? [...history.value, ...data.results] : data.results
      historyMeta.value.skip = skip + data.results.length
      if (data.results.length < limit) historyMeta.value.exhausted = true
    } catch (err) {
      console.error('fetchHistory failed:', err)
    }
  }

  function viewResult(doc) {
    result.value = doc
    status.value = 'done'
    error.value  = null
    progress.value = []
  }

  function reset() {
    _closeStream()
    status.value   = 'idle'
    jobId.value    = null
    progress.value = []
    result.value   = null
    error.value    = null
    if (pdfUrl.value) { URL.revokeObjectURL(pdfUrl.value); pdfUrl.value = null }
  }

  function _setError(msg) {
    error.value  = msg
    status.value = 'error'
  }

  return {
    providers, activeProvider, activeModel, currentProvider,
    status, jobId, progress, result, error, pdfUrl, history, historyMeta,
    isLoading,
    fetchProviders, setProvider,
    uploadPdf, fetchHistory, viewResult, reset,
  }
})
