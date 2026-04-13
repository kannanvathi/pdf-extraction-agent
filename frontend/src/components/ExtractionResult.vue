<template>
  <div v-if="result" class="w-full space-y-6">

    <!-- Header card -->
    <div class="rounded-2xl bg-white border border-gray-200 shadow-sm p-6">
      <div class="flex items-center justify-between flex-wrap gap-3">
        <div class="flex items-center gap-2 flex-wrap">
          <span
            class="inline-block px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wide"
            :class="typeColor"
          >{{ result.doc_type }}</span>
          <span
            v-if="result.parser"
            class="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-violet-100 text-violet-700"
          >{{ result.parser }}</span>
        </div>
        <div class="text-right text-xs text-gray-400 space-y-0.5">
          <p>{{ result.page_count }} page{{ result.page_count !== 1 ? 's' : '' }}</p>
          <p>{{ formatDate(result.extracted_at) }}</p>
        </div>
      </div>
    </div>

    <!-- Extracted fields -->
    <section v-if="hasFields">
      <h3 class="section-heading">Extracted Fields</h3>
      <div class="rounded-xl border border-gray-200 overflow-hidden">
        <table class="w-full text-sm">
          <tbody>
            <tr
              v-for="(value, key) in result.fields"
              :key="key"
              class="border-b last:border-0 hover:bg-gray-50"
            >
              <td class="px-4 py-2.5 font-medium text-gray-500 w-2/5 capitalize">
                {{ humanize(key) }}
              </td>
              <td class="px-4 py-2.5 text-gray-800 break-words">{{ value ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Entities -->
    <section v-if="hasEntities">
      <h3 class="section-heading">Named Entities</h3>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div
          v-for="(items, group) in result.entities"
          :key="group"
          v-show="items?.length"
          class="rounded-xl bg-gray-50 border border-gray-200 p-3"
        >
          <p class="text-xs font-semibold text-gray-400 uppercase mb-2">{{ group }}</p>
          <ul class="space-y-1">
            <li v-for="item in items" :key="item" class="text-sm text-gray-700 truncate">
              {{ item }}
            </li>
          </ul>
        </div>
      </div>
    </section>

    <!-- Errors -->
    <section v-if="result.errors?.length">
      <h3 class="section-heading text-red-500">Extraction Warnings</h3>
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

    <!-- Full document text (markdown) -->
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
                 prose-td:px-3 prose-td:py-2 prose-td:border prose-td:border-gray-100 prose-td:text-gray-700 prose-td:align-top
                 prose-p:text-gray-600"
          v-html="fullTextHtml"
        />
      </div>
    </details>

    <!-- Raw JSON toggle -->
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

const fullTextHtml = computed(() => {
  const text = result.value?.full_text
  if (!text) return ''
  return marked.parse(text)
})

const hasFields = computed(() =>
  result.value?.fields && Object.keys(result.value.fields).length > 0
)

const hasEntities = computed(() =>
  Object.values(result.value?.entities ?? {}).some(arr => arr?.length > 0)
)

const typeColor = computed(() => ({
  invoice:  'bg-emerald-100 text-emerald-700',
  contract: 'bg-blue-100 text-blue-700',
  resume:   'bg-purple-100 text-purple-700',
  report:   'bg-amber-100 text-amber-700',
  form:     'bg-pink-100 text-pink-700',
  document: 'bg-violet-100 text-violet-700',
  unknown:  'bg-gray-100 text-gray-600',
}[result.value?.doc_type] ?? 'bg-gray-100 text-gray-600'))

function humanize(key) {
  return String(key).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatDate(iso) {
  if (!iso) return ''
  try { return new Date(iso).toLocaleString() } catch { return iso }
}
</script>

<style scoped>
.section-heading {
  @apply text-sm font-semibold text-gray-700 mb-3;
}
</style>
