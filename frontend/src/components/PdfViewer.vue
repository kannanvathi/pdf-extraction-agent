<template>
  <div class="pdf-viewer-root" @click="closePopup">

    <!-- ── Toolbar ────────────────────────────────────────────────────────── -->
    <div class="flex items-center gap-3 px-4 py-2 bg-gray-800 rounded-t-xl text-white text-sm flex-wrap">
      <!-- page nav -->
      <button class="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed"
        :disabled="currentPage <= 1" @click.stop="currentPage--">‹ Prev</button>
      <span class="text-xs text-gray-300 tabular-nums">Page {{ currentPage }} / {{ totalPages }}</span>
      <button class="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed"
        :disabled="currentPage >= totalPages" @click.stop="currentPage++">Next ›</button>

      <div class="flex-1" />

      <!-- threshold -->
      <label class="flex items-center gap-1.5 text-xs select-none">
        <span class="text-gray-400">Threshold</span>
        <input type="number" v-model.number="spatialThreshold" min="5" max="100"
          class="w-12 rounded bg-gray-700 text-white text-xs px-1.5 py-0.5 text-center focus:outline-none focus:ring-1 focus:ring-indigo-400"
          @click.stop />
        <span class="text-gray-400">px</span>
      </label>

      <!-- overlay toggles -->
      <label class="flex items-center gap-1.5 text-xs cursor-pointer select-none">
        <input type="checkbox" v-model="showGroups" class="accent-orange-400" @click.stop />
        Groups
      </label>
      <label class="flex items-center gap-1.5 text-xs cursor-pointer select-none">
        <input type="checkbox" v-model="showBoundingBoxes" class="accent-red-400" @click.stop />
        Boxes
      </label>
      <label class="flex items-center gap-1.5 text-xs cursor-pointer select-none">
        <input type="checkbox" v-model="showTextItems" class="accent-teal-400" @click.stop />
        Items
      </label>

      <!-- zoom -->
      <button class="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600" @click.stop="zoom = Math.max(0.5, zoom - 0.25)">−</button>
      <span class="text-xs tabular-nums w-10 text-center">{{ Math.round(zoom * 100) }}%</span>
      <button class="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600" @click.stop="zoom = Math.min(3, zoom + 0.25)">+</button>
    </div>

    <!-- ── Canvas + overlay ───────────────────────────────────────────────── -->
    <div class="relative overflow-auto bg-gray-600" style="max-height: 60vh;" @click="closePopup">
      <div v-if="isLoading" class="flex items-center justify-center h-64 text-gray-300 text-sm">Loading PDF…</div>
      <div v-else-if="loadError" class="flex items-center justify-center h-64 text-red-400 text-sm">{{ loadError }}</div>

      <div v-else ref="canvasWrapper" class="relative inline-block"
        :style="{ width: canvasW + 'px', height: canvasH + 'px' }">
        <canvas ref="canvasEl" class="block" />

        <svg v-if="pageData" class="absolute inset-0"
          :width="canvasW" :height="canvasH" :viewBox="`0 0 ${canvasW} ${canvasH}`">

          <!-- ① Individual bounding boxes (red) -->
          <template v-if="showBoundingBoxes">
            <rect v-for="(bb, i) in scaledBoundingBoxes" :key="'bb-'+i"
              :x="bb.x" :y="bb.y" :width="bb.w" :height="bb.h"
              :fill="rawSelected === i ? 'rgba(99,102,241,0.25)' : 'rgba(239,68,68,0.10)'"
              :stroke="rawSelected === i ? 'rgb(99,102,241)' : 'rgb(239,68,68)'"
              stroke-width="1.5" class="cursor-pointer"
              @click.stop="selectRaw(i)" />
          </template>

          <!-- ② Individual text items (teal) -->
          <template v-if="showTextItems">
            <rect v-for="(ti, i) in scaledTextItems" :key="'ti-'+i"
              :x="ti.x" :y="ti.y" :width="ti.w" :height="ti.h"
              :fill="rawSelected === i ? 'rgba(99,102,241,0.20)' : 'rgba(20,184,166,0.08)'"
              :stroke="rawSelected === i ? 'rgb(99,102,241)' : 'rgb(20,184,166)'"
              stroke-width="1" class="cursor-pointer"
              @click.stop="selectRaw(i)" />
          </template>

          <!-- ③ Merged groups (orange) — 30 px threshold clusters -->
          <template v-if="showGroups">
            <rect v-for="(g, i) in scaledGroupBoxes" :key="'g-'+i"
              :x="g.x" :y="g.y" :width="g.w" :height="g.h"
              :fill="groupSelected === i ? 'rgba(99,102,241,0.28)' : 'rgba(251,146,60,0.15)'"
              :stroke="groupSelected === i ? 'rgb(99,102,241)' : 'rgb(251,146,60)'"
              stroke-width="2" rx="2" class="cursor-pointer"
              @click.stop="selectGroup(i)" />
          </template>
        </svg>

        <!-- ── Edit popup ──────────────────────────────────────────────────── -->
        <Transition name="popup">
          <div v-if="popupVisible && popupData"
            class="absolute z-50 bg-white rounded-xl shadow-2xl border border-gray-200 w-72"
            :style="popupStyle" @click.stop>

            <div class="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-t-xl border-b border-gray-200">
              <span class="text-xs font-semibold text-gray-600">
                {{ tableMode === 'spatial' ? 'Edit Merged Cell' : 'Edit Value' }}
              </span>
              <button class="text-gray-400 hover:text-gray-700 text-sm" @click="closePopup">✕</button>
            </div>

            <div class="px-3 pt-3 pb-2">
              <label class="block text-xs text-gray-500 mb-1">Text content</label>
              <textarea ref="popupInput" v-model="editText" rows="3"
                class="w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none" />
            </div>

            <div class="px-3 pb-2 grid grid-cols-3 gap-x-2 gap-y-1 text-xs text-gray-500">
              <span class="text-gray-400">x</span><span class="text-gray-400">y</span><span class="text-gray-400">width</span>
              <span class="font-mono">{{ fmtNum(popupData.x) }}</span>
              <span class="font-mono">{{ fmtNum(popupData.y) }}</span>
              <span class="font-mono">{{ fmtNum(popupData.width) }}</span>
            </div>

            <div class="px-3 pb-3 flex gap-2">
              <button class="flex-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold py-1.5 transition-colors"
                @click="saveEdit">Save</button>
              <button class="flex-1 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-600 text-xs font-semibold py-1.5 transition-colors"
                @click="closePopup">Cancel</button>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- ── Legend ─────────────────────────────────────────────────────────── -->
    <div v-if="pageData" class="flex flex-wrap gap-4 mt-2 px-1 text-xs text-gray-500">
      <span v-if="showGroups" class="flex items-center gap-1">
        <span class="inline-block w-3 h-3 rounded-sm bg-orange-400 opacity-60"></span>
        Merged groups ({{ spatialTable.flatCells.length }})
      </span>
      <span v-if="showBoundingBoxes" class="flex items-center gap-1">
        <span class="inline-block w-3 h-3 rounded-sm bg-red-400 opacity-50"></span>
        Bounding boxes ({{ pageData.boundingBoxes?.length ?? 0 }})
      </span>
      <span v-if="showTextItems" class="flex items-center gap-1">
        <span class="inline-block w-3 h-3 rounded-sm bg-teal-400 opacity-50"></span>
        Text items ({{ pageItems.length }})
      </span>
    </div>

    <!-- ── Table section ──────────────────────────────────────────────────── -->
    <div v-if="pageItems.length" class="mt-4 rounded-xl border border-gray-200 overflow-hidden bg-white">

      <!-- table header + mode toggle -->
      <div class="flex items-center justify-between px-4 py-2.5 bg-gray-50 border-b border-gray-200">
        <div class="flex items-center gap-3">
          <span class="text-xs font-semibold text-gray-600 uppercase tracking-wide">
            Page {{ currentPage }} — Extracted Text
          </span>
          <span v-if="tableMode === 'spatial'" class="text-xs text-gray-400">
            {{ spatialTable.rows.length }} row{{ spatialTable.rows.length !== 1 ? 's' : '' }} ·
            {{ spatialTable.cols.length }} col{{ spatialTable.cols.length !== 1 ? 's' : '' }}
          </span>
          <span v-else class="text-xs text-gray-400">
            {{ pageItems.length }} raw item{{ pageItems.length !== 1 ? 's' : '' }}
          </span>
        </div>

        <!-- mode toggle -->
        <div class="flex rounded-lg border border-gray-200 overflow-hidden text-xs">
          <button
            class="px-3 py-1 font-medium transition-colors"
            :class="tableMode === 'spatial' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="tableMode = 'spatial'">Spatial Table</button>
          <button
            class="px-3 py-1 font-medium transition-colors border-l border-gray-200"
            :class="tableMode === 'raw' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="tableMode = 'raw'">Raw Items</button>
        </div>
      </div>

      <!-- ── Spatial Table ─────────────────────────────────────────────── -->
      <div v-if="tableMode === 'spatial'" class="overflow-auto" style="max-height: 320px;">
        <div v-if="!spatialTable.rows.length" class="text-center py-8 text-gray-400 text-sm">
          No text items to group on this page.
        </div>
        <table v-else class="w-full text-xs border-collapse">
          <thead class="sticky top-0 z-10">
            <tr class="bg-gray-50 text-gray-500 text-[0.65rem] uppercase tracking-wide">
              <th class="px-3 py-2 text-left font-semibold w-6 border-b border-gray-200">#</th>
              <th v-for="col in spatialTable.cols" :key="col.key"
                class="px-3 py-2 text-left font-semibold border-b border-gray-200 whitespace-nowrap">
                {{ col.label }}
                <span class="ml-1 text-[0.55rem] text-gray-400 font-normal normal-case">x≈{{ Math.round(col.x) }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in spatialTable.rows" :key="ri"
              :ref="el => { if (el) groupRowRefs[ri] = el }"
              class="border-b border-gray-100 cursor-pointer transition-colors"
              :class="isGroupRowSelected(ri) ? 'bg-orange-50 ring-1 ring-inset ring-orange-300' : 'hover:bg-gray-50'"
              @click.stop="selectGroupByRow(ri)">
              <td class="px-3 py-1.5 text-gray-400 tabular-nums">{{ ri + 1 }}</td>
              <td v-for="(cell, ci) in row" :key="ci"
                class="px-3 py-1.5 text-gray-800 border-l border-gray-100 max-w-xs"
                :class="groupSelected !== null && groupSelected === flatGroupIndex(ri, ci) ? 'bg-indigo-50 font-semibold text-indigo-700' : ''">
                <span :class="editedGroupValues[groupEditKey(ri, ci)] ? 'text-indigo-700' : ''">
                  {{ editedGroupValues[groupEditKey(ri, ci)] ?? cell }}
                </span>
                <span v-if="editedGroupValues[groupEditKey(ri, ci)]"
                  class="ml-1 text-[0.6rem] text-indigo-400">(edited)</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ── Raw Items Table ────────────────────────────────────────────── -->
      <div v-else class="overflow-auto" style="max-height: 320px;">
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
            <tr v-for="(item, i) in pageItems" :key="i"
              :ref="el => { if (el) rowRefs[i] = el }"
              class="border-b border-gray-100 cursor-pointer transition-colors"
              :class="rawSelected === i ? 'bg-indigo-50 ring-1 ring-inset ring-indigo-300' : 'hover:bg-gray-50'"
              @click.stop="selectRawByRow(i)">
              <td class="px-3 py-1.5 text-gray-400 tabular-nums">{{ i + 1 }}</td>
              <td class="px-3 py-1.5 text-gray-800 font-medium max-w-xs">
                <span :class="editedValues[rawEditKey(i)] ? 'text-indigo-700' : ''">
                  {{ editedValues[rawEditKey(i)] ?? item.text }}
                </span>
                <span v-if="editedValues[rawEditKey(i)]" class="ml-1 text-[0.6rem] text-indigo-400">(edited)</span>
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

// ── Overlay + table mode ───────────────────────────────────────────────────
const showGroups        = ref(true)
const showBoundingBoxes = ref(false)
const showTextItems     = ref(false)
const tableMode         = ref('spatial')    // 'spatial' | 'raw'
const spatialThreshold  = ref(30)

// ── Selection state ────────────────────────────────────────────────────────
const rawSelected   = ref(null)   // index into pageItems
const groupSelected = ref(null)   // flat index into spatialTable.flatCells

// ── Popup state ────────────────────────────────────────────────────────────
const popupVisible = ref(false)
const popupPos     = ref({ x: 0, y: 0 })
const popupData    = ref(null)   // {text, x, y, width, mode, key}
const editText     = ref('')
const popupInput   = ref(null)

// ── Edit stores ────────────────────────────────────────────────────────────
const editedValues      = ref({})   // raw mode: "page:idx" → text
const editedGroupValues = ref({})   // spatial mode: "page:ri:ci" → text

// ── Row refs for scroll-into-view ──────────────────────────────────────────
const rowRefs      = ref({})
const groupRowRefs = ref({})

const POPUP_W = 288
const POPUP_H = 200

// ── LiteParse page data ────────────────────────────────────────────────────
const pageData = computed(() =>
  props.pages?.find(p => p.pageNum === currentPage.value) ?? null
)
const pageItems = computed(() => pageData.value?.textItems ?? [])

// ── Coordinate helpers ─────────────────────────────────────────────────────
const scaleX = computed(() =>
  pageData.value?.width  ? canvasW.value / pageData.value.width  : 1
)
const scaleY = computed(() =>
  pageData.value?.height ? canvasH.value / pageData.value.height : 1
)
function toCanvasRect(x, y, w, h) {
  return { x: x * scaleX.value, y: y * scaleY.value,
           w: w * scaleX.value, h: h * scaleY.value }
}

// ── Scaled overlays ────────────────────────────────────────────────────────
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

// ── Spatial grouping algorithm ─────────────────────────────────────────────
// Returns { cols, rows (grid of strings), flatCells (merged boxes), mergedRows }
const spatialTable = computed(() => {
  return reconstructSpatialTable(pageItems.value, spatialThreshold.value)
})

function reconstructSpatialTable(items, threshold) {
  const empty = { cols: [], rows: [], flatCells: [], mergedRows: [] }
  if (!items?.length) return empty

  const valid = items.filter(t => t.text?.trim())
  if (!valid.length) return empty

  // Sort by y (rows), break ties by x (left-to-right)
  const sorted = [...valid].sort((a, b) =>
    Math.abs(a.y - b.y) <= threshold ? a.x - b.x : a.y - b.y
  )

  // Step 1 — row grouping: items whose y is within threshold belong to same row
  const rowBuckets = []
  let bucket    = [sorted[0]]
  let bucketY   = sorted[0].y

  for (let i = 1; i < sorted.length; i++) {
    const item = sorted[i]
    if (Math.abs(item.y - bucketY) <= threshold) {
      bucket.push(item)
    } else {
      rowBuckets.push([...bucket].sort((a, b) => a.x - b.x))
      bucket  = [item]
      bucketY = item.y
    }
  }
  rowBuckets.push([...bucket].sort((a, b) => a.x - b.x))

  // Step 2 — horizontal merging: items in the same row with gap ≤ threshold
  const mergedRows = rowBuckets.map(row => {
    const cells = []
    for (const item of row) {
      const last = cells[cells.length - 1]
      if (last) {
        const gap = item.x - (last.x + last.width)
        if (gap <= threshold) {
          last.text  += (gap > 2 ? ' ' : '') + item.text
          last.width  = (item.x + item.width) - last.x
          last.height = Math.max(last.height, item.height)
          continue
        }
      }
      cells.push({
        text: item.text, x: item.x, y: item.y,
        width: item.width, height: item.height,
      })
    }
    return cells
  })

  // Step 3 — column detection: cluster x-positions across all rows
  const allX = mergedRows.flatMap(r => r.map(c => c.x))
  const colCenters = []
  for (const x of [...allX].sort((a, b) => a - b)) {
    if (!colCenters.some(c => Math.abs(c - x) <= threshold)) colCenters.push(x)
  }
  colCenters.sort((a, b) => a - b)

  if (!colCenters.length) return empty

  // Step 4 — build grid: assign each merged cell to the nearest column
  const grid = mergedRows.map(row => {
    const cells = Array(colCenters.length).fill('')
    for (const cell of row) {
      let bestCol = 0, bestDist = Infinity
      for (let i = 0; i < colCenters.length; i++) {
        const d = Math.abs(cell.x - colCenters[i])
        if (d < bestDist) { bestDist = d; bestCol = i }
      }
      cells[bestCol] = cells[bestCol]
        ? cells[bestCol] + ' ' + cell.text
        : cell.text
    }
    return cells
  })

  const cols      = colCenters.map((x, i) => ({ key: `c${i}`, label: `Col ${i + 1}`, x }))
  const flatCells = mergedRows.flatMap((row, ri) =>
    row.map((cell, ci) => ({ ...cell, rowIdx: ri, cellIdx: ci }))
  )

  return { cols, rows: grid, flatCells, mergedRows }
}

// Scaled merged group boxes for the SVG overlay
const scaledGroupBoxes = computed(() =>
  spatialTable.value.flatCells.map(c =>
    toCanvasRect(c.x, c.y, c.width, c.height)
  )
)

// ── Popup position ─────────────────────────────────────────────────────────
const popupStyle = computed(() => {
  const x = Math.min(popupPos.value.x, canvasW.value - POPUP_W - 4)
  const y = Math.min(popupPos.value.y, canvasH.value - POPUP_H - 4)
  return { left: Math.max(4, x) + 'px', top: Math.max(4, y) + 'px' }
})

// ── Selection helpers ──────────────────────────────────────────────────────
function flatGroupIndex(ri, ci) {
  // linear index of a (rowIdx, cellIdx) pair in flatCells
  return spatialTable.value.flatCells.findIndex(
    c => c.rowIdx === ri && c.cellIdx === ci
  )
}

function isGroupRowSelected(ri) {
  if (groupSelected.value === null) return false
  const cell = spatialTable.value.flatCells[groupSelected.value]
  return cell?.rowIdx === ri
}

// ── Selection: canvas group click ─────────────────────────────────────────
function selectGroup(flatIdx) {
  groupSelected.value = flatIdx
  rawSelected.value   = null
  tableMode.value     = 'spatial'

  const cell = spatialTable.value.flatCells[flatIdx]
  if (!cell) return

  const box = scaledGroupBoxes.value[flatIdx]
  popupPos.value = { x: box.x + box.w + 8, y: box.y }

  popupData.value = { text: cell.text, x: cell.x, y: cell.y, width: cell.width,
                      mode: 'group', ri: cell.rowIdx, ci: cell.cellIdx }
  editText.value  = editedGroupValues.value[groupEditKey(cell.rowIdx, cell.cellIdx)] ?? cell.text
  popupVisible.value = true

  nextTick(() => {
    groupRowRefs.value[cell.rowIdx]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
}

// ── Selection: spatial table row click ────────────────────────────────────
function selectGroupByRow(ri) {
  const flatIdx = spatialTable.value.flatCells.findIndex(c => c.rowIdx === ri)
  if (flatIdx < 0) return
  groupSelected.value = flatIdx
  rawSelected.value   = null

  const cell = spatialTable.value.flatCells[flatIdx]
  popupPos.value  = { x: canvasW.value / 2 - POPUP_W / 2, y: 20 }
  popupData.value = { text: cell.text, x: cell.x, y: cell.y, width: cell.width,
                      mode: 'group', ri: cell.rowIdx, ci: cell.cellIdx }
  editText.value  = editedGroupValues.value[groupEditKey(ri, 0)] ?? cell.text
  popupVisible.value = true

  nextTick(() => popupInput.value?.focus())
}

// ── Selection: canvas raw click ────────────────────────────────────────────
function selectRaw(i) {
  rawSelected.value   = i
  groupSelected.value = null
  tableMode.value     = 'raw'

  const item = pageItems.value[i]
  const box  = scaledBoundingBoxes.value[i] ?? scaledTextItems.value[i]
  if (box) popupPos.value = { x: box.x + box.w + 8, y: box.y }

  popupData.value = { text: item.text, x: item.x, y: item.y, width: item.width,
                      mode: 'raw', idx: i }
  editText.value  = editedValues.value[rawEditKey(i)] ?? item.text
  popupVisible.value = true

  nextTick(() => {
    rowRefs.value[i]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
}

// ── Selection: raw table row click ────────────────────────────────────────
function selectRawByRow(i) {
  rawSelected.value   = i
  groupSelected.value = null

  const item = pageItems.value[i]
  popupPos.value  = { x: canvasW.value / 2 - POPUP_W / 2, y: 20 }
  popupData.value = { text: item.text, x: item.x, y: item.y, width: item.width,
                      mode: 'raw', idx: i }
  editText.value  = editedValues.value[rawEditKey(i)] ?? item.text
  popupVisible.value = true

  nextTick(() => popupInput.value?.focus())
}

function closePopup() {
  popupVisible.value  = false
  rawSelected.value   = null
  groupSelected.value = null
}

// ── Save edit ──────────────────────────────────────────────────────────────
function saveEdit() {
  if (!popupData.value) return
  const { mode, idx, ri, ci } = popupData.value

  if (mode === 'raw') {
    const key      = rawEditKey(idx)
    const original = pageItems.value[idx]?.text ?? ''
    if (editText.value !== original) editedValues.value[key] = editText.value
    else delete editedValues.value[key]
    emit('update:item', { pageNum: currentPage.value, index: idx, text: editText.value })
  } else {
    const key      = groupEditKey(ri, ci)
    const original = spatialTable.value.rows[ri]?.[ci] ?? ''
    if (editText.value !== original) editedGroupValues.value[key] = editText.value
    else delete editedGroupValues.value[key]
  }
  popupVisible.value = false
}

// ── Key helpers ────────────────────────────────────────────────────────────
function rawEditKey(idx)    { return `${currentPage.value}:${idx}` }
function groupEditKey(ri, ci) { return `${currentPage.value}:${ri}:${ci}` }

// ── Misc ───────────────────────────────────────────────────────────────────
function fmtNum(v) {
  if (v == null) return '—'
  return typeof v === 'number' ? v.toFixed(1) : v
}

// ── PDF.js ─────────────────────────────────────────────────────────────────
let pdfDoc = null, pdfjsLib = null

async function loadPdfJs() {
  if (pdfjsLib) return
  const mod = await import('pdfjs-dist')
  pdfjsLib  = mod
  pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.mjs', import.meta.url,
  ).href
}

async function loadDocument() {
  isLoading.value = true
  loadError.value = null
  try {
    await loadPdfJs()
    pdfDoc = await pdfjsLib.getDocument(props.pdfUrl).promise
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
  canvasW.value  = Math.round(viewport.width)
  canvasH.value  = Math.round(viewport.height)
  await nextTick()
  const canvas   = canvasEl.value
  if (!canvas) return
  canvas.width   = canvasW.value
  canvas.height  = canvasH.value
  await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise
}

watch(() => props.pdfUrl, loadDocument)
watch(currentPage, renderPage)
watch(zoom, renderPage)
onMounted(loadDocument)
onBeforeUnmount(() => { if (pdfDoc) { pdfDoc.destroy(); pdfDoc = null } })
</script>

<style scoped>
.pdf-viewer-root { font-family: inherit; }
.popup-enter-active, .popup-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.popup-enter-from, .popup-leave-to { opacity: 0; transform: scale(0.95) translateY(-4px); }
</style>
