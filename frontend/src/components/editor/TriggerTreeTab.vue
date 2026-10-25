<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  Code2,
  DoorOpen,
  FolderTree,
  Globe,
  Layers,
  Link2,
  MapPin,
  MessageSquareQuote,
  Package,
  PencilLine,
  ShieldCheck,
  Type,
  User,
  Users,
} from 'lucide-vue-next'
import {
  buildTriggerTree,
  countLeaves,
  filterTriggerTree,
  type TriggerLeaf,
  type TriggerTreeNode,
} from '@/services/triggerTree'

const props = defineProps<{
  adventure: any
  protagonist?: any
  scenes?: any[]
  exits?: any[]
  npcs?: any[]
  objects?: any[]
}>()

const emit = defineEmits<{
  (e: 'edit', node: TriggerTreeNode): void
}>()

type Row =
  | { type: 'node'; key: string; depth: number; node: TriggerTreeNode; count: number }
  | { type: 'leaf'; key: string; depth: number; leaf: TriggerLeaf; owner: TriggerTreeNode }

const query = ref('')
const onlyConfigured = ref(true)
const collapsed = ref<Set<string>>(new Set())
const selected = ref<{ leaf: TriggerLeaf; owner: TriggerTreeNode } | null>(null)

const fullTree = computed(() => buildTriggerTree({
  adventure: props.adventure,
  protagonist: props.protagonist,
  scenes: props.scenes,
  exits: props.exits,
  npcs: props.npcs,
  objects: props.objects,
}))

const tree = computed(() => filterTriggerTree(fullTree.value, query.value, onlyConfigured.value))
const totalTriggers = computed(() => fullTree.value.reduce((sum, node) => sum + countLeaves(node), 0))

// A search always shows its hits, regardless of collapsed nodes.
const isOpen = (key: string): boolean => Boolean(query.value.trim()) || !collapsed.value.has(key)

const rows = computed<Row[]>(() => {
  const out: Row[] = []
  const walk = (node: TriggerTreeNode, depth: number): void => {
    out.push({ type: 'node', key: node.key, depth, node, count: countLeaves(node) })
    if (!isOpen(node.key)) return
    node.leaves.forEach((leaf) => out.push({ type: 'leaf', key: leaf.key, depth: depth + 1, leaf, owner: node }))
    node.children.forEach((child) => walk(child, depth + 1))
  }
  tree.value.forEach((node) => walk(node, 0))
  return out
})

watch(fullTree, () => {
  // Keep the detail pane in sync after a save; drop it when the trigger is gone.
  if (!selected.value) return
  const key = selected.value.leaf.key
  const row = rows.value.find((r) => r.type === 'leaf' && r.key === key)
  selected.value = row && row.type === 'leaf' ? { leaf: row.leaf, owner: row.owner } : null
})

function toggle(key: string): void {
  const next = new Set(collapsed.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  collapsed.value = next
}

function collectKeys(nodes: TriggerTreeNode[], acc: string[] = []): string[] {
  nodes.forEach((node) => {
    acc.push(node.key)
    collectKeys(node.children, acc)
  })
  return acc
}

function expandAll(): void {
  collapsed.value = new Set()
}

function collapseAll(): void {
  collapsed.value = new Set(collectKeys(tree.value).filter((key) => !key.startsWith('group:')))
}

const NODE_ICONS: Record<string, any> = {
  global: Globe,
  protagonist: User,
  sequence: BookOpen,
  scene: MapPin,
  exit: DoorOpen,
  npc: Users,
  object: Package,
  group: FolderTree,
}

const LEAF_STYLES: Record<string, { icon: any; color: string; tag: string }> = {
  script: { icon: Code2, color: 'text-emerald-300', tag: 'script' },
  text: { icon: Type, color: 'text-sky-300', tag: 'text' },
  guard: { icon: ShieldCheck, color: 'text-amber-300', tag: 'guard' },
  soft_rule: { icon: MessageSquareQuote, color: 'text-orange-300', tag: 'soft rule' },
  scoped_script: { icon: Layers, color: 'text-violet-300', tag: 'sequence script' },
  linked: { icon: Link2, color: 'text-slate-400', tag: 'linked' },
}

const canEdit = (node: TriggerTreeNode): boolean => node.kind !== 'group'
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 bg-slate-900/60 border border-white/10 rounded-2xl p-5 backdrop-blur-md">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-violet-600 to-emerald-500 flex items-center justify-center shadow-lg">
          <FolderTree class="w-5 h-5 text-white" />
        </div>
        <div>
          <h2 class="text-xl font-black text-white flex items-center gap-2">
            Trigger Overview
            <span class="text-xs px-2 py-0.5 rounded-full bg-violet-500/20 border border-violet-500/40 text-violet-300 font-bold">
              {{ totalTriggers }} configured
            </span>
          </h2>
          <p class="text-xs text-slate-400 mt-0.5">
            Every script, text and guard of the adventure in one tree. Scripts that target an entity are also listed under it as linked.
          </p>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <input
          v-model="query"
          type="search"
          placeholder="Search names, triggers, code…"
          class="w-56 bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-violet-500/50 outline-none"
        />
        <label class="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
          <input v-model="onlyConfigured" type="checkbox" class="accent-violet-500" />
          Only with triggers
        </label>
        <button type="button" class="px-3 py-2 rounded-xl text-[11px] font-bold uppercase tracking-wider text-slate-400 hover:text-white hover:bg-white/5" @click="expandAll">Expand all</button>
        <button type="button" class="px-3 py-2 rounded-xl text-[11px] font-bold uppercase tracking-wider text-slate-400 hover:text-white hover:bg-white/5" @click="collapseAll">Collapse all</button>
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-4 items-start">
      <!-- Tree -->
      <div class="bg-slate-900/60 border border-white/10 rounded-2xl p-3 max-h-[70vh] overflow-y-auto">
        <p v-if="rows.length === 0" class="p-6 text-center text-xs text-slate-500 italic">
          {{ query ? 'Nothing matches your search.' : 'No triggers configured yet.' }}
        </p>
        <template v-for="row in rows" :key="row.key">
          <div
            v-if="row.type === 'node'"
            class="group flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-white/5 cursor-pointer"
            :style="{ paddingLeft: `${row.depth * 18 + 8}px` }"
            @click="toggle(row.key)"
          >
            <component :is="isOpen(row.key) ? ChevronDown : ChevronRight" class="w-3.5 h-3.5 text-slate-500 shrink-0" />
            <component :is="NODE_ICONS[row.node.kind]" class="w-3.5 h-3.5 shrink-0" :class="row.node.kind === 'group' ? 'text-slate-400' : 'text-violet-300'" />
            <span class="text-xs truncate" :class="row.node.kind === 'group' ? 'font-black uppercase tracking-widest text-slate-300' : 'font-semibold text-white'">
              {{ row.node.label }}
            </span>
            <span v-if="row.node.subtitle" class="text-[10px] text-slate-500 shrink-0">{{ row.node.subtitle }}</span>
            <span class="ml-auto text-[10px] font-mono shrink-0" :class="row.count ? 'text-emerald-300' : 'text-slate-600'">{{ row.count }}</span>
            <button
              v-if="canEdit(row.node)"
              type="button"
              class="opacity-0 group-hover:opacity-100 p-1 rounded text-slate-400 hover:text-white hover:bg-white/10 transition-opacity"
              title="Open editor"
              @click.stop="emit('edit', row.node)"
            >
              <PencilLine class="w-3 h-3" />
            </button>
          </div>
          <button
            v-else
            type="button"
            class="w-full flex items-center gap-2 rounded-lg px-2 py-1 text-left transition-colors"
            :class="selected?.leaf.key === row.key ? 'bg-violet-500/15 ring-1 ring-violet-400/40' : 'hover:bg-white/5'"
            :style="{ paddingLeft: `${row.depth * 18 + 8}px` }"
            @click="selected = { leaf: row.leaf, owner: row.owner }"
          >
            <component :is="LEAF_STYLES[row.leaf.kind].icon" class="w-3.5 h-3.5 shrink-0" :class="LEAF_STYLES[row.leaf.kind].color" />
            <span class="text-xs text-slate-200 truncate">{{ row.leaf.label }}</span>
            <span class="ml-auto text-[9px] uppercase tracking-wider shrink-0" :class="LEAF_STYLES[row.leaf.kind].color">{{ LEAF_STYLES[row.leaf.kind].tag }}</span>
          </button>
        </template>
      </div>

      <!-- Detail -->
      <div class="bg-slate-900/60 border border-white/10 rounded-2xl p-5 xl:sticky xl:top-4">
        <template v-if="selected">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="text-[10px] font-black uppercase tracking-widest text-slate-500">{{ selected.owner.label }}</p>
              <h3 class="text-sm font-black text-white flex items-center gap-2">
                <component :is="LEAF_STYLES[selected.leaf.kind].icon" class="w-4 h-4" :class="LEAF_STYLES[selected.leaf.kind].color" />
                {{ selected.leaf.label }}
              </h3>
              <p v-if="selected.leaf.note" class="mt-1 text-[11px] text-slate-400">{{ selected.leaf.note }}</p>
            </div>
            <button
              v-if="canEdit(selected.owner)"
              type="button"
              class="shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-[11px] font-black uppercase tracking-wider"
              @click="emit('edit', selected.owner)"
            >
              <PencilLine class="w-3.5 h-3.5" /> Edit
            </button>
          </div>
          <pre class="mt-4 max-h-[55vh] overflow-auto rounded-xl bg-black/50 border border-white/5 p-4 text-[11px] leading-relaxed text-slate-200 font-mono whitespace-pre-wrap">{{ selected.leaf.code }}</pre>
          <p v-if="selected.leaf.kind === 'linked'" class="mt-2 text-[10px] text-slate-500">
            Defined elsewhere (global or sequence script) and targeting this entity.
          </p>
        </template>
        <p v-else class="text-xs text-slate-500 italic">Select a trigger in the tree to see its code.</p>
      </div>
    </div>
  </div>
</template>
