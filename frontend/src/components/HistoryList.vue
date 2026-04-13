<template>
  <div class="w-full">
    <!-- Search / filter bar -->
    <div class="flex items-center gap-2 mb-4">
      <input
        v-model="userId"
        type="text"
        placeholder="Enter user ID to load history…"
        class="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
        @keyup.enter="load"
      />
      <button
        class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 active:scale-[0.97] transition-all"
        @click="load"
      >Load</button>
    </div>

    <!-- Empty state -->
    <div v-if="!store.history.length && !loading" class="text-center py-12 text-gray-400 text-sm">
      No history yet. Enter a user ID above to fetch past extractions.
    </div>

    <!-- Loading spinner -->
    <div v-if="loading" class="flex justify-center py-10">
      <span class="h-6 w-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></span>
    </div>

    <!-- History cards -->
    <ul v-else class="space-y-3">
      <li
        v-for="doc in store.history"
        :key="doc._id"
        class="rounded-xl border border-gray-200 bg-white p-4 hover:border-indigo-300 hover:shadow-sm transition-all cursor-pointer"
        @click="store.viewResult(doc)"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span
                class="inline-block px-2 py-0.5 rounded-full text-xs font-semibold uppercase"
                :class="typeColor(doc.doc_type)"
              >{{ doc.doc_type }}</span>
              <span class="text-sm font-medium text-gray-700 truncate">{{ doc.file_name }}</span>
            </div>
            <p class="mt-1 text-xs text-gray-500 line-clamp-2">{{ doc.summary }}</p>
          </div>
          <div class="flex-shrink-0 text-right text-xs text-gray-400 space-y-0.5">
            <p>{{ doc.page_count }}p</p>
            <p>{{ timeAgo(doc.created_at) }}</p>
          </div>
        </div>

        <!-- Mini entity chips -->
        <div v-if="topEntities(doc).length" class="mt-2 flex flex-wrap gap-1">
          <span
            v-for="entity in topEntities(doc)"
            :key="entity"
            class="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
          >{{ entity }}</span>
        </div>
      </li>
    </ul>

    <!-- Load more -->
    <div v-if="store.history.length && !store.historyMeta.exhausted" class="mt-4 text-center">
      <button
        class="text-sm text-indigo-600 hover:underline"
        @click="loadMore"
      >Load more</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useExtractionStore } from '../stores/extraction.js'

const store   = useExtractionStore()
const userId  = ref('')
const loading = ref(false)

async function load() {
  if (!userId.value.trim()) return
  loading.value = true
  store.historyMeta.skip       = 0
  store.historyMeta.exhausted  = false
  await store.fetchHistory(userId.value.trim())
  loading.value = false
}

async function loadMore() {
  await store.fetchHistory(userId.value.trim(), { append: true })
}

function typeColor(type) {
  return ({
    invoice:  'bg-emerald-100 text-emerald-700',
    contract: 'bg-blue-100 text-blue-700',
    resume:   'bg-purple-100 text-purple-700',
    report:   'bg-amber-100 text-amber-700',
    form:     'bg-pink-100 text-pink-700',
    unknown:  'bg-gray-100 text-gray-600',
  }[type] ?? 'bg-gray-100 text-gray-600')
}

function topEntities(doc) {
  const all = [
    ...(doc.entities?.persons ?? []),
    ...(doc.entities?.orgs    ?? []),
  ]
  return all.slice(0, 3)
}

function timeAgo(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const min  = Math.floor(diff / 60_000)
  if (min < 1)   return 'just now'
  if (min < 60)  return `${min}m ago`
  const hrs = Math.floor(min / 60)
  if (hrs < 24)  return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}
</script>
