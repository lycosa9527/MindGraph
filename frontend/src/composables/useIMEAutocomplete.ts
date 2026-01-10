/**
 * useIMEAutocomplete - Chinese IME-style autocomplete for node editing
 *
 * Provides:
 * - Debounced API calls when user types (300ms)
 * - Ghost text suggestion (first suggestion appended to input)
 * - Numbered suggestions (1-5) with keyboard selection
 * - Pagination with -/= keys (fetch more from LLM)
 * - Tab to accept ghost suggestion
 *
 * Keyboard shortcuts:
 * - Tab: Accept ghost suggestion
 * - 1-5: Select numbered suggestion
 * - -: Previous page
 * - =: Next page
 * - Escape: Close dropdown
 */
import { computed, ref, watch } from 'vue'

import { useDebounceFn } from '@vueuse/core'

import { useLanguage } from './useLanguage'
import { authFetch } from '@/utils/api'

// Types
export interface IMESuggestion {
  text: string
  confidence: number
}

export interface IMEAutocompleteOptions {
  /** Diagram type for context */
  diagramType: string
  /** Main topic(s) for context */
  mainTopics: string[]
  /** Node category (e.g., 'similarities', 'differences', 'children') */
  nodeCategory?: string
  /** Existing nodes in the same category (to avoid duplicates) */
  existingNodes?: string[]
  /** Debounce delay in ms (default: 300) */
  debounceMs?: number
  /** Number of suggestions per page (default: 5) */
  pageSize?: number
}

export interface IMEAutocompleteState {
  /** All fetched suggestions */
  suggestions: IMESuggestion[]
  /** Current page (0-indexed) */
  currentPage: number
  /** Whether suggestions are loading */
  isLoading: boolean
  /** Whether the dropdown is visible */
  isVisible: boolean
  /** Error message if any */
  error: string | null
  /** Current user input */
  userInput: string
  /** Previous suggestions to avoid duplicates across pages */
  previousSuggestions: string[]
}

/**
 * IME-style autocomplete composable
 */
export function useIMEAutocomplete(options: IMEAutocompleteOptions) {
  const {
    diagramType,
    mainTopics,
    nodeCategory = 'general',
    existingNodes = [],
    debounceMs = 300,
    pageSize = 5,
  } = options

  const { isZh } = useLanguage()

  // State
  const state = ref<IMEAutocompleteState>({
    suggestions: [],
    currentPage: 0,
    isLoading: false,
    isVisible: false,
    error: null,
    userInput: '',
    previousSuggestions: [],
  })

  // Computed: Current page suggestions
  const currentSuggestions = computed(() => {
    const start = state.value.currentPage * pageSize
    const end = start + pageSize
    return state.value.suggestions.slice(start, end)
  })

  // Computed: Ghost text (first suggestion that starts with user input)
  const ghostText = computed(() => {
    if (!state.value.isVisible || state.value.suggestions.length === 0) {
      return ''
    }
    const input = state.value.userInput.toLowerCase()
    if (!input) return ''

    // Find first suggestion that could be an extension of input
    for (const suggestion of state.value.suggestions) {
      const suggestionLower = suggestion.text.toLowerCase()
      if (suggestionLower.startsWith(input) && suggestionLower !== input) {
        // Return the part after the user's input
        return suggestion.text.slice(state.value.userInput.length)
      }
    }
    // If no prefix match, return first suggestion as ghost
    return state.value.suggestions[0]?.text || ''
  })

  // Computed: Has more pages
  const hasNextPage = computed(() => {
    return true // Always allow fetching more from LLM
  })

  const hasPrevPage = computed(() => {
    return state.value.currentPage > 0
  })

  // Computed: Total pages loaded
  const totalPages = computed(() => {
    return Math.ceil(state.value.suggestions.length / pageSize)
  })

  /**
   * Fetch suggestions from API
   */
  async function fetchSuggestions(partialInput: string, pageOffset: number = 0): Promise<void> {
    if (state.value.isLoading) return

    state.value.isLoading = true
    state.value.error = null

    try {
      const response = await authFetch('/api/tab_suggestions', {
        method: 'POST',
        body: JSON.stringify({
          mode: 'autocomplete',
          diagram_type: diagramType,
          main_topics: mainTopics,
          node_category: nodeCategory,
          partial_input: partialInput,
          existing_nodes: [...existingNodes, ...state.value.previousSuggestions],
          language: isZh.value ? 'zh' : 'en',
          llm: 'doubao',
          page_offset: pageOffset,
        }),
      })

      if (!response.ok) {
        if (response.status === 403) {
          // Feature disabled
          state.value.error = 'IME autocomplete feature is disabled'
          state.value.isVisible = false
          return
        }
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()

      if (data.success && data.suggestions) {
        const newSuggestions: IMESuggestion[] = data.suggestions.map(
          (s: { text: string; confidence: number }) => ({
            text: s.text,
            confidence: s.confidence,
          })
        )

        if (pageOffset === 0) {
          // First page - replace all
          state.value.suggestions = newSuggestions
          state.value.currentPage = 0
          state.value.previousSuggestions = []
        } else {
          // Additional page - append
          state.value.suggestions = [...state.value.suggestions, ...newSuggestions]
        }

        state.value.isVisible = newSuggestions.length > 0
      } else {
        state.value.error = data.error || 'Failed to fetch suggestions'
      }
    } catch (error) {
      console.error('[IMEAutocomplete] Error fetching suggestions:', error)
      state.value.error = error instanceof Error ? error.message : 'Unknown error'
    } finally {
      state.value.isLoading = false
    }
  }

  // Debounced fetch
  const debouncedFetch = useDebounceFn((input: string) => {
    if (input.trim().length > 0) {
      fetchSuggestions(input, 0)
    } else {
      state.value.isVisible = false
      state.value.suggestions = []
    }
  }, debounceMs)

  /**
   * Update user input and trigger debounced fetch
   */
  function updateInput(input: string): void {
    state.value.userInput = input
    debouncedFetch(input)
  }

  /**
   * Accept a suggestion (by index or ghost)
   */
  function acceptSuggestion(index?: number): string | null {
    if (!state.value.isVisible) return null

    let selectedText: string | null = null

    if (index !== undefined && index >= 0 && index < currentSuggestions.value.length) {
      // Select by number (1-5 maps to 0-4)
      selectedText = currentSuggestions.value[index].text
    } else if (ghostText.value) {
      // Accept ghost text (append to current input)
      selectedText = state.value.userInput + ghostText.value
    }

    if (selectedText) {
      // Track accepted suggestion to avoid duplicates
      state.value.previousSuggestions.push(selectedText)
      hide()
    }

    return selectedText
  }

  /**
   * Go to next page (fetch more if needed)
   */
  async function nextPage(): Promise<void> {
    const nextPageIndex = state.value.currentPage + 1
    const neededSuggestions = (nextPageIndex + 1) * pageSize

    if (state.value.suggestions.length < neededSuggestions) {
      // Need to fetch more
      const pageOffset = Math.floor(state.value.suggestions.length / pageSize)
      await fetchSuggestions(state.value.userInput, pageOffset)
    }

    if (state.value.suggestions.length > state.value.currentPage * pageSize + pageSize) {
      state.value.currentPage = nextPageIndex
    }
  }

  /**
   * Go to previous page
   */
  function prevPage(): void {
    if (state.value.currentPage > 0) {
      state.value.currentPage -= 1
    }
  }

  /**
   * Hide the dropdown
   */
  function hide(): void {
    state.value.isVisible = false
  }

  /**
   * Show the dropdown (if has suggestions)
   */
  function show(): void {
    if (state.value.suggestions.length > 0) {
      state.value.isVisible = true
    }
  }

  /**
   * Reset state
   */
  function reset(): void {
    state.value = {
      suggestions: [],
      currentPage: 0,
      isLoading: false,
      isVisible: false,
      error: null,
      userInput: '',
      previousSuggestions: [],
    }
  }

  /**
   * Handle keyboard events
   * Returns true if the event was handled
   */
  function handleKeydown(event: KeyboardEvent): boolean {
    if (!state.value.isVisible) return false

    // Tab: Accept ghost suggestion
    if (event.key === 'Tab') {
      const accepted = acceptSuggestion()
      if (accepted) {
        event.preventDefault()
        return true
      }
    }

    // Number keys 1-5: Select suggestion
    if (event.key >= '1' && event.key <= '5') {
      const index = parseInt(event.key) - 1
      if (index < currentSuggestions.value.length) {
        const accepted = acceptSuggestion(index)
        if (accepted) {
          event.preventDefault()
          return true
        }
      }
    }

    // = key: Next page
    if (event.key === '=') {
      event.preventDefault()
      nextPage()
      return true
    }

    // - key: Previous page
    if (event.key === '-') {
      event.preventDefault()
      prevPage()
      return true
    }

    // Escape: Hide dropdown
    if (event.key === 'Escape') {
      hide()
      return true
    }

    return false
  }

  return {
    // State
    state,
    currentSuggestions,
    ghostText,
    hasNextPage,
    hasPrevPage,
    totalPages,
    isLoading: computed(() => state.value.isLoading),
    isVisible: computed(() => state.value.isVisible),
    error: computed(() => state.value.error),

    // Methods
    updateInput,
    acceptSuggestion,
    nextPage,
    prevPage,
    hide,
    show,
    reset,
    handleKeydown,
    fetchSuggestions,
  }
}
