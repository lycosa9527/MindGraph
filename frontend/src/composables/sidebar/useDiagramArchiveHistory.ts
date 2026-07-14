/**
 * Grouping and persistence helpers for saved-diagram archive folders.
 */
import { computed, ref, type ComputedRef, type Ref } from 'vue'

import type { DiagramFolder, SavedDiagram } from '@/stores/savedDiagrams'

const COLLAPSED_STORAGE_KEY = 'mindgraph:diagram-archive:collapsed'

export interface TimeGroupedDiagrams {
  pinned: SavedDiagram[]
  today: SavedDiagram[]
  yesterday: SavedDiagram[]
  week: SavedDiagram[]
  month: SavedDiagram[]
}

export function loadCollapsedFolderIds(): Set<string> {
  try {
    const raw = sessionStorage.getItem(COLLAPSED_STORAGE_KEY)
    if (!raw) return new Set()
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return new Set()
    return new Set(parsed.filter((id): id is string => typeof id === 'string'))
  } catch {
    return new Set()
  }
}

export function persistCollapsedFolderIds(collapsed: Set<string>): void {
  try {
    sessionStorage.setItem(COLLAPSED_STORAGE_KEY, JSON.stringify([...collapsed]))
  } catch {
    // ignore quota / private mode
  }
}

export function diagramsInFolder(
  diagrams: SavedDiagram[],
  folderId: string
): SavedDiagram[] {
  return diagrams
    .filter((diagram) => diagram.folder_id === folderId)
    .sort((a, b) => {
      if (a.is_pinned !== b.is_pinned) {
        return a.is_pinned ? -1 : 1
      }
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    })
}

export function groupUncategorizedDiagrams(
  diagrams: SavedDiagram[],
  options: { limit?: number; showAll?: boolean } = {}
): TimeGroupedDiagrams {
  const groups: TimeGroupedDiagrams = {
    pinned: [],
    today: [],
    yesterday: [],
    week: [],
    month: [],
  }

  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterdayStart = todayStart - 24 * 60 * 60 * 1000
  const weekStart = todayStart - 7 * 24 * 60 * 60 * 1000

  const uncategorized = diagrams.filter((diagram) => !diagram.folder_id)
  const limit = options.showAll ? uncategorized.length : (options.limit ?? uncategorized.length)
  const items = uncategorized.slice(0, limit)

  items.forEach((diagram) => {
    if (diagram.is_pinned) {
      groups.pinned.push(diagram)
      return
    }

    const diagramTime = new Date(diagram.updated_at).getTime()
    if (diagramTime >= todayStart) {
      groups.today.push(diagram)
    } else if (diagramTime >= yesterdayStart) {
      groups.yesterday.push(diagram)
    } else if (diagramTime >= weekStart) {
      groups.week.push(diagram)
    } else {
      groups.month.push(diagram)
    }
  })

  return groups
}

export function syncFolderDiagramCounts(
  folders: DiagramFolder[],
  diagrams: SavedDiagram[]
): DiagramFolder[] {
  const counts = new Map<string, number>()
  for (const diagram of diagrams) {
    if (!diagram.folder_id) continue
    counts.set(diagram.folder_id, (counts.get(diagram.folder_id) ?? 0) + 1)
  }
  return folders.map((folder) => ({
    ...folder,
    diagram_count: counts.get(folder.id) ?? 0,
  }))
}

export function folderNameById(
  folders: DiagramFolder[],
  folderId: string | null | undefined
): string | null {
  if (!folderId) return null
  return folders.find((folder) => folder.id === folderId)?.name ?? null
}

export function useDiagramArchiveHistory(
  diagrams: Ref<SavedDiagram[]> | ComputedRef<SavedDiagram[]>,
  folders: Ref<DiagramFolder[]> | ComputedRef<DiagramFolder[]>,
  initialLimit = 10
) {
  const showAllUncategorized = ref(false)
  const collapsedFolders = ref<Set<string>>(loadCollapsedFolderIds())

  const uncategorizedDiagrams = computed(() =>
    diagrams.value.filter((diagram) => !diagram.folder_id)
  )

  const groupedUncategorized = computed(() =>
    groupUncategorizedDiagrams(uncategorizedDiagrams.value, {
      limit: initialLimit,
      showAll: showAllUncategorized.value,
    })
  )

  const hasMoreUncategorized = computed(
    () => uncategorizedDiagrams.value.length > initialLimit && !showAllUncategorized.value
  )

  const remainingUncategorizedCount = computed(
    () => uncategorizedDiagrams.value.length - initialLimit
  )

  function isFolderCollapsed(folderId: string): boolean {
    return collapsedFolders.value.has(folderId)
  }

  function toggleFolderCollapsed(folderId: string): void {
    const next = new Set(collapsedFolders.value)
    if (next.has(folderId)) {
      next.delete(folderId)
    } else {
      next.add(folderId)
    }
    collapsedFolders.value = next
    persistCollapsedFolderIds(next)
  }

  function diagramsForFolder(folderId: string): SavedDiagram[] {
    return diagramsInFolder(diagrams.value, folderId)
  }

  return {
    showAllUncategorized,
    collapsedFolders,
    uncategorizedDiagrams,
    groupedUncategorized,
    hasMoreUncategorized,
    remainingUncategorizedCount,
    isFolderCollapsed,
    toggleFolderCollapsed,
    diagramsForFolder,
  }
}
