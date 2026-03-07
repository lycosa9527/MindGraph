/**
 * Auto-Complete Composable
 * ========================
 *
 * Handles AI-powered diagram generation (auto-complete functionality).
 *
 * Features:
 * - Calls 3 LLMs in parallel (Qwen, DeepSeek, Doubao)
 * - First-result-wins: renders immediately when first LLM completes
 * - Caches results for switching between LLM perspectives
 * - Placeholder text detection and filtering
 * - 10-minute TTL cache with validation
 *
 * Usage:
 *   const { isGenerating, autoComplete, switchToModel } = useAutoComplete()
 *
 *   // Generate from all 3 LLMs
 *   await autoComplete()
 *
 *   // Switch to different model's result
 *   switchToModel('deepseek')
 */
import { computed } from 'vue'

import { eventBus, useLanguage, useNotifications } from '@/composables'
import { useDiagramStore, useLLMResultsStore } from '@/stores'
import { authFetch } from '@/utils/api'

// LLM Models to use for parallel generation
const LLM_MODELS = ['qwen', 'deepseek', 'doubao'] as const

// Chinese placeholder patterns (from old JS diagram-validator.js)
const CHINESE_PLACEHOLDERS = [
  /^分支\s*\d+$/, // 分支1, 分支2
  /^子项\s*[\d.]+$/, // 子项1.1, 子项2.3
  /^子节点\s*[\d.]+$/, // 子节点1.1
  /^子\s*[\d.]+$/, // 子1.1
  /^新.*$/, // 新节点, 新属性, 新步骤, 新原因, 新结果, etc.
  /^属性\s*\d+$/, // 属性1, 属性2
  /^步骤\s*\d+$/, // 步骤1, 步骤2
  /^子步骤\s*[\d.]+$/, // 子步骤1.1, 子步骤2.2 (Flow Map)
  /^原因\s*\d+$/, // 原因1
  /^结果\s*\d+$/, // 结果1
  /^联想\s*\d+$/, // 联想1, 联想2 (Circle Map context nodes)
  /^事件流程$/, // 事件流程 (Flow Map title)
  /^事件$/, // 事件 (Multi-Flow Map event)
  /^主题\s*\d+$/, // 主题1
  /^主题$/, // 主题 (Circle Map default)
  /^主题[A-Z]$/, // 主题A, 主题B (Double Bubble Map)
  /^相似点\s*\d+$/, // 相似点1, 相似点2 (Double Bubble Map)
  /^不同点[A-Z]\d+$/, // 不同点A1, 不同点B2 (Double Bubble Map)
  /^如同$/, // 如同 (Bridge Map relating factor)
  /^事物[A-Z]\d+$/, // 事物A1, 事物B1 (Bridge Map)
  /^项目[\d.]+$/, // 项目1.1, 项目2.3 (Tree Map)
  /^根主题$/, // 根主题 (Tree Map)
  /^类别\s*\d+$/, // 类别1, 类别2 (Tree Map)
  /^分类\s*\d+$/, // 分类1
  /^叶子\s*\d+$/, // 叶子1
  /^部分\s*\d+$/, // 部分1, 部分2 (Brace Map)
  /^子部分\s*[\d.]+$/, // 子部分1.1, 子部分1.2 (Brace Map)
  /^新子部分\s*[\d.]+$/, // 新子部分 1, 新子部分 2 (Brace Map default subparts)
  /^左\s*\d+$/, // 左1
  /^右\s*\d+$/, // 右1
  /^中心主题$/, // 中心主题
  /^主要主题$/, // 主要主题
  /^要点\s*\d+$/, // 要点1
  /^概念\s*\d+$/, // 概念1
  /^关联$/, // 关联
  /^整体$/, // 整体 (Brace Map)
  /^特征\s*\d+$/, // 特征1 (Bubble Map)
  /^请输入/, // 请输入主题
  /^点击编辑/, // 点击编辑
  /^\[点击设置\]$/, // Bridge map dimension placeholder
]

// English placeholder patterns
const ENGLISH_PLACEHOLDERS = [
  /^Branch\s+\d+$/i, // Branch 1, Branch 2
  /^Child\s+[\d.]+$/i, // Child 1.1, Child 2.3
  /^New\s+.*$/i, // New Node, New Attribute, New Step, etc.
  /^Attribute\s+\d+$/i, // Attribute 1, Attribute 2
  /^Step\s+\d+$/i, // Step 1, Step 2
  /^Substep\s+[\d.]+$/i, // Substep 1.1, Substep 2.2 (Flow Map)
  /^Cause\s+\d+$/i, // Cause 1
  /^Effect\s+\d+$/i, // Effect 1
  /^Context\s+\d+$/i, // Context 1, Context 2 (Circle Map context nodes)
  /^Process$/i, // Process (Flow Map title)
  /^Main\s+Event$/i, // Main Event (Multi-Flow Map event)
  /^Topic\s*\d*$/i, // Topic, Topic 1
  /^Topic\s+[A-Z]$/i, // Topic A, Topic B (Double Bubble Map)
  /^Similarity\s+\d+$/i, // Similarity 1, 2 (Double Bubble Map)
  /^Difference\s+[A-Z]\d+$/i, // Difference A1, B2 (Double Bubble Map)
  /^as$/i, // as (Bridge Map relating factor)
  /^Item\s+\d+$/i, // Item 1, Item 2 (Bridge Map)
  /^Item\s+[A-Z]$/i, // Item A, Item B (Bridge Map)
  /^Item\s+[\d.]+$/i, // Item 1.1, Item 2.3 (Tree Map)
  /^Root\s+Topic$/i, // Root Topic (Tree Map)
  /^Category\s+\d+$/i, // Category 1 (Tree Map)
  /^Leaf\s+\d+$/i, // Leaf 1
  /^Part\s+\d+$/i, // Part 1 (Brace Map)
  /^Subpart\s+[\d.]+$/i, // Subpart 1.1, Subpart 1.2 (Brace Map)
  /^New\s+Subpart\s+\d+$/i, // New Subpart 1, New Subpart 2 (Brace Map default subparts)
  /^Left\s+\d+$/i, // Left 1
  /^Right\s+\d+$/i, // Right 1
  /^Main\s+Topic$/i, // Main Topic
  /^Central\s+Topic$/i, // Central Topic
  /^Point\s+\d+$/i, // Point 1
  /^Concept\s+\d+$/i, // Concept 1
  /^Relation(ship)?$/i, // Relation, Relationship
  /^Whole$/i, // Whole (Brace Map)
  /^Event$/i, // Event (Multi-Flow Map)
  /^Enter\s+/i, // Enter topic
  /^Click\s+to\s+edit/i, // Click to edit
  /^Association\s*\d*$/i, // Association 1 (Circle Map)
  /^Property\s+\d+$/i, // Property 1 (Bubble Map)
]

// Combined placeholder patterns
const PLACEHOLDER_PATTERNS = [...CHINESE_PLACEHOLDERS, ...ENGLISH_PLACEHOLDERS]

/**
 * Check if text is a placeholder that shouldn't be used as topic
 */
export function isPlaceholderText(text: string | undefined | null): boolean {
  if (!text || !text.trim()) return true
  return PLACEHOLDER_PATTERNS.some((pattern) => pattern.test(text.trim()))
}

/**
 * Auto-complete composable for AI diagram generation
 */
export function useAutoComplete() {
  const diagramStore = useDiagramStore()
  const llmResultsStore = useLLMResultsStore()
  const { isZh } = useLanguage()
  const notify = useNotifications()

  // Expose store state
  const isGenerating = computed(() => llmResultsStore.isGenerating)
  const selectedModel = computed(() => llmResultsStore.selectedModel)
  const modelStates = computed(() => llmResultsStore.modelStates)
  const hasAnyResults = computed(() => llmResultsStore.hasAnyResults)
  const readyModels = computed(() => llmResultsStore.readyModels)

  type NodeWithText = {
    id?: string
    type?: string
    text?: string
    data?: { label?: string }
  }

  function getNodeText(n: NodeWithText | undefined): string {
    if (!n) return ''
    return (n.text ?? (n.data as { label?: string })?.label ?? '').trim()
  }

  /**
   * Extract main topic from current diagram.
   * Data stores { nodes, connections }; spec fields (topic, whole, event, etc.) are filtered out
   * on load, so we must extract from nodes for all diagram types.
   */
  function extractMainTopic(): string | null {
    const spec = diagramStore.data as Record<string, unknown> | null
    const type = diagramStore.type

    if (!spec || !type) return null

    const nodes = spec.nodes as NodeWithText[] | undefined
    if (!nodes || !Array.isArray(nodes)) return null

    // Strategy 1: bubble_map, circle_map, tree_map: topic/root node
    if (type === 'bubble_map' || type === 'circle_map' || type === 'tree_map') {
      const topicNode = nodes.find(
        (n) => n.id === 'topic' || n.id === 'tree-topic' || n.type === 'topic'
      )
      const text = getNodeText(topicNode)
      if (text && !isPlaceholderText(text)) return text
    }

    // Strategy 2: Brace map: whole node (root, type 'topic')
    if (type === 'brace_map') {
      const wholeNode = nodes.find((n) => n.type === 'topic')
      const text = getNodeText(wholeNode)
      if (text && !isPlaceholderText(text)) return text
    }

    // Strategy 3: Multi-flow map: event node (id 'event')
    if (type === 'multi_flow_map') {
      const eventNode = nodes.find((n) => n.id === 'event' || n.type === 'topic')
      const text = getNodeText(eventNode)
      if (text && !isPlaceholderText(text)) return text
    }

    // Strategy 4: Flow map: flow-topic node (id 'flow-topic')
    if (type === 'flow_map') {
      const topicNode = nodes.find((n) => n.id === 'flow-topic')
      const text = getNodeText(topicNode)
      if (text && !isPlaceholderText(text)) return text
    }

    // Strategy 5: Double bubble map: left/right topic nodes
    if (type === 'double_bubble_map') {
      const leftNode = nodes.find((n) => n.id === 'left-topic')
      const rightNode = nodes.find((n) => n.id === 'right-topic')
      const left = getNodeText(leftNode)
      const right = getNodeText(rightNode)
      const leftValid = left && !isPlaceholderText(left)
      const rightValid = right && !isPlaceholderText(right)
      if (leftValid && rightValid) {
        return isZh.value ? `${left} 和 ${right}` : `${left} vs ${right}`
      }
      if (leftValid) return left
      if (rightValid) return right
    }

    // Strategy 6: Fallback - find topic/center node (bubble, circle, mindmap, etc.)
    const topicNode = nodes.find(
      (n) =>
        n.type === 'topic' ||
        n.type === 'center' ||
        n.id === 'topic' ||
        n.id === 'center' ||
        n.id === 'event'
    )
    const topicText = getNodeText(topicNode)
    if (topicText && !isPlaceholderText(topicText)) return topicText

    // Strategy 7: First non-placeholder node
    const firstValid = nodes.find((n) => {
      const t = getNodeText(n)
      return t && !isPlaceholderText(t)
    })
    const firstText = getNodeText(firstValid)
    if (firstText && !isPlaceholderText(firstText)) return firstText

    return null
  }

  /**
   * Extract existing bridge map analogies from nodes.
   * spec.analogies is filtered out on load; nodes use pair-X-left, pair-X-right.
   */
  function extractBridgeMapAnalogies(): Array<{ left: string; right: string }> {
    const spec = diagramStore.data as Record<string, unknown> | null
    if (!spec || diagramStore.type !== 'bridge_map') return []

    const nodes = spec.nodes as NodeWithText[] | undefined
    if (!nodes || !Array.isArray(nodes)) return []

    const pairIndices = new Set(
      nodes
        .filter((n) => /^pair-\d+-left$/.test(n.id ?? ''))
        .map((n) => parseInt(n.id!.replace('pair-', '').replace('-left', ''), 10))
    )

    const result: Array<{ left: string; right: string }> = []
    for (const idx of [...pairIndices].sort((a, b) => a - b)) {
      const leftNode = nodes.find((n) => n.id === `pair-${idx}-left`)
      const rightNode = nodes.find((n) => n.id === `pair-${idx}-right`)
      const left = getNodeText(leftNode)
      const right = getNodeText(rightNode)
      if (left && right && !isPlaceholderText(left) && !isPlaceholderText(right)) {
        result.push({ left, right })
      }
    }
    return result
  }

  /**
   * Extract fixed dimension if user specified one.
   * For brace_map, tree_map, bridge_map: checks dimension-label node first (user-edited),
   * then falls back to spec.dimension / spec.relating_factor (preserved in metadata).
   */
  function extractFixedDimension(): string | null {
    const spec = diagramStore.data as Record<string, unknown> | null
    if (!spec) return null

    const nodes = spec.nodes as NodeWithText[] | undefined
    const supportsDimensionLabel =
      diagramStore.type === 'brace_map' ||
      diagramStore.type === 'tree_map' ||
      diagramStore.type === 'bridge_map'
    if (nodes && Array.isArray(nodes) && supportsDimensionLabel) {
      const labelNode = nodes.find((n) => n.id === 'dimension-label')
      const labelText = getNodeText(labelNode)
      if (labelText && !isPlaceholderText(labelText)) {
        return labelText
      }
    }

    const dimension = spec.dimension as string | undefined
    if (dimension && dimension.trim() !== '') {
      return dimension.trim()
    }
    if (diagramStore.type === 'bridge_map') {
      const rf = spec.relating_factor as string | undefined
      if (rf && rf.trim() !== '' && !isPlaceholderText(rf)) {
        return rf.trim()
      }
    }
    return null
  }

  /**
   * Check if auto-complete can be triggered
   */
  function validateForAutoComplete(): { valid: boolean; error?: string } {
    if (llmResultsStore.isGenerating) {
      return {
        valid: false,
        error: isZh.value ? '正在生成中，请稍候' : 'Generation in progress, please wait',
      }
    }

    if (!diagramStore.type) {
      return { valid: false, error: isZh.value ? '请选择图表类型' : 'Please select diagram type' }
    }

    if (!diagramStore.data) {
      return { valid: false, error: isZh.value ? '没有图表数据' : 'No diagram data' }
    }

    // Concept map uses real-time relationship generation only (no multi-stage AI Generate)
    if (diagramStore.type === 'concept_map') {
      return {
        valid: false,
        error: isZh.value
          ? '概念图使用实时关系建议，请通过创建链接来生成关系'
          : 'Concept maps use real-time relationship suggestions; create links to generate',
      }
    }

    // Bridge map can work with dimension only (no topic needed)
    if (diagramStore.type === 'bridge_map') {
      const analogies = extractBridgeMapAnalogies()
      const dimension = extractFixedDimension()
      if (analogies.length > 0 || dimension) {
        return { valid: true }
      }
    }

    // Tree/brace map can work with dimension only
    if (diagramStore.type === 'tree_map' || diagramStore.type === 'brace_map') {
      const dimension = extractFixedDimension()
      if (dimension) {
        return { valid: true }
      }
    }

    // All other cases need a valid topic
    const mainTopic = extractMainTopic()
    if (!mainTopic) {
      return {
        valid: false,
        error: isZh.value ? '请先输入主题内容' : 'Please enter topic content first',
      }
    }

    return { valid: true }
  }

  /**
   * Generate diagram from a single LLM (internal)
   */
  async function generateFromSingleLLM(
    requestBody: Record<string, unknown>,
    model: string,
    signal: AbortSignal
  ): Promise<{
    model: string
    success: boolean
    spec?: Record<string, unknown>
    diagramType?: string
    error?: string
    elapsed: number
  }> {
    const startTime = Date.now()

    try {
      const response = await authFetch('/api/generate_graph', {
        method: 'POST',
        body: JSON.stringify({
          ...requestBody,
          llm: model,
        }),
        signal,
      })

      const elapsed = (Date.now() - startTime) / 1000

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Request failed' }))
        return {
          model,
          success: false,
          error: errorData.detail || `HTTP ${response.status}`,
          elapsed,
        }
      }

      const result = await response.json()

      if (result.success && result.spec) {
        let diagramType = result.diagram_type || requestBody.diagram_type
        if (diagramType === 'mind_map') {
          diagramType = 'mindmap'
        }

        return {
          model,
          success: true,
          spec: result.spec,
          diagramType,
          elapsed,
        }
      } else {
        return {
          model,
          success: false,
          error: result.error || 'Unknown error',
          elapsed,
        }
      }
    } catch (error) {
      const elapsed = (Date.now() - startTime) / 1000

      if (error instanceof Error && error.name === 'AbortError') {
        return { model, success: false, error: 'Cancelled', elapsed }
      }

      return {
        model,
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        elapsed,
      }
    }
  }

  /**
   * Generate diagram from all 3 LLMs in parallel
   */
  async function autoComplete(
    options: {
      modelsToRun?: string[]
      onFirstResult?: (model: string) => void
      onAllComplete?: (successCount: number, totalCount: number) => void
      onSuccess?: () => void
      onError?: (error: string) => void
      /** Append to prompt (e.g. ' 半成品' for learning sheet mode) */
      promptSuffix?: string
    } = {}
  ): Promise<{ success: boolean; error?: string }> {
    const { modelsToRun = [...LLM_MODELS], onFirstResult, onAllComplete, promptSuffix } = options

    // Validate
    const validation = validateForAutoComplete()
    if (!validation.valid) {
      options.onError?.(validation.error || 'Validation failed')
      return { success: false, error: validation.error }
    }

    // Build simple request - backend handles prompt construction
    const language = isZh.value ? 'zh' : 'en'
    const topic = (extractMainTopic() || '') + (promptSuffix ?? '')

    const requestBody: Record<string, unknown> = {
      prompt: topic,
      diagram_type: diagramStore.type,
      language,
      request_type: 'autocomplete',
    }

    // Add bridge map specific data
    if (diagramStore.type === 'bridge_map') {
      const analogies = extractBridgeMapAnalogies()
      if (analogies.length > 0) {
        requestBody.existing_analogies = analogies
      }
    }

    // Add dimension if specified
    const dimension = extractFixedDimension()
    if (dimension) {
      requestBody.fixed_dimension = dimension

      if (!topic && (diagramStore.type === 'tree_map' || diagramStore.type === 'brace_map')) {
        requestBody.dimension_only_mode = true
      }
    }

    // Generate session ID
    const newSessionId = `gen_${Date.now()}`

    // Normalize diagram type
    let diagramType = diagramStore.type || 'mindmap'
    if (diagramType === 'mind_map') {
      diagramType = 'mindmap'
    }

    // Start generation
    llmResultsStore.startGeneration(newSessionId, diagramType, modelsToRun)

    eventBus.emit('llm:generation_started', {
      models: modelsToRun,
      diagramType,
      mainTopic: topic,
      language,
    })

    console.log(`[AutoComplete] Starting parallel generation with ${modelsToRun.length} models`)

    try {
      const abortControllers = modelsToRun.map(() => new AbortController())
      abortControllers.forEach((controller) => llmResultsStore.addAbortController(controller))

      const promises = modelsToRun.map((model, index) =>
        generateFromSingleLLM(requestBody, model, abortControllers[index].signal)
      )

      let firstResultHandled = false
      const results = await Promise.allSettled(promises)

      for (const [index, settledResult] of results.entries()) {
        const model = modelsToRun[index]

        if (settledResult.status === 'fulfilled') {
          const result = settledResult.value

          if (result.success && result.spec) {
            const rendered = await llmResultsStore.handleModelSuccess(
              model,
              result.spec,
              result.diagramType || diagramType,
              result.elapsed
            )

            if (rendered && !firstResultHandled) {
              firstResultHandled = true
              onFirstResult?.(model)
              options.onSuccess?.()

              eventBus.emit('llm:first_result_available', {
                model,
                elapsedTime: result.elapsed,
              })

              console.log(
                `[AutoComplete] First result from ${model} rendered (${result.elapsed.toFixed(2)}s)`
              )
            }
          } else {
            llmResultsStore.handleModelError(model, result.error || 'Unknown error', result.elapsed)
            console.warn(`[AutoComplete] ${model} failed: ${result.error}`)
          }
        } else {
          llmResultsStore.handleModelError(
            model,
            settledResult.reason?.message || 'Request failed',
            0
          )
          console.warn(`[AutoComplete] ${model} rejected: ${settledResult.reason}`)
        }

        llmResultsStore.removeAbortController(abortControllers[index])
      }

      llmResultsStore.completeGeneration()

      const successCount = llmResultsStore.successCount
      const totalCount = modelsToRun.length

      console.log(`[AutoComplete] Completed: ${successCount}/${totalCount} successful`)

      eventBus.emit('llm:generation_completed', {
        successCount,
        totalCount,
        allFailed: successCount === 0,
      })

      onAllComplete?.(successCount, totalCount)

      if (successCount === 0) {
        const errorMsg = isZh.value ? '生成失败，请重试' : 'Generation failed, please try again'
        notify.error(errorMsg)
        options.onError?.(errorMsg)
        return { success: false, error: 'All models failed' }
      } else {
        const msg = isZh.value
          ? `${successCount}/${totalCount} 个模型就绪`
          : `${successCount}/${totalCount} models ready`
        notify.success(msg)
        return { success: true }
      }
    } catch (error) {
      console.error('[AutoComplete] Unexpected error:', error)
      llmResultsStore.completeGeneration()

      const errorMessage = error instanceof Error ? error.message : 'Generation failed'
      notify.error(errorMessage)
      options.onError?.(errorMessage)

      eventBus.emit('llm:generation_failed', { error: errorMessage })

      return { success: false, error: errorMessage }
    }
  }

  /**
   * Switch to a different model's cached result
   * Saves current diagram (including learning sheet state) before replacing
   */
  async function switchToModel(model: string): Promise<boolean> {
    const switched = await llmResultsStore.switchToModel(model)
    if (switched) {
      eventBus.emit('llm:result_rendered', {
        model,
        diagramType: diagramStore.type,
        nodeCount: diagramStore.nodeCount,
      })
    }
    return switched
  }

  /**
   * Cancel all active generation requests
   */
  function cancelGeneration(): void {
    llmResultsStore.cancelAllRequests()
    notify.info(isZh.value ? '已取消生成' : 'Generation cancelled')
  }

  return {
    // State
    isGenerating,
    selectedModel,
    modelStates,
    hasAnyResults,
    readyModels,

    // Methods
    extractMainTopic,
    validateForAutoComplete,
    autoComplete,
    switchToModel,
    cancelGeneration,

    // Utilities
    isPlaceholderText,
  }
}
