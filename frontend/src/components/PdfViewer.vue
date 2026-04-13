<template>
  <div class="pdf-viewer-root" @click="closePopup">

    <!-- ── Toolbar ─────────────────────────────────────────────────────── -->
    <div class="flex items-center gap-3 px-4 py-2 bg-gray-800 rounded-t-xl text-white text-sm flex-wrap">
      <button
        class="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed"
        :disabled="currentPage <= 1"
        @click.stop="currentPage--"
      >‹ Prev</button>

      <span class="text-xs text-gray-300 tabular-nums">
        Page {{ currentPage }} / {{ totalPages }}
      </span>

      <button
        class="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed"
        :disabled="currentPage >= totalPages"
        @click.stop="currentPage++"
      >Next ›</button>

      <div class="flex-1" />

      <label class="flex items-center gap-1.5 text-xs cursor-pointer select-none">
        <input type="checkbox" v-model="showBoundingBoxes" class="accent-indigo-400" @click.stop />
        Bounding boxes
      </label>
      <label class="flex items-center gap-1.5 text-xs cursor-pointer select-none">
        <input type="checkbox" v-model="showTextItems" class="accent-teal-400" @click.stop />
        Text items
      </label>

      <button class="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600" @click.stop="zoom = Math.max(0.5, zoom - 0.25)">−</button>
      <span class="text-xs tabular-nums w-10 text-center">{{ Math.round(zoom * 100) }}%</span>
      <button class="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600" @click.stop="zoom = Math.min(3, zoom + 0.25)">+</button>
    </div>

    <!-- ── Canvas + overlay ────────────────────────────────────────────── -->
    <div
      class="relative overflow-auto bg-gray-600"
      style="max-height: 60vh;"
      @click="closePopup"
    >
      <div v-if="isLoading" class="flex items-center justify-center h-64 text-gray-300 text-sm">
        Loading PDF…
      </div>
      <div v-else-if="loadError" class="flex items-center justify-center h-64 text-red-400 text-sm">
        {{ loadError }}
      </div>

      <!-- canvas wrapper — position: relative so popup anchors to it -->
      <div
        v-else
        ref="canvasWrapper"
        class="relative inline-block"
        :style="{ width: canvasW + 'px', height: canvasH + 'px' }"
      >
        <canvas ref="canvasEl" class="block" />

        <!-- SVG overlay — not pointer-events-none so rects are clickable -->
        <svg
          v-if="pageData"
          class="absolute inset-0"
          :width="canvasW"
          :height="canvasH"
          :viewBox="`0 0 ${canvasW} ${canvasH}`"
        >
          <!-- Bounding boxes layer -->
          <template v-if="showBoundingBoxes">
            <rect
              v-for="(bb, i) in scaledBoundingBoxes"
              :key="'bb-' + i"
              :x="bb.x" :y="bb.y" :width="bb.w" :height="bb.h"
              :fill="selectedIdx === i ? 'rgba(99,102,241,0.25)' : 'rgba(239,68,68,0.10)'"
              :stroke="selectedIdx === i ? 'rgb(99,102,241)' : 'rgb(239,68,68)'"
              stroke-width="1.5"
              class="cursor-pointer"
              @click.stop="selectItem(i, 'bb', $event)"
            />
          </template>

          <!-- Text items layer -->
          <template v-if="showTextItems">
            <rect
              v-for="(ti, i) in scaledTextItems"
              :key="'ti-' + i"
              :x="ti.x" :y="ti.y" :width="ti.w" :height="ti.h"
              :fill="selectedIdx === i ? 'rgba(99,102,241,0.20)' : 'rgba(20,184,166,0.08)'"
              :stroke="selectedIdx === i ? 'rgb(99,102,241)' : 'rgb(20,184,166)'"
              stroke-width="1"
              class="cursor-pointer"
              @click.stop="selectItem(i, 'ti', $event)"
            />
          </template>
        </svg>

        <!-- ── Edit Popup ───────────────────────────────────────────────── -->
        <Transition name="popup">
          <div
            v-if="popupVisible && selectedIdx !== null && pageItems[selectedIdx]"
            class="absolute z-50 bg-white rounded-xl shadow-2xl border border-gray-200 w-72"
            :style="popupStyle"
            @click.stop
          >
            <!-- popup header -->
            <div class="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-t-xl border-b border-gray-200">
              <span class="text-xs font-semibold text-gray-600">Edit Value</span>
              <button class="text-gray-400 hover:text-gray-700 text-sm leading-none" @click="closePopup">✕</button>
            </div>

            <!-- editable text -->
            <div class="px-3 pt-3 pb-2">
              <label class="block text-xs text-gray-500 mb-1">Text content</label>
              <textarea
                ref="popupInput"
                v-model="editText"
                rows="2"
                class="w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
              />
            </div>

            <!-- metadata grid -->
            <div class="px-3 pb-2 grid grid-cols-3 gap-x-2 gap-y-1 text-xs text-gray-500">
              <span class="text-gray-400">x</span>
              <span class="text-gray-400">y</span>
              <span class="text-gray-400">conf</span>
              <span class="font-mono">{{ fmtNum(pageItems[selectedIdx].x) }}</span>
              <span class="font-mono">{{ fmtNum(pageItems[selectedIdx].y) }}</span>
              <span class="font-mono">{{ fmtNum(pageItems[selectedIdx].confidence) }}</span>
              <span class="text-gray-400 col-span-2">font</span>
              <span class="text-gray-400">size</span>
              <span class="font-mono col-span-2 truncate">{{ pageItems[selectedIdx].fontName ?? '—' }}</span>
              <span class="font-mono">{{ fmtNum(pageItems[selectedIdx].fontSize) }}</span>
            </div>

            <!-- action row -->
            <div class="px-3 pb-3 flex gap-2">
              <button
                class="flex-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold py-1.5 transition-colors"
                @click="saveEdit"
              >Save</button>
              <button
                class="flex-1 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-600 text-xs font-semibold py-1.5 transition-colors"
                @click="closePopup"
              >Cancel</button>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- ── Legend ──────────────────────────────────────────────────────── -->
    <div
      v-if="pageData && (showBoundingBoxes || showTextItems)"
      class="flex gap-4 mt-2 px-1 text-xs text-gray-500"
    >
      <span v-if="showBoundingBoxes" class="flex items-center gap-1">
        <span class="inline-block w-3 h-3 rounded-sm bg-red-400 opacity-50"></span>
        Bounding boxes ({{ pageData.boundingBoxes?.length ?? 0 }})
      </span>
      <span v-if="showTextItems" class="flex items-center gap-1">
        <span class="inline-block w-3 h-3 rounded-sm bg-teal-400 opacity-50"></span>
        Text items ({{ pageData.textItems?.length ?? 0 }})
      </span>
      <span v-if="selectedIdx !== null" class="flex items-center gap-1 ml-auto text-indigo-600">
        <span class="inline-block w-3 h-3 rounded-sm bg-indigo-400 opacity-60"></span>
        Selected: #{{ selectedIdx + 1 }}
      </span>
    </div>

    <!-- ── Text Items Table ────────────────────────────────────────────── -->
    <div v-if="pageItems.length" class="mt-4 rounded-xl border border-gray-200 overflow-hidden bg-white">
      <div class="flex items-center justify-between px-4 py-2.5 bg-gray-50 border-b border-gray-200">
        <span class="text-xs font-semibold text-gray-600 uppercase tracking-wide">
          Extracted Text Items — Page {{ currentPage }}
        </span>
        <span class="text-xs text-gray-400">{{ pageItems.length }} item{{ pageItems.length !== 1 ? 's' : '' }} · click row or box to select</span>
      </div>

      <div class="overflow-auto" style="max-height: 280px;">
        <table class="w-full text-xs border-collapse">
          <thead class="sticky top-0 z-10">
            <tr class="bg-gray-50 text-gray-500 uppercase text-[0.65rem] tracking-wide">
              <th class="px-3 py-2 text-left font-semibold w-6">#</th>
              <th class="px-3 py-2 text-left font-semibold">Text</th>
              <th class="px-3 py-2 text-right font-semibold">x</th>
              <th class="px-3 py-2 text-right font-semibold">y</th>
              <th class="px-3 py-2 text-right font-semibold">w</th>
              <th class="px-3 py-2 text-right font-semibold">h</th>
              <th class="px-3 py-2 text-right font-semibold">conf</th>
              <th class="px-3 py-2 text-right font-semibold">font px</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(item, i) in pageItems"
              :key="i"
              :ref="el => { if (el) rowRefs[i] = el }"
              class="border-b border-gray-100 cursor-pointer transition-colors"
              :class="selectedIdx === i
                ? 'bg-indigo-50 ring-1 ring-inset ring-indigo-300'
                : 'hover:bg-gray-50'"
              @click.stop="selectItem(i, 'row')"
            >
              <td class="px-3 py-1.5 text-gray-400 tabular-nums">{{ i + 1 }}</td>
              <td class="px-3 py-1.5 text-gray-800 font-medium max-w-xs">
                <!-- show edited value if exists, otherwise original -->
                <span :class="editedValues[editKey(i)] ? 'text-indigo-700' : ''">
                  {{ editedValues[editKey(i)] ?? item.text }}
                </span>
                <span v-if="editedValues[editKey(i)]" class="ml-1 text-[0.6rem] text-indigo-400">(edited)</span>
              </td>
              <td class="px-3 py-1.5 text-gray-500 tabular-nums text-right">{{ fmtNum(item.x) }}</td>
              <td class="px-3 py-1.5 text-gray-500 tabular-nums text-right">{{ fmtNum(item.y) }}</td>
              <td class="px-3 py-1.5 text-gray-500 tabular-nums text-right">{{ fmtNum(item.width) }}</td>
              <td class="px-3 py-1.5 text-gray-500 tabular-nums text-right">{{ fmtNum(item.height) }}</td>
              <td class="px-3 py-1.5 tabular-nums text-right"
                  :class="item.confidence >= 0.9 ? 'text-green-600' : item.confidence >= 0.7 ? 'text-yellow-600' : 'text-red-500'">
                {{ item.confidence != null ? (item.confidence * 100).toFixed(0) + '%' : '—' }}
              </td>
              <td class="px-3 py-1.5 text-gray-500 tabular-nums text-right">{{ fmtNum(item.fontSize) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps({
  pdfUrl: { type: String, required: true },
  pages:  { type: Array, default: () => [] },
})

const emit = defineEmits(['update:item'])

// ── PDF state ──────────────────────────────────────────────────────────────
const canvasEl      = ref(null)
const canvasWrapper = ref(null)
const currentPage   = ref(1)
const totalPages    = ref(0)
const zoom          = ref(1.25)
const isLoading     = ref(true)
const loadError     = ref(null)
const canvasW       = ref(0)
const canvasH       = ref(0)

// ── Overlay toggles ────────────────────────────────────────────────────────
const showBoundingBoxes = ref(true)
const showTextItems     = ref(false)

// ── Selection + popup state ────────────────────────────────────────────────
const selectedIdx  = ref(null)
const popupVisible = ref(false)
const popupPos     = ref({ x: 0, y: 0 })
const editText     = ref('')
const popupInput   = ref(null)

// Persists edited values across pages: key = "page:idx"
const editedValues = ref({})

// Row element refs for scroll-into-view
const rowRefs = ref({})

function editKey(idx) {
  return `${currentPage.value}:${idx}`
}

// ── PDF.js ─────────────────────────────────────────────────────────────────
let pdfDoc   = null
let pdfjsLib = null

// ── LiteParse page data ────────────────────────────────────────────────────
const pageData = computed(() =>
  props.pages?.find(p => p.pageNum === currentPage.value) ?? null
)

const pageItems = computed(() => pageData.value?.textItems ?? [])

// ── Coordinate mapping ─────────────────────────────────────────────────────
// LiteParse uses top-left origin (y=0 at top), same as canvas. Scale only.

const scaleX = computed(() =>
  pageData.value?.width ? canvasW.value / pageData.value.width : 1
)
const scaleY = computed(() =>
  pageData.value?.height ? canvasH.value / pageData.value.height : 1
)

function toCanvasRect(x, y, w, h) {
  return {
    x: x * scaleX.value,
    y: y * scaleY.value,
    w: w * scaleX.value,
    h: h * scaleY.value,
  }
}

const scaledBoundingBoxes = computed(() =>
  (pageData.value?.boundingBoxes ?? []).map(bb =>
    toCanvasRect(bb.x1, bb.y1, bb.x2 - bb.x1, bb.y2 - bb.y1)
  )
)

const scaledTextItems = computed(() =>
  pageItems.value
    .filter(ti => ti.width > 0 && ti.height > 0)
    .map(ti => toCanvasRect(ti.x, ti.y, ti.width, ti.height))
)

// ── Popup position (clamped so it stays inside canvas wrapper) ─────────────
const POPUP_W = 288  // matches w-72
const POPUP_H = 230  // approx popup height

const popupStyle = computed(() => {
  const x = Math.min(popupPos.value.x, canvasW.value - POPUP_W - 4)
  const y = Math.min(popupPos.value.y, canvasH.value - POPUP_H - 4)
  return {
    left: Math.max(4, x) + 'px',
    top:  Math.max(4, y) + 'px',
  }
})

// ── Selection ──────────────────────────────────────────────────────────────

function selectItem(i, source, svgEvent) {
  selectedIdx.value = i
  editText.value = editedValues.value[editKey(i)] ?? pageItems.value[i]?.text ?? ''

  // Position popup relative to canvas wrapper
  if (source === 'bb' || source === 'ti') {
    const rects = source === 'bb' ? scaledBoundingBoxes.value : scaledTextItems.value
    const r = rects[i]
    if (r) {
      popupPos.value = {
        x: r.x + r.w + 8,
        y: r.y,
      }
    }
  } else if (source === 'row') {
    // Center popup in canvas
    popupPos.value = { x: canvasW.value / 2 - POPUP_W / 2, y: 20 }
  }

  popupVisible.value = true

  // Scroll table row into view
  nextTick(() => {
    rowRefs.value[i]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    if (source === 'row') popupInput.value?.focus()
  })
}

function closePopup() {
  popupVisible.value = false
  selectedIdx.value = null
}

function saveEdit() {
  if (selectedIdx.value === null) return
  const key = editKey(selectedIdx.value)
  const original = pageItems.value[selectedIdx.value]?.text ?? ''
  if (editText.value !== original) {
    editedValues.value[key] = editText.value
  } else {
    delete editedValues.value[key]
  }
  emit('update:item', {
    pageNum: currentPage.value,
    index:   selectedIdx.value,
    text:    editText.value,
  })
  popupVisible.value = false
}

// ── Helpers ────────────────────────────────────────────────────────────────
function fmtNum(v) {
  if (v == null) return '—'
  return typeof v === 'number' ? v.toFixed(1) : v
}

// ── PDF.js rendering ───────────────────────────────────────────────────────
async function loadPdfJs() {
  if (pdfjsLib) return
  const mod = await import('pdfjs-dist')
  pdfjsLib = mod
  pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.mjs',
    import.meta.url,
  ).href
}

async function loadDocument() {
  isLoading.value = true
  loadError.value = null
  try {
    await loadPdfJs()
    const task = pdfjsLib.getDocument(props.pdfUrl)
    pdfDoc = await task.promise
    totalPages.value  = pdfDoc.numPages
    currentPage.value = 1
    await renderPage()
  } catch (err) {
    loadError.value = `Failed to load PDF: ${err.message}`
  } finally {
    isLoading.value = false
  }
}

async function renderPage() {
  if (!pdfDoc) return
  closePopup()
  const page     = await pdfDoc.getPage(currentPage.value)
  const viewport = page.getViewport({ scale: zoom.value })

  canvasW.value = Math.round(viewport.width)
  canvasH.value = Math.round(viewport.height)

  await nextTick()

  const canvas = canvasEl.value
  if (!canvas) return
  const ctx    = canvas.getContext('2d')
  canvas.width  = canvasW.value
  canvas.height = canvasH.value

  await page.render({ canvasContext: ctx, viewport }).promise
}

watch(() => props.pdfUrl, loadDocument)
watch(currentPage, renderPage)
watch(zoom,        renderPage)

onMounted(loadDocument)
onBeforeUnmount(() => {
  if (pdfDoc) { pdfDoc.destroy(); pdfDoc = null }
})
</script>

<style scoped>
.pdf-viewer-root {
  font-family: inherit;
}

/* Popup slide-in transition */
.popup-enter-active,
.popup-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.popup-enter-from,
.popup-leave-to {
  opacity: 0;
  transform: scale(0.95) translateY(-4px);
}
</style>
