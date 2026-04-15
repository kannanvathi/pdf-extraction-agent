<template>
  <div v-if="result" class="w-full space-y-5">

    <!-- Policy Header Card -->
    <div class="rounded-2xl bg-white border border-gray-200 shadow-sm p-5">
      <div class="flex items-start justify-between flex-wrap gap-3 mb-4">
        <div>
          <span class="inline-block px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wide bg-amber-100 text-amber-700">
            Loss Run
          </span>
          <span v-if="result.parser" class="ml-2 inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-violet-100 text-violet-700">
            {{ result.parser }}
          </span>
        </div>
        <div class="text-right text-xs text-gray-400 space-y-0.5">
          <p>{{ result.page_count }} page{{ result.page_count !== 1 ? 's' : '' }}</p>
          <p>{{ formatDate(result.extracted_at) }}</p>
        </div>
      </div>

      <!-- Policy Info grid -->
      <div v-if="hasPolicyInfo" class="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        <div v-for="[key, val] in policyFields" :key="key" class="flex flex-col">
          <span class="text-xs font-medium text-gray-400 uppercase tracking-wide">{{ humanize(key) }}</span>
          <span class="text-gray-800 font-medium mt-0.5">{{ val || '—' }}</span>
        </div>
      </div>
      <div v-else class="text-sm text-gray-400 italic">Policy header not extracted — see raw JSON or full text below.</div>
    </div>

    <!-- Summary KPIs -->
    <div v-if="hasSummary" class="grid grid-cols-2 sm:grid-cols-3 gap-3">
      <div class="rounded-xl border border-gray-200 bg-white p-4 text-center">
        <p class="text-2xl font-bold text-gray-800">{{ summary.total_claims ?? '—' }}</p>
        <p class="text-xs text-gray-400 mt-1">Total Claims</p>
      </div>
      <div class="rounded-xl border border-green-100 bg-green-50 p-4 text-center">
        <p class="text-2xl font-bold text-green-700">{{ summary.closed_claims ?? '—' }}</p>
        <p class="text-xs text-green-500 mt-1">Closed</p>
      </div>
      <div class="rounded-xl border border-red-100 bg-red-50 p-4 text-center">
        <p class="text-2xl font-bold text-red-600">{{ summary.open_claims ?? '—' }}</p>
        <p class="text-xs text-red-400 mt-1">Open</p>
      </div>
      <div class="rounded-xl border border-gray-200 bg-white p-4 text-center">
        <p class="text-lg font-bold text-gray-800">{{ fmtMoney(summary.total_paid) }}</p>
        <p class="text-xs text-gray-400 mt-1">Total Paid</p>
      </div>
      <div class="rounded-xl border border-orange-100 bg-orange-50 p-4 text-center">
        <p class="text-lg font-bold text-orange-700">{{ fmtMoney(summary.total_reserve) }}</p>
        <p class="text-xs text-orange-400 mt-1">Outstanding Reserve</p>
      </div>
      <div class="rounded-xl border border-indigo-100 bg-indigo-50 p-4 text-center">
        <p class="text-lg font-bold text-indigo-700">{{ fmtMoney(summary.total_incurred) }}</p>
        <p class="text-xs text-indigo-400 mt-1">Total Incurred</p>
      </div>
    </div>

    <!-- Claims table (shown when not hidden by parent) -->
    <section v-if="!hideTables && hasClaims">
      <h3 class="text-sm font-semibold text-gray-700 mb-3">
        Claims
        <span class="ml-2 text-xs font-normal bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
          {{ result.claims.length }}
        </span>
      </h3>
      <div class="rounded-xl border border-gray-200 overflow-hidden bg-white">
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="bg-gray-50 border-b border-gray-200">
                <th v-for="col in claimColumns" :key="col.key" class="px-3 py-2 text-left font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap">
                  {{ col.label }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(claim, i) in result.claims"
                :key="i"
                class="border-b last:border-0 hover:bg-gray-50"
              >
                <td class="px-3 py-2 font-mono text-gray-700">{{ claim.claim_number || '—' }}</td>
                <td class="px-3 py-2 text-gray-600 whitespace-nowrap">{{ claim.date_of_loss || '—' }}</td>
                <td class="px-3 py-2 text-gray-600 max-w-[160px] truncate">{{ claim.claimant_name || '—' }}</td>
                <td class="px-3 py-2 text-gray-600 max-w-[120px] truncate">{{ claim.type_of_loss || '—' }}</td>
                <td class="px-3 py-2">
                  <span
                    class="inline-block px-2 py-0.5 rounded-full text-[0.65rem] font-semibold"
                    :class="statusClass(claim.status)"
                  >{{ claim.status || '—' }}</span>
                </td>
                <td class="px-3 py-2 text-right font-mono text-gray-700">{{ fmtMoney(claim.total_paid) }}</td>
                <td class="px-3 py-2 text-right font-mono text-orange-600">{{ fmtMoney(claim.outstanding_reserve) }}</td>
                <td class="px-3 py-2 text-right font-mono font-semibold text-indigo-700">{{ fmtMoney(claim.total_incurred) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- Policy periods -->
    <section v-if="!hideTables && hasPeriods">
      <h3 class="text-sm font-semibold text-gray-700 mb-3">Policy Periods</h3>
      <div class="space-y-2">
        <div
          v-for="(period, i) in result.policy_periods"
          :key="i"
          class="rounded-xl border border-gray-200 bg-white px-4 py-3 flex flex-wrap gap-4 text-sm"
        >
          <div>
            <p class="text-xs text-gray-400">Period</p>
            <p class="font-medium text-gray-800">{{ period.period_start || '?' }} → {{ period.period_end || '?' }}</p>
          </div>
          <div v-if="period.policy_number">
            <p class="text-xs text-gray-400">Policy #</p>
            <p class="font-mono text-gray-700">{{ period.policy_number }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-400">Claims</p>
            <p class="font-semibold text-gray-800">{{ period.total_claims ?? '—' }}
              <span class="text-red-500 text-xs ml-1">{{ period.open_claims ? `(${period.open_claims} open)` : '' }}</span>
            </p>
          </div>
          <div class="ml-auto text-right">
            <p class="text-xs text-gray-400">Total Incurred</p>
            <p class="font-semibold text-indigo-700">{{ fmtMoney(period.total_incurred) }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Errors -->
    <section v-if="result.errors?.length">
      <h3 class="text-sm font-semibold text-red-500 mb-2">Extraction Warnings</h3>
      <ul class="space-y-1">
        <li
          v-for="err in result.errors"
          :key="err.field"
          class="rounded-lg bg-red-50 border border-red-100 px-4 py-2 text-xs text-red-700"
        >
          <span class="font-semibold">{{ err.field }}</span>: {{ err.reason }}
        </li>
      </ul>
    </section>

    <!-- Full document text -->
    <details v-if="fullTextHtml" class="group">
      <summary class="cursor-pointer text-xs font-medium text-indigo-500 hover:text-indigo-700 select-none">
        View full document text
      </summary>
      <div class="mt-3 rounded-xl border border-gray-200 bg-white overflow-x-auto p-6">
        <div
          class="prose prose-sm max-w-none
                 prose-headings:text-gray-800 prose-headings:font-semibold
                 prose-table:text-xs prose-table:w-full
                 prose-th:bg-gray-50 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:font-semibold prose-th:text-gray-600 prose-th:border prose-th:border-gray-200
                 prose-td:px-3 prose-td:py-2 prose-td:border prose-td:border-gray-100 prose-td:text-gray-700
                 prose-p:text-gray-600"
          v-html="fullTextHtml"
        />
      </div>
    </details>

    <!-- Raw JSON -->
    <details class="group">
      <summary class="cursor-pointer text-xs font-medium text-indigo-500 hover:text-indigo-700 select-none">
        View raw JSON
      </summary>
      <pre class="mt-2 rounded-xl bg-gray-900 text-green-300 text-xs p-4 overflow-x-auto max-h-80">{{ pretty }}</pre>
    </details>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import { useExtractionStore } from '../stores/extraction.js'

defineProps({ hideTables: { type: Boolean, default: false } })

const store  = useExtractionStore()
const result = computed(() => store.result)
const pretty = computed(() => JSON.stringify(result.value, null, 2))

const POLICY_DISPLAY_KEYS = [
  'insured_name', 'policy_number', 'line_of_business', 'insurer_name',
  'policy_period_start', 'policy_period_end', 'producer_name', 'report_date', 'state',
]

const policyFields = computed(() => {
  const info = result.value?.policy_info || {}
  return POLICY_DISPLAY_KEYS
    .filter(k => info[k] != null)
    .map(k => [k, info[k]])
})

const hasPolicyInfo = computed(() => policyFields.value.length > 0)
const hasSummary    = computed(() => result.value?.summary && typeof result.value.summary === 'object' && Object.keys(result.value.summary).length > 0)
const hasClaims     = computed(() => result.value?.claims?.length > 0)
const hasPeriods    = computed(() => result.value?.policy_periods?.length > 0)

const summary = computed(() => result.value?.summary || {})

const claimColumns = [
  { key: 'claim_number',        label: 'Claim #' },
  { key: 'date_of_loss',        label: 'Date of Loss' },
  { key: 'claimant_name',       label: 'Claimant' },
  { key: 'type_of_loss',        label: 'Type' },
  { key: 'status',              label: 'Status' },
  { key: 'total_paid',          label: 'Paid' },
  { key: 'outstanding_reserve', label: 'Reserve' },
  { key: 'total_incurred',      label: 'Incurred' },
]

const fullTextHtml = computed(() => {
  const text = result.value?.full_text
  if (!text) return ''
  return marked.parse(text)
})

function humanize(key) {
  return String(key).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatDate(iso) {
  if (!iso) return ''
  try { return new Date(iso).toLocaleString() } catch { return iso }
}

function fmtMoney(val) {
  if (val == null) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val)
}

function statusClass(status) {
  const s = (status || '').toLowerCase()
  if (s === 'open')     return 'bg-red-100 text-red-700'
  if (s === 'closed')   return 'bg-green-100 text-green-700'
  if (s === 'reopened') return 'bg-yellow-100 text-yellow-700'
  return 'bg-gray-100 text-gray-600'
}
</script>
