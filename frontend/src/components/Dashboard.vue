<template>
  <div class="flex h-full gap-0 overflow-hidden" style="min-height: calc(100vh - 65px);">

    <!-- ── Left: Document List ──────────────────────────────────────────── -->
    <aside class="w-80 flex-shrink-0 flex flex-col border-r border-gray-200 bg-white">

      <!-- header + portfolio KPIs -->
      <div class="px-4 py-3 border-b border-gray-200">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-sm font-semibold text-gray-700 flex-1">Loss Run Portfolio</span>
          <span class="text-xs text-gray-400 tabular-nums">{{ docs.length }}</span>
          <button
            class="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
            :class="{ 'animate-spin': loading }"
            title="Refresh"
            @click="loadDocuments"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
          </button>
        </div>
        <!-- Portfolio totals strip -->
        <div class="grid grid-cols-3 gap-1 text-center">
          <div class="rounded-lg bg-gray-50 py-1.5">
            <p class="text-base font-bold text-gray-800">{{ portfolioKpis.totalClaims }}</p>
            <p class="text-[0.6rem] text-gray-400 uppercase">Claims</p>
          </div>
          <div class="rounded-lg bg-red-50 py-1.5">
            <p class="text-base font-bold text-red-600">{{ portfolioKpis.openClaims }}</p>
            <p class="text-[0.6rem] text-red-400 uppercase">Open</p>
          </div>
          <div class="rounded-lg bg-indigo-50 py-1.5">
            <p class="text-base font-bold text-indigo-700">{{ fmtMoneyShort(portfolioKpis.totalIncurred) }}</p>
            <p class="text-[0.6rem] text-indigo-400 uppercase">Incurred</p>
          </div>
        </div>
      </div>

      <!-- search -->
      <div class="px-3 py-2 border-b border-gray-100">
        <input
          v-model="search"
          type="text"
          placeholder="Search by insured, file, or ID…"
          class="w-full rounded-lg border border-gray-200 px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-400"
        />
      </div>

      <!-- list -->
      <div class="flex-1 overflow-y-auto">
        <div v-if="loading && !docs.length" class="flex items-center justify-center h-32 text-gray-400 text-sm">
          Loading…
        </div>
        <div v-else-if="!filteredDocs.length" class="flex items-center justify-center h-32 text-gray-400 text-sm">
          No documents found
        </div>

        <button
          v-for="doc in filteredDocs"
          :key="doc._id"
          class="w-full text-left px-4 py-3 border-b border-gray-100 transition-colors focus:outline-none"
          :class="activeDoc?._id === doc._id
            ? 'bg-indigo-50 border-l-4 border-l-indigo-500'
            : 'hover:bg-gray-50 border-l-4 border-l-transparent'"
          @click="selectDoc(doc)"
        >
          <div class="flex items-center gap-2 mb-1">
            <span class="text-[0.65rem] font-mono font-semibold bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded">
              {{ doc.lr_doc_id }}
            </span>
            <span
              v-if="doc.provider || doc.parser"
              class="text-[0.6rem] font-medium px-1.5 py-0.5 rounded"
              :class="providerBadgeClass(doc.provider || doc.parser)"
            >
              {{ providerLabel(doc.provider || doc.parser) }}
            </span>
          </div>
          <p class="text-xs font-medium text-gray-800 truncate leading-snug">
            {{ displayName(doc.file_name) }}
          </p>
          <div class="flex items-center gap-2 mt-1 text-[0.65rem] text-gray-400">
            <span>{{ formatDate(doc.created_at) }}</span>
            <span v-if="doc.page_count" class="text-gray-300">·</span>
            <span v-if="doc.page_count">{{ doc.page_count }}p</span>
          </div>
        </button>
      </div>
    </aside>

    <!-- ── Right: Detail Panel ──────────────────────────────────────────── -->
    <div class="flex-1 flex flex-col overflow-hidden bg-gray-50">

      <!-- empty state -->
      <div v-if="!activeDoc" class="flex-1 flex flex-col items-center justify-center text-gray-400 gap-3">
        <svg class="w-12 h-12 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414A1 1 0 0119 9.414V19a2 2 0 01-2 2z"/>
        </svg>
        <p class="text-sm">Select a loss run to view details</p>
      </div>

      <template v-else>

        <!-- doc header -->
        <div class="px-6 py-3 bg-white border-b border-gray-200 flex items-center gap-3 flex-shrink-0">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-0.5">
              <span class="text-xs font-mono font-semibold text-indigo-600">{{ activeDoc.lr_doc_id }}</span>
              <span class="text-[0.65rem] px-2 py-0.5 rounded-full font-semibold bg-amber-100 text-amber-700">Loss Run</span>
              <span
                v-if="activeDoc.provider || activeDoc.parser"
                class="text-[0.6rem] font-medium px-1.5 py-0.5 rounded"
                :class="providerBadgeClass(activeDoc.provider || activeDoc.parser)"
              >
                {{ providerLabel(activeDoc.provider || activeDoc.parser) }}
              </span>
            </div>
            <p class="text-sm font-semibold text-gray-800 truncate">{{ displayName(activeDoc.file_name) }}</p>
          </div>
          <div class="flex-shrink-0 text-right text-xs text-gray-400">
            <div>{{ formatDate(activeDoc.created_at) }}</div>
            <div v-if="activeDoc.page_count">{{ activeDoc.page_count }}p</div>
          </div>
          <button
            class="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700"
            @click="activeDoc = null; activePdfUrl = null; fullDoc = null"
          >✕</button>
        </div>

        <!-- KPI strip for selected doc -->
        <div v-if="docSummary" class="px-6 py-3 bg-white border-b border-gray-200 grid grid-cols-6 gap-3 flex-shrink-0">
          <div class="text-center">
            <p class="text-lg font-bold text-gray-800">{{ docSummary.total_claims ?? '—' }}</p>
            <p class="text-[0.65rem] text-gray-400">Total Claims</p>
          </div>
          <div class="text-center">
            <p class="text-lg font-bold text-red-600">{{ docSummary.open_claims ?? '—' }}</p>
            <p class="text-[0.65rem] text-red-400">Open</p>
          </div>
          <div class="text-center">
            <p class="text-lg font-bold text-green-600">{{ docSummary.closed_claims ?? '—' }}</p>
            <p class="text-[0.65rem] text-green-500">Closed</p>
          </div>
          <div class="text-center">
            <p class="text-lg font-bold text-gray-700">{{ fmtMoneyShort(docSummary.total_paid) }}</p>
            <p class="text-[0.65rem] text-gray-400">Paid</p>
          </div>
          <div class="text-center">
            <p class="text-lg font-bold text-orange-600">{{ fmtMoneyShort(docSummary.total_reserve) }}</p>
            <p class="text-[0.65rem] text-orange-400">Reserve</p>
          </div>
          <div class="text-center">
            <p class="text-lg font-bold text-indigo-700">{{ fmtMoneyShort(docSummary.total_incurred) }}</p>
            <p class="text-[0.65rem] text-indigo-400">Incurred</p>
          </div>
        </div>

        <!-- tabs -->
        <div class="px-6 bg-white border-b border-gray-200 flex gap-0 flex-shrink-0">
          <button
            v-for="t in detailTabs"
            :key="t.id"
            class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors"
            :class="detailTab === t.id
              ? 'border-indigo-500 text-indigo-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
            @click="detailTab = t.id"
          >{{ t.label }}</button>
        </div>

        <!-- tab content -->
        <div class="flex-1 overflow-auto">

          <!-- ── Policy + Claims ──────────────────────────────────────── -->
          <div v-show="detailTab === 'claims'" class="p-6 space-y-5">
            <div v-if="!fullDoc" class="text-gray-400 text-sm text-center py-12">Loading…</div>
            <template v-else>

              <!-- Policy info -->
              <div v-if="policyInfoFields.length" class="rounded-xl border border-gray-200 bg-white p-4">
                <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Policy Information</h3>
                <div class="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-2">
                  <div v-for="[k, v] in policyInfoFields" :key="k">
                    <p class="text-[0.65rem] font-medium text-gray-400 uppercase">{{ humanize(k) }}</p>
                    <p class="text-sm text-gray-800 font-medium">{{ v || '—' }}</p>
                  </div>
                </div>
              </div>

              <!-- Policy periods -->
              <div v-if="fullDoc.policy_periods?.length" class="rounded-xl border border-gray-200 bg-white overflow-hidden">
                <div class="px-4 py-2.5 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
                  <span class="text-xs font-semibold text-gray-600 uppercase tracking-wide">Policy Periods</span>
                  <span class="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-medium">
                    {{ fullDoc.policy_periods.length }}
                  </span>
                </div>
                <div class="divide-y divide-gray-100">
                  <div
                    v-for="(period, i) in fullDoc.policy_periods"
                    :key="i"
                    class="px-4 py-3 flex flex-wrap gap-4 items-center text-sm"
                  >
                    <div class="w-36">
                      <p class="text-xs text-gray-400">Period</p>
                      <p class="font-medium text-gray-800 text-xs">{{ period.period_start || '?' }} → {{ period.period_end || '?' }}</p>
                    </div>
                    <div v-if="period.policy_number" class="w-32">
                      <p class="text-xs text-gray-400">Policy #</p>
                      <p class="font-mono text-xs text-gray-700">{{ period.policy_number }}</p>
                    </div>
                    <div class="flex gap-4 ml-auto text-right">
                      <div>
                        <p class="text-xs text-gray-400">Claims</p>
                        <p class="font-semibold text-gray-800">{{ period.total_claims ?? '—' }}
                          <span v-if="period.open_claims" class="text-red-500 text-xs">({{ period.open_claims }} open)</span>
                        </p>
                      </div>
                      <div>
                        <p class="text-xs text-gray-400">Incurred</p>
                        <p class="font-semibold text-indigo-700">{{ fmtMoney(period.total_incurred) }}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Claims table -->
              <div v-if="fullDoc.claims?.length" class="rounded-xl border border-gray-200 bg-white overflow-hidden">
                <div class="px-4 py-2.5 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
                  <span class="text-xs font-semibold text-gray-600 uppercase tracking-wide">Claims</span>
                  <span class="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                    {{ fullDoc.claims.length }}
                  </span>
                </div>
                <div class="overflow-x-auto">
                  <table class="w-full text-xs">
                    <thead>
                      <tr class="bg-gray-50 border-b border-gray-200">
                        <th class="px-3 py-2 text-left font-semibold text-gray-500 whitespace-nowrap">Claim #</th>
                        <th class="px-3 py-2 text-left font-semibold text-gray-500 whitespace-nowrap">Date of Loss</th>
                        <th class="px-3 py-2 text-left font-semibold text-gray-500">Claimant</th>
                        <th class="px-3 py-2 text-left font-semibold text-gray-500">Type</th>
                        <th class="px-3 py-2 text-left font-semibold text-gray-500">Status</th>
                        <th class="px-3 py-2 text-right font-semibold text-gray-500 whitespace-nowrap">Total Paid</th>
                        <th class="px-3 py-2 text-right font-semibold text-gray-500 whitespace-nowrap">Reserve</th>
                        <th class="px-3 py-2 text-right font-semibold text-gray-500 whitespace-nowrap">Total Incurred</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="(claim, i) in fullDoc.claims"
                        :key="i"
                        class="border-b last:border-0 hover:bg-gray-50"
                      >
                        <td class="px-3 py-2 font-mono text-gray-700">{{ claim.claim_number || '—' }}</td>
                        <td class="px-3 py-2 text-gray-600 whitespace-nowrap">{{ claim.date_of_loss || '—' }}</td>
                        <td class="px-3 py-2 text-gray-700 max-w-[140px] truncate">{{ claim.claimant_name || '—' }}</td>
                        <td class="px-3 py-2 text-gray-600 max-w-[120px] truncate">{{ claim.type_of_loss || '—' }}</td>
                        <td class="px-3 py-2">
                          <span class="inline-block px-2 py-0.5 rounded-full text-[0.6rem] font-semibold" :class="statusClass(claim.status)">
                            {{ claim.status || '—' }}
                          </span>
                        </td>
                        <td class="px-3 py-2 text-right font-mono text-gray-700">{{ fmtMoney(claim.total_paid) }}</td>
                        <td class="px-3 py-2 text-right font-mono text-orange-600">{{ fmtMoney(claim.outstanding_reserve) }}</td>
                        <td class="px-3 py-2 text-right font-mono font-semibold text-indigo-700">{{ fmtMoney(claim.total_incurred) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div v-if="!policyInfoFields.length && !fullDoc.claims?.length && !fullDoc.policy_periods?.length"
                   class="text-center py-12 text-gray-400 text-sm">
                No structured loss run data extracted — try with an AI provider (OpenAI / Anthropic / Gemini).
              </div>
            </template>
          </div>

          <!-- ── PDF View ──────────────────────────────────────────────── -->
          <div v-show="detailTab === 'pdf'" class="p-6">
            <div v-if="pdfLoading" class="flex items-center justify-center h-48 text-gray-400 text-sm">Loading PDF…</div>
            <div v-else-if="pdfError" class="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-700">
              {{ pdfError }}
            </div>
            <PdfViewer
              v-else-if="activePdfUrl"
              :pdf-url="activePdfUrl"
              :pages="fullDoc?.pages ?? []"
              :doc-id="activeDoc?._id ?? null"
            />
          </div>

          <!-- ── Raw Tables ────────────────────────────────────────────── -->
          <div v-show="detailTab === 'tables'" class="p-6">
            <div v-if="!fullDoc" class="text-gray-400 text-sm text-center py-12">Loading…</div>
            <div v-else-if="!fullDoc.table_data?.length" class="text-gray-400 text-sm text-center py-12">
              No raw tables extracted.
            </div>
            <template v-else>
              <div class="flex items-center gap-3 mb-4">
                <h3 class="text-sm font-semibold text-gray-700">Raw Extracted Tables</h3>
                <span class="text-xs font-medium bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full">
                  {{ fullDoc.table_data.length }}
                </span>
              </div>
              <div v-for="table in fullDoc.table_data" :key="table.name" class="mb-6 rounded-xl border border-gray-200 overflow-hidden bg-white">
                <div class="flex items-center justify-between px-4 py-2.5 bg-gray-50 border-b border-gray-200">
                  <span class="text-xs font-semibold text-gray-600 uppercase tracking-wide">{{ table.name }}</span>
                  <span class="text-xs text-gray-400">{{ table.rows?.length }} rows</span>
                </div>
                <q-table
                  :rows="table.rows ?? []"
                  :columns="buildColumns(table)"
                  :row-key="buildColumns(table)[0]?.name ?? 'index'"
                  flat dense bordered
                  :pagination="{ rowsPerPage: 15 }"
                  class="qtable-full"
                >
                  <template #no-data>
                    <div class="text-center py-6 text-gray-400 text-sm w-full">No data</div>
                  </template>
                </q-table>
              </div>
            </template>
          </div>

          <!-- ── JSON ─────────────────────────────────────────────────── -->
          <div v-show="detailTab === 'json'" class="p-6">
            <div v-if="!fullDoc" class="text-gray-400 text-sm text-center py-12">Loading…</div>
            <template v-else>
              <div class="flex items-center gap-3 mb-3">
                <h3 class="text-sm font-semibold text-gray-700">Raw Extraction Data</h3>
                <button
                  class="ml-auto text-xs px-3 py-1 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-600 transition-colors"
                  @click="copyJson"
                >{{ copied ? '✓ Copied' : 'Copy JSON' }}</button>
              </div>
              <pre
                class="text-xs font-mono bg-gray-900 rounded-xl p-4 overflow-auto leading-relaxed"
                style="max-height: calc(100vh - 300px);"
                v-html="highlightedJson"
              ></pre>
            </template>
          </div>

        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import PdfViewer from './PdfViewer.vue'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const POLICY_DISPLAY_KEYS = [
  'insured_name', 'policy_number', 'line_of_business', 'insurer_name',
  'policy_period_start', 'policy_period_end', 'producer_name', 'report_date', 'state',
]

// ── State ──────────────────────────────────────────────────────────────────
const docs         = ref([])
const loading      = ref(false)
const search       = ref('')
const activeDoc    = ref(null)
const fullDoc      = ref(null)
const activePdfUrl = ref(null)
const pdfLoading   = ref(false)
const pdfError     = ref(null)
const detailTab    = ref('claims')
const copied       = ref(false)

const detailTabs = [
  { id: 'claims', label: 'Policy & Claims' },
  { id: 'pdf',    label: 'PDF View'        },
  { id: 'tables', label: 'Raw Tables'      },
  { id: 'json',   label: 'JSON'            },
]

// ── Portfolio KPIs (computed across all docs in list) ─────────────────────
const portfolioKpis = computed(() => {
  return docs.value.reduce((acc, doc) => {
    const s = doc.summary || {}
    acc.totalClaims   += s.total_claims   ?? 0
    acc.openClaims    += s.open_claims    ?? 0
    acc.totalIncurred += s.total_incurred ?? 0
    return acc
  }, { totalClaims: 0, openClaims: 0, totalIncurred: 0 })
})

// ── Active doc derived state ───────────────────────────────────────────────
const docSummary = computed(() => {
  if (!fullDoc.value?.summary) return null
  const s = fullDoc.value.summary
  if (Object.keys(s).length === 0) return null
  return s
})

const policyInfoFields = computed(() => {
  const info = fullDoc.value?.policy_info || {}
  return POLICY_DISPLAY_KEYS.filter(k => info[k] != null).map(k => [k, info[k]])
})

// ── Filtered list ──────────────────────────────────────────────────────────
const filteredDocs = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return docs.value
  return docs.value.filter(d =>
    d.lr_doc_id?.toLowerCase().includes(q) ||
    d.file_name?.toLowerCase().includes(q) ||
    d.policy_info?.insured_name?.toLowerCase().includes(q) ||
    d.provider?.toLowerCase().includes(q)
  )
})

// ── Load documents ─────────────────────────────────────────────────────────
async function loadDocuments() {
  loading.value = true
  try {
    const res  = await fetch(`${API}/documents?limit=100`)
    const data = await res.json()
    docs.value = data.results ?? []
  } catch (err) {
    console.error('loadDocuments failed:', err)
  } finally {
    loading.value = false
  }
}

// ── Select document ────────────────────────────────────────────────────────
async function selectDoc(doc) {
  activeDoc.value    = doc
  fullDoc.value      = null
  activePdfUrl.value = null
  pdfError.value     = null
  detailTab.value    = 'claims'

  const [fullResult, pdfResult] = await Promise.allSettled([
    fetchFullDoc(doc._id),
    fetchPdf(doc._id),
  ])
  if (fullResult.status === 'fulfilled') fullDoc.value = fullResult.value
  if (pdfResult.status === 'fulfilled')  activePdfUrl.value = pdfResult.value
  else pdfError.value = pdfResult.reason?.message ?? 'PDF file not available on server.'
}

async function fetchFullDoc(id) {
  const res = await fetch(`${API}/extractions/${id}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

async function fetchPdf(id) {
  pdfLoading.value = true
  try {
    const res = await fetch(`${API}/pdf/${id}`)
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? `HTTP ${res.status}`)
    }
    const blob = await res.blob()
    return URL.createObjectURL(blob)
  } finally {
    pdfLoading.value = false
  }
}

// ── JSON highlight ─────────────────────────────────────────────────────────
const highlightedJson = computed(() => {
  if (!fullDoc.value) return ''
  const raw = JSON.stringify(fullDoc.value, null, 2)
  return raw
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(
      /("(\\u[\dA-Fa-f]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
      match => {
        if (/^"/.test(match))
          return /:$/.test(match)
            ? `<span style="color:#fbbf24">${match}</span>`
            : `<span style="color:#86efac">${match}</span>`
        if (/true|false/.test(match)) return `<span style="color:#c084fc">${match}</span>`
        if (/null/.test(match))       return `<span style="color:#f87171">${match}</span>`
        return `<span style="color:#93c5fd">${match}</span>`
      }
    )
})

async function copyJson() {
  if (!fullDoc.value) return
  await navigator.clipboard.writeText(JSON.stringify(fullDoc.value, null, 2))
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

// ── q-table helper ─────────────────────────────────────────────────────────
function buildColumns(table) {
  const cols = table.columns ?? (table.rows?.length ? Object.keys(table.rows[0]) : [])
  return cols.map(key => ({
    name: key,
    label: String(key).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    field: key,
    align: 'left',
    sortable: true,
  }))
}

// ── Helpers ────────────────────────────────────────────────────────────────
function displayName(filename) {
  if (!filename) return 'Unknown'
  return filename.replace(/^[\da-f-]{36}_/i, '')
}

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function humanize(key) {
  return String(key).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function fmtMoney(val) {
  if (val == null) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val)
}

function fmtMoneyShort(val) {
  if (val == null || val === 0) return '—'
  if (Math.abs(val) >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`
  if (Math.abs(val) >= 1_000)     return `$${(val / 1_000).toFixed(0)}K`
  return `$${val}`
}

function statusClass(status) {
  const s = (status || '').toLowerCase()
  if (s === 'open')     return 'bg-red-100 text-red-700'
  if (s === 'closed')   return 'bg-green-100 text-green-700'
  if (s === 'reopened') return 'bg-yellow-100 text-yellow-700'
  return 'bg-gray-100 text-gray-600'
}

function providerLabel(raw) {
  if (!raw) return ''
  return {
    llamaparse: 'LlamaParse', 'llamaparse/markdown': 'LlamaParse',
    'llamaparse/text': 'LlamaParse', liteparse: 'LiteParse',
    openai: 'OpenAI', gemini: 'Gemini', anthropic: 'Claude',
  }[raw] ?? raw.split('/')[0].toUpperCase()
}

function providerBadgeClass(raw) {
  const id = (raw ?? '').split('/')[0]
  return {
    llamaparse: 'bg-violet-100 text-violet-700',
    liteparse:  'bg-teal-100 text-teal-700',
    openai:     'bg-green-100 text-green-700',
    gemini:     'bg-blue-100 text-blue-700',
    anthropic:  'bg-purple-100 text-purple-700',
  }[id] ?? 'bg-gray-100 text-gray-600'
}

onMounted(loadDocuments)
</script>

<style scoped>
aside { min-height: 0; }
</style>
