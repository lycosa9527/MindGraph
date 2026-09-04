import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it } from 'vitest'

import { useFeatureFlagsStore } from '@/stores/featureFlags'
import {
  effectiveMindMapCanvasMode,
  isMindMapV2FamilyMode,
  layoutMindMapCanvasMode,
  readShowcaseMindMapCanvasMode,
} from '@/utils/mindMapCanvasMode'

describe('mind map canvas V3 mode helpers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('treats v2 and v3 as the same layout family', () => {
    expect(isMindMapV2FamilyMode('v2')).toBe(true)
    expect(isMindMapV2FamilyMode('v3')).toBe(true)
    expect(isMindMapV2FamilyMode('legacy')).toBe(false)
    expect(layoutMindMapCanvasMode('v3')).toBe('v2')
    expect(layoutMindMapCanvasMode('legacy')).toBe('legacy')
  })

  it('clamps v3 to v2 when the V3 flag is off (does not persist here)', () => {
    expect(effectiveMindMapCanvasMode('v3', true, false)).toBe('v2')
    expect(effectiveMindMapCanvasMode('v2', true, false)).toBe('v2')
    expect(effectiveMindMapCanvasMode('legacy', true, false)).toBe('legacy')
  })

  it('clamps v3 and v2 to classic when the V2 flag is off', () => {
    expect(effectiveMindMapCanvasMode('v3', false, true)).toBe('legacy')
    expect(effectiveMindMapCanvasMode('v2', false, true)).toBe('legacy')
  })

  it('keeps showcase on v2 when the v2 flag is on', () => {
    const flagsStore = useFeatureFlagsStore()
    flagsStore.flags = {
      external_base_url: '',
      feature_rag_chunk_test: false,
      feature_course: false,
      feature_mate_learning: false,
      feature_template: false,
      feature_community: false,
      feature_showcase: false,
      feature_zhihui: false,
      feature_askonce: false,
      feature_debateverse: false,
      feature_knowledge_space: false,
      feature_mindmap_v2_canvas: true,
      feature_mindmap_v3_canvas: true,
      feature_library: false,
      feature_gewe: false,
      feature_smart_response: false,
      feature_teacher_usage: false,
      feature_workshop_chat: false,
      feature_mindmate_collab: false,
      feature_markets: false,
      feature_mindbot: false,
      feature_mindmate_export: false,
      feature_kitty_agent: false,
      feature_auth_pixel_battle: false,
      feature_test_server_banner: false,
      feature_wechat_login: false,
      feature_dingtalk_login: false,
      feature_word_addin: false,
      feature_thinking_coins: false,
      workshop_chat_preview_org_ids: [],
      feature_org_access: {},
    }
    expect(readShowcaseMindMapCanvasMode()).toBe('v2')
    flagsStore.flags.feature_mindmap_v2_canvas = false
    expect(readShowcaseMindMapCanvasMode()).toBe('legacy')
  })
})
