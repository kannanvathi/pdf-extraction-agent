<template>
  <div class="min-h-screen bg-gray-50 text-gray-900">
    <!-- Top nav -->
    <header class="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
      <svg class="h-7 w-7 text-indigo-600" fill="currentColor" viewBox="0 0 24 24">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm4 18H6V4h7v5h5v11z"/>
      </svg>
      <span class="text-lg font-bold tracking-tight">PDF Extraction Agent</span>
      <nav class="ml-auto flex gap-1">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
          :class="activeTab === tab.id
            ? 'bg-indigo-100 text-indigo-700'
            : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'"
          @click="activeTab = tab.id"
        >{{ tab.label }}</button>
      </nav>
    </header>

    <!-- Main -->
    <main :class="activeTab === 'dashboard' ? '' : 'py-8'">

      <!-- ── Extract tab ───────────────────────────────────────────────── -->
      <div v-show="activeTab === 'extract'">

        <!-- Upload + result summary (centered, constrained width) -->
        <div class="mx-auto max-w-5xl px-4">
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div>
              <h2 class="text-base font-semibold text-gray-700 mb-4">Upload Document</h2>
              <PdfUploader />
            </div>
            <div>
              <h2 class="text-base font-semibold text-gray-700 mb-4">
                Extraction Result
                <span v-if="store.status === 'done'" class="ml-2 text-xs font-normal text-emerald-600">✓ Complete</span>
              </h2>
              <div
                v-if="store.status === 'idle'"
                class="rounded-2xl border-2 border-dashed border-gray-200 flex items-center justify-center min-h-[200px] text-gray-400 text-sm"
              >
                Results will appear here after extraction
              </div>
              <!-- Summary/fields/entities — no tables here -->
              <ExtractionResult v-else :hide-tables="true" />
            </div>
          </div>
        </div>

        <!-- Full-width table section -->
        <div
          v-if="store.result?.table_data?.length"
          class="mt-8 px-4"
        >
          <div class="flex items-center gap-3 mb-4 max-w-5xl mx-auto">
            <h2 class="text-base font-semibold text-gray-700">
              Extracted Tables
            </h2>
            <span class="text-xs font-medium bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full">
              {{ store.result.table_data.length }} table{{ store.result.table_data.length !== 1 ? 's' : '' }}
            </span>
          </div>

          <div
            v-for="table in store.result.table_data"
            :key="table.name"
            class="mb-6 rounded-xl border border-gray-200 overflow-hidden bg-white"
          >
            <!-- table header bar -->
            <div class="flex items-center justify-between px-4 py-2.5 bg-gray-50 border-b border-gray-200">
              <span class="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                {{ table.name }}
              </span>
              <span class="text-xs text-gray-400">
                {{ table.rows?.length }} row{{ table.rows?.length !== 1 ? 's' : '' }}
              </span>
            </div>

            <q-table
              :rows="table.rows ?? []"
              :columns="buildColumns(table)"
              :row-key="buildColumns(table)[0]?.name ?? 'index'"
              flat
              dense
              bordered
              :pagination="{ rowsPerPage: 15 }"
              rows-per-page-label="Rows per page"
              class="qtable-full"
            >
              <template #no-data>
                <div class="text-center py-6 text-gray-400 text-sm w-full">No data</div>
              </template>
            </q-table>
          </div>
        </div>

      </div>

      <!-- ── PDF View tab (LiteParse only) ──────────────────────────────── -->
      <div v-show="activeTab === 'pdfview'" class="mx-auto max-w-5xl px-4">
        <div class="flex items-center gap-3 mb-4">
          <h2 class="text-base font-semibold text-gray-700">PDF Viewer</h2>
          <span class="text-xs font-medium bg-teal-100 text-teal-700 px-2 py-0.5 rounded-full">
            LiteParse · {{ store.result?.pages?.length ?? 0 }} pages
          </span>
        </div>
        <PdfViewer
          v-if="store.pdfUrl"
          :pdf-url="store.pdfUrl"
          :pages="store.result?.pages ?? []"
          :doc-id="store.result?._id ?? null"
        />
      </div>

      <!-- ── Dashboard tab ───────────────────────────────────────────────── -->
      <div v-show="activeTab === 'dashboard'" class="h-full">
        <Dashboard />
      </div>

      <!-- ── History tab ───────────────────────────────────────────────── -->
      <div v-show="activeTab === 'history'" class="mx-auto max-w-5xl px-4">
        <h2 class="text-base font-semibold text-gray-700 mb-4">Extraction History</h2>
        <HistoryList />
      </div>

    </main>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import PdfUploader      from './components/PdfUploader.vue'
import ExtractionResult from './components/ExtractionResult.vue'
import HistoryList      from './components/HistoryList.vue'
import PdfViewer        from './components/PdfViewer.vue'
import Dashboard        from './components/Dashboard.vue'
import { useExtractionStore } from './stores/extraction.js'

const store     = useExtractionStore()
const activeTab = ref('extract')

const showPdfViewer = computed(() =>
  store.activeProvider === 'liteparse' && store.result && store.pdfUrl
)

const tabs = computed(() => [
  { id: 'extract',   label: 'Extract'    },
  ...(showPdfViewer.value ? [{ id: 'pdfview', label: 'PDF View' }] : []),
  { id: 'dashboard', label: 'Dashboard'  },
  { id: 'history',   label: 'History'    },
])

function buildColumns(table) {
  const cols = table.columns ?? (table.rows?.length ? Object.keys(table.rows[0]) : [])
  return cols.map(key => ({
    name:     key,
    label:    String(key).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    field:    key,
    align:    'left',
    sortable: true,
  }))
}
</script>

<style>
/* Full-width q-table styles (not scoped — applied globally to qtable-full class) */
.qtable-full {
  font-size: 0.75rem;
  border-radius: 0 !important;
  width: 100%;
}
.qtable-full .q-table__top,
.qtable-full .q-table__bottom {
  padding: 8px 16px;
  font-size: 0.75rem;
}
.qtable-full thead tr th {
  background-color: #f9fafb !important;
  color: #6b7280 !important;
  font-weight: 600 !important;
  font-size: 0.7rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.05em !important;
  padding: 8px 12px !important;
  position: sticky !important;
  top: 0 !important;
  z-index: 1 !important;
  white-space: nowrap;
}
.qtable-full tbody tr td {
  padding: 6px 12px !important;
  color: #374151 !important;
  vertical-align: top !important;
  max-width: 240px;
  white-space: normal;
  word-break: break-word;
}
.qtable-full tbody tr:hover td {
  background-color: #f9fafb !important;
}
</style>
