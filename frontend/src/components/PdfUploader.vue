<template>
  <div class="w-full max-w-xl mx-auto space-y-4">

    <!-- Provider switcher -->
    <div class="rounded-2xl border border-gray-200 bg-white p-4">
      <p class="text-xs font-semibold text-gray-400 uppercase mb-3">AI Provider</p>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="p in store.providers"
          :key="p.id"
          :disabled="!p.available"
          class="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border-2 transition-all duration-150"
          :class="providerBtnClass(p)"
          @click="p.available && store.setProvider(p.id)"
          :title="!p.available ? 'API key not configured' : ''"
        >
          <span class="text-base">{{ providerIcon(p.id) }}</span>
          <span>{{ p.label }}</span>
          <span v-if="!p.available" class="text-xs opacity-50">no key</span>
        </button>
      </div>

      <!-- Model selector -->
      <div v-if="store.currentProvider" class="mt-3 flex items-center gap-2">
        <label class="text-xs text-gray-500 w-14 flex-shrink-0">Model</label>
        <select
          v-model="store.activeModel"
          class="flex-1 rounded-lg border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
        >
          <option v-for="m in store.currentProvider.models" :key="m" :value="m">{{ m }}</option>
        </select>
        <span class="h-2 w-2 rounded-full flex-shrink-0" :class="`bg-${store.currentProvider.color}-400`"></span>
      </div>
    </div>

    <!-- Drop zone -->
    <div
      class="relative border-2 border-dashed rounded-2xl p-10 text-center transition-colors duration-200 cursor-pointer"
      :class="[
        isDragging
          ? 'border-indigo-500 bg-indigo-50'
          : 'border-gray-300 bg-white hover:border-indigo-400 hover:bg-gray-50'
      ]"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="onDrop"
      @click="fileInput.click()"
    >
      <input ref="fileInput" type="file" accept=".pdf" class="hidden" @change="onFileChange" />

      <div v-if="!selectedFile">
        <svg class="mx-auto mb-3 h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
        </svg>
        <p class="text-sm font-medium text-gray-600">
          Drop a Loss Run PDF here, or <span class="text-indigo-600 underline">browse</span>
        </p>
        <p class="mt-1 text-xs text-gray-400">PDF files only · up to 50 MB</p>
      </div>

      <div v-else class="flex items-center justify-center gap-3">
        <svg class="h-8 w-8 text-red-500 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm4 18H6V4h7v5h5v11z"/>
        </svg>
        <div class="text-left">
          <p class="text-sm font-semibold text-gray-800 truncate max-w-xs">{{ selectedFile.name }}</p>
          <p class="text-xs text-gray-400">{{ fileSize }}</p>
        </div>
        <button class="ml-auto text-gray-400 hover:text-red-500" @click.stop="clearFile">✕</button>
      </div>
    </div>

    <!-- User ID + doc type badge row -->
    <div class="flex items-center gap-3">
      <div class="flex-1">
        <label class="block text-xs font-medium text-gray-500 mb-1">User ID (optional)</label>
        <input
          v-model="userId"
          type="text"
          placeholder="e.g. user_123"
          class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
        />
      </div>
      <div class="flex-shrink-0 mt-5">
        <span class="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-xs font-semibold text-amber-700">
          <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd"/>
          </svg>
          Loss Run
        </span>
      </div>
    </div>

    <!-- Submit -->
    <button
      class="w-full rounded-xl py-3 text-sm font-semibold text-white transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2"
      :class="canSubmit ? 'bg-indigo-600 hover:bg-indigo-700 active:scale-[0.98] cursor-pointer' : 'bg-gray-300 cursor-not-allowed'"
      :disabled="!canSubmit"
      @click="submit"
    >
      <span v-if="store.status === 'uploading'">Uploading…</span>
      <span v-else-if="store.status === 'streaming'">
        Extracting with {{ { llamaparse: 'LlamaParse', liteparse: 'LiteParse' }[store.activeProvider] || store.activeProvider?.toUpperCase() }}…
      </span>
      <span v-else>Extract Loss Run</span>
    </button>

    <!-- Progress feed -->
    <div v-if="store.progress.length" class="rounded-xl bg-gray-900 p-4 space-y-1 text-xs font-mono max-h-40 overflow-y-auto">
      <p v-for="(item, i) in store.progress" :key="i" class="text-green-400">▸ {{ item.message }}</p>
      <p v-if="store.status === 'streaming'" class="text-yellow-400 animate-pulse">● Processing…</p>
    </div>

    <!-- Error -->
    <div v-if="store.error" class="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
      {{ store.error }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useExtractionStore } from '../stores/extraction.js'

const store    = useExtractionStore()
const fileInput = ref(null)
const selectedFile = ref(null)
const userId   = ref('')
const isDragging = ref(false)

onMounted(() => store.fetchProviders())

const fileSize = computed(() => {
  if (!selectedFile.value) return ''
  const b = selectedFile.value.size
  return b > 1_048_576 ? `${(b / 1_048_576).toFixed(1)} MB` : `${(b / 1024).toFixed(0)} KB`
})

const canSubmit = computed(() => !!selectedFile.value && !store.isLoading)

function onFileChange(e) {
  const f = e.target.files?.[0]
  if (f?.type === 'application/pdf') selectedFile.value = f
}
function onDrop(e) {
  isDragging.value = false
  const f = e.dataTransfer.files?.[0]
  if (f?.type === 'application/pdf') selectedFile.value = f
}
function clearFile() {
  selectedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
}
async function submit() {
  if (!canSubmit.value) return
  await store.uploadPdf(selectedFile.value, {
    userId: userId.value || null,
    docType: 'lossrun',
  })
}

function providerIcon(id) {
  return { llamaparse: '🦙', liteparse: '⚡', openai: '🤖', gemini: '✨', anthropic: '🧠' }[id] ?? '🔮'
}

function providerBtnClass(p) {
  const isActive = store.activeProvider === p.id
  const colorMap = {
    llamaparse: { active: 'border-violet-500 bg-violet-50 text-violet-700', inactive: 'border-gray-200 text-gray-500' },
    liteparse:  { active: 'border-teal-500 bg-teal-50 text-teal-700',       inactive: 'border-gray-200 text-gray-500' },
    openai:     { active: 'border-green-500 bg-green-50 text-green-700',    inactive: 'border-gray-200 text-gray-500' },
    gemini:     { active: 'border-blue-500 bg-blue-50 text-blue-700',       inactive: 'border-gray-200 text-gray-500' },
    anthropic:  { active: 'border-purple-500 bg-purple-50 text-purple-700', inactive: 'border-gray-200 text-gray-500' },
  }
  const colors = colorMap[p.id] || { active: 'border-indigo-500 bg-indigo-50 text-indigo-700', inactive: 'border-gray-200 text-gray-500' }
  return [
    isActive ? colors.active : colors.inactive,
    !p.available ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer hover:opacity-90',
  ]
}
</script>
