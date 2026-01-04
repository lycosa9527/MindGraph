/**
 * Chat Store - Pinia store for MindMate chat state
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

export interface ChatMessage {
  id: string
  text: string
  sender: 'user' | 'ai'
  timestamp: Date
  isTyping?: boolean
}

// Mock AI responses for different keywords
const MOCK_RESPONSES: Record<string, string[]> = {
  平行四边形: [
    '在《平行四边形》的教学中，可以设计以下认知冲突：\n1. 让学生判断"一组对边平行的四边形是平行四边形"是否正确，引发对定义的深入理解\n2. 呈现一个看起来像平行四边形但实际不是的图形，挑战学生的视觉判断\n3. 讨论"平行四边形是否一定是轴对称图形"，打破常见误解',
  ],
  教学设计: [
    '《呼吸作用》教学设计方案：\n【教学目标】\n- 理解呼吸作用的概念和实质\n- 掌握呼吸作用的反应式和过程\n- 了解呼吸作用在生产生活中的应用\n\n【教学重点】呼吸作用的过程和意义\n【教学难点】呼吸作用与光合作用的区别和联系\n\n需要更详细的教学过程设计吗？',
  ],
  万有引力: [
    '学生在学习万有引力时常出现的迷思概念：\n1. 认为只有地球对物体有引力，忽视了物体间的相互吸引\n2. 混淆重力和万有引力的概念\n3. 认为宇航员在太空中不受重力\n4. 难以理解为什么月球不会掉下来\n5. 误认为质量越大的物体下落速度越快',
  ],
  小组合作学习: [
    '设计有效小组合作学习课的策略：\n1. 合理分组：考虑学生的学习水平、性格特点和多元智能\n2. 明确角色：分配组长、记录员、汇报员等不同角色\n3. 任务驱动：设计结构化、有挑战性的学习任务\n4. 规则引导：建立小组合作的基本规则和评价标准\n5. 教师支持：在合作过程中提供适时的指导和反馈',
  ],
}

// Default suggestion prompts
export const SUGGESTION_PROMPTS = [
  '《平行四边形》这节课可以设计哪些认知冲突？',
  '请帮我生成《呼吸作用》的教学设计。',
  '学生在万有引力这个知识点上存在哪些迷思概念？',
  '如何设计一堂有效的小组合作学习课？',
  '怎样提升学生的科学探究能力？',
  '小学语文阅读教学有哪些创新方法？',
  '数学概念教学中如何联系生活实际？',
  '如何培养学生的批判性思维能力？',
  '英语听力教学的有效策略有哪些？',
  '历史课堂中如何进行情境教学？',
  '物理实验教学中应注意哪些安全问题？',
  '如何设计符合学生认知水平的作业？',
]

export const useChatStore = defineStore('chat', () => {
  // State
  const messages = ref<ChatMessage[]>([])
  const isAiTyping = ref(false)
  const copiedMessageId = ref<string | null>(null)
  const inputValue = ref('')

  // Getters
  const hasMessages = computed(() => messages.value.length > 0)
  const lastMessage = computed(() =>
    messages.value.length > 0 ? messages.value[messages.value.length - 1] : null
  )

  // Actions
  function getMockAiResponse(userMessage: string): string {
    for (const keyword in MOCK_RESPONSES) {
      if (userMessage.includes(keyword)) {
        const responses = MOCK_RESPONSES[keyword]
        return responses[Math.floor(Math.random() * responses.length)]
      }
    }
    return '感谢你的提问！我需要思考一下如何更好地回答你...\n\n这是一个很好的问题。根据教学理论和实践经验，我可以为你提供一些建议。如果你能提供更多细节，我可以给出更有针对性的回答。'
  }

  function addUserMessage(text: string): ChatMessage {
    const message: ChatMessage = {
      id: `msg-${Date.now()}-user`,
      text,
      sender: 'user',
      timestamp: new Date(),
    }
    messages.value.push(message)
    return message
  }

  function addAiMessage(text: string): ChatMessage {
    const message: ChatMessage = {
      id: `msg-${Date.now()}-ai`,
      text,
      sender: 'ai',
      timestamp: new Date(),
    }
    messages.value.push(message)
    return message
  }

  async function sendMessage(text: string): Promise<void> {
    if (!text.trim() || isAiTyping.value) return

    addUserMessage(text)
    inputValue.value = ''
    isAiTyping.value = true

    // Simulate AI thinking time
    await new Promise((resolve) => setTimeout(resolve, 1500 + Math.random() * 1000))

    const response = getMockAiResponse(text)
    addAiMessage(response)
    isAiTyping.value = false
  }

  function copyMessage(messageId: string): void {
    const message = messages.value.find((m) => m.id === messageId)
    if (message) {
      navigator.clipboard.writeText(message.text)
      copiedMessageId.value = messageId
      setTimeout(() => {
        copiedMessageId.value = null
      }, 2000)
    }
  }

  function setInputValue(value: string): void {
    inputValue.value = value
  }

  function clearMessages(): void {
    messages.value = []
  }

  function formatTime(date: Date): string {
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return {
    // State
    messages,
    isAiTyping,
    copiedMessageId,
    inputValue,

    // Getters
    hasMessages,
    lastMessage,

    // Actions
    addUserMessage,
    addAiMessage,
    sendMessage,
    copyMessage,
    setInputValue,
    clearMessages,
    formatTime,
  }
})
