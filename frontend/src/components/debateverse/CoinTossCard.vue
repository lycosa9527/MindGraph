<script setup lang="ts">
/**
 * CoinTossCard - Card component for coin toss stage
 * 
 * Displays stage info, rules, and generates positions using Doubao LLM
 * Consolidated component that handles all coin toss stage logic
 */
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { Coins } from 'lucide-vue-next'
import { useLanguage } from '@/composables/useLanguage'
import { useDebateVerseStore } from '@/stores/debateverse'

const { isZh } = useLanguage()
const store = useDebateVerseStore()

// Position generation state
const isGenerating = ref(false)
const affirmativePosition = ref('')
const negativePosition = ref('')
const error = ref<string | null>(null)
let abortController: AbortController | null = null

// Show card during coin_toss stage, or during opening if positions were generated
const showCard = computed(() => {
  const stage = store.currentStage || 'setup'
  return (
    stage === 'coin_toss' ||
    (stage === 'opening' && (affirmativePosition.value || negativePosition.value))
  )
})

// Parse positions from text (supports both Chinese and English)
function parsePositions(text: string) {
  // Try Chinese format first
  let affirmativeMatch = text.match(/正方立场[：:]\s*(.+?)(?=反方立场|$)/s)
  let negativeMatch = text.match(/反方立场[：:]\s*(.+?)$/s)
  
  // If not found, try English format
  if (!affirmativeMatch) {
    affirmativeMatch = text.match(/Affirmative Position[：:]\s*(.+?)(?=Negative Position|$)/is)
  }
  if (!negativeMatch) {
    negativeMatch = text.match(/Negative Position[：:]\s*(.+?)$/is)
  }
  
  if (affirmativeMatch) {
    affirmativePosition.value = affirmativeMatch[1].trim()
  }
  if (negativeMatch) {
    negativePosition.value = negativeMatch[1].trim()
  }
}

// Generate positions using Doubao
async function generatePositions(sessionId: string, topic: string, language: string = 'zh') {
  if (!sessionId || !topic || isGenerating.value) {
    return
  }
  
  isGenerating.value = true
  error.value = null
  affirmativePosition.value = ''
  negativePosition.value = ''
  
  // Abort previous request if exists
  if (abortController) {
    abortController.abort()
  }
  
  abortController = new AbortController()
  
  try {
    // Session ID already contains the topic, so we don't need to pass it separately
    const url = `/api/debateverse/sessions/${sessionId}/generate-positions?language=${language}`
    
    const response = await fetch(url, {
      method: 'GET',
      signal: abortController.signal,
      credentials: 'same-origin',
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error: ${response.status}`)
    }
    
    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('No response body')
    }
    
    const decoder = new TextDecoder()
    let buffer = ''
    let positionsText = ''
    
    while (true) {
      const { done, value } = await reader.read()
      
      if (done) {
        if (buffer.trim()) {
          // Process remaining buffer
          const lines = buffer.split('\n')
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const jsonStr = line.slice(6).trim()
              if (jsonStr) {
                try {
                  const data = JSON.parse(jsonStr)
                  if (data.type === 'token') {
                    positionsText += data.content
                    parsePositions(positionsText)
                  }
                } catch (e) {
                  console.warn('[CoinTossCard] Failed to parse SSE:', jsonStr, e)
                }
              }
            }
          }
        }
        break
      }
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6).trim()
          if (!jsonStr) continue
          
          try {
            const data = JSON.parse(jsonStr)
            
            if (data.type === 'token') {
              positionsText += data.content
              parsePositions(positionsText)
            } else if (data.type === 'done') {
              break
            } else if (data.type === 'error') {
              throw new Error(data.error || 'Position generation error')
            }
          } catch (e) {
            if (e instanceof Error && e.message.includes('Position generation')) {
              throw e
            }
            console.warn('[CoinTossCard] Failed to parse SSE:', jsonStr, e)
          }
        }
      }
    }
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'AbortError') {
      console.log('[CoinTossCard] Generation aborted')
    } else {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error'
      error.value = errorMsg
      console.error('[CoinTossCard] Generation error:', err)
    }
  } finally {
    isGenerating.value = false
    abortController = null
  }
}

// Generate positions when session is created
watch(
  () => [store.currentSessionId, store.currentSession?.session.topic],
  ([sessionId, topic]) => {
    if (sessionId && topic && !isGenerating.value && 
        !affirmativePosition.value && !negativePosition.value) {
      const language = 'zh' // Default language, can be extended if stored in session
      generatePositions(sessionId, topic, language)
    }
  },
  { immediate: true }
)

// Check on mount
onMounted(() => {
  if (store.currentSessionId && store.currentSession?.session.topic &&
      !isGenerating.value &&
      !affirmativePosition.value &&
      !negativePosition.value) {
    const language = 'zh' // Default language, can be extended if stored in session
    generatePositions(store.currentSessionId, store.currentSession.session.topic, language)
  }
})

onUnmounted(() => {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  isGenerating.value = false
})
</script>

<template>
  <div
    v-if="showCard"
    class="coin-toss-card mb-4"
  >
    <div class="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-lg">
      <div class="flex-shrink-0 w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
        <Coins
          :size="20"
          class="text-blue-600"
        />
      </div>
      <div class="flex-1">
        <!-- Stage Title -->
        <h3 class="text-sm font-semibold text-blue-900 mb-2">
          {{ isZh ? '掷硬币阶段' : 'Coin Toss Stage' }}
        </h3>
        
        <!-- Stage Rules/Description -->
        <div class="space-y-1.5 text-sm text-blue-700">
          <p>
            {{ isZh ? 'AI模型已随机分配给各个辩论角色，赛前通过掷硬币决定发言顺序或选择正反方立场' : 'AI models have been randomly assigned to debate roles. Before the debate, determine speaking order or choose affirmative/negative positions through coin toss' }}
          </p>
          
          <!-- Current Topic -->
          <div v-if="store.currentSession?.session.topic" class="mt-2 pt-2 border-t border-blue-200">
            <p class="text-blue-800 font-medium">
              <span class="font-semibold">{{ isZh ? '辩论主题：' : 'Debate Topic: ' }}</span>
              <span>{{ store.currentSession.session.topic }}</span>
            </p>
          </div>
          
          <!-- Position Generation -->
          <div v-if="isGenerating || affirmativePosition || negativePosition" class="mt-3 pt-3 border-t border-blue-200">
            <div v-if="isGenerating" class="text-blue-600 italic">
              {{ isZh ? '正在生成正反方立场...' : 'Generating positions...' }}
            </div>
            <div v-else-if="affirmativePosition || negativePosition" class="space-y-2">
              <div v-if="affirmativePosition" class="text-blue-800">
                <span class="font-semibold">{{ isZh ? '正方立场：' : 'Affirmative Position: ' }}</span>
                <span class="whitespace-pre-wrap">{{ affirmativePosition }}</span>
              </div>
              <div v-if="negativePosition" class="text-blue-800">
                <span class="font-semibold">{{ isZh ? '反方立场：' : 'Negative Position: ' }}</span>
                <span class="whitespace-pre-wrap">{{ negativePosition }}</span>
              </div>
              <div class="text-blue-600 text-xs italic mt-2">
                {{ isZh ? '请点击下一步按钮使更改生效' : 'Please click the next button to take changes in effect' }}
              </div>
            </div>
            <div v-if="error" class="text-red-600 text-xs mt-2">
              {{ error }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.coin-toss-card {
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
