import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  COMMON_MINDMATE_VIEWPORTS,
  mindmateStageSize,
  sidebarAccountFits,
  welcomeClusterHeight,
  welcomeComposerWidth,
  welcomeFitsViewport,
} from '@/utils/mindmateWelcomeLayoutBudget'

const here = dirname(fileURLToPath(import.meta.url))
const welcomeLayoutCss = readFileSync(
  join(here, '../src/components/panels/mindmate/mindmate-welcome-layout.css'),
  'utf8'
)
const mindmateCss = readFileSync(
  join(here, '../src/components/panels/mindmate/mindmate.css'),
  'utf8'
)
const mainLayoutVue = readFileSync(join(here, '../src/layouts/MainLayout.vue'), 'utf8')
const sidebarVue = readFileSync(join(here, '../src/components/sidebar/AppSidebar.vue'), 'utf8')
const footerVue = readFileSync(
  join(here, '../src/components/sidebar/AppSidebarAccountFooter.vue'),
  'utf8'
)
const suggestionBubblesVue = readFileSync(
  join(here, '../src/components/common/SuggestionBubbles.vue'),
  'utf8'
)

describe('mindmate welcome layout', () => {
  it('centers the welcome cluster without size containment', () => {
    expect(welcomeLayoutCss).toContain('.mindmate-stage--welcome')
    expect(welcomeLayoutCss).toContain('container-type: inline-size')
    expect(welcomeLayoutCss).not.toContain('container-type: size')
    expect(welcomeLayoutCss).toContain('--mm-avatar: clamp(')
    expect(welcomeLayoutCss).toContain('12dvh')
    expect(welcomeLayoutCss).toContain('.mindmate-stage--welcome::before')
    expect(welcomeLayoutCss).toContain('.mindmate-stage--welcome::after')
  })

  it('does not pin the fullpage welcome block with fixed 140px / 50vh offsets', () => {
    expect(mindmateCss).not.toMatch(/welcome-fullpage[\s\S]{0,200}min-height:\s*50vh/)
    expect(mindmateCss).not.toMatch(/welcome-fullpage[\s\S]{0,200}padding:\s*140px/)
    expect(mindmateCss).not.toContain('margin-top: 50px')
    expect(mindmateCss).not.toContain('padding-bottom: 64px')
  })

  it('lets the composer fill the stage so tablet chips are not clipped to 320px', () => {
    expect(welcomeLayoutCss).toContain('--mm-composer-max: min(48rem, 100%)')
    expect(welcomeLayoutCss).not.toMatch(/--mm-composer-max:\s*clamp\([^)]*cqi/)
    expect(welcomeLayoutCss).toContain('min-width: 0')
    expect(welcomeLayoutCss).toContain('--mm-suggest-max-h: clamp(108px')
    expect(welcomeLayoutCss).not.toContain('--mm-suggest-max-h: 72px')
  })

  it('wraps suggestion chips inside the composer instead of centering nowrap overflow', () => {
    expect(suggestionBubblesVue).toContain('max-width: 100%')
    expect(suggestionBubblesVue).toContain('white-space: normal')
    expect(suggestionBubblesVue).toContain('justify-content: safe center')
    expect(suggestionBubblesVue).not.toContain('white-space: nowrap')
  })

  it('locks the main shell and pins the sidebar account row to the visible viewport', () => {
    expect(mainLayoutVue).toContain('html:has(.main-layout)')
    expect(mainLayoutVue).toContain('height: 100dvh')
    expect(mainLayoutVue).toContain('max-height: 100dvh')
    expect(mainLayoutVue).toContain('safe-area-inset-bottom')
    expect(sidebarVue).toContain('min-h-0')
    expect(footerVue).toContain('sidebar-account-footer')
    expect(footerVue).toContain('flex-shrink: 0')
  })
})

describe('mindmate layout budget across common resolutions', () => {
  it.each(COMMON_MINDMATE_VIEWPORTS)(
    '$name ($width×$height) keeps welcome cluster, composer, and account row on screen',
    ({ width, height }) => {
      const { stageWidth, stageHeight } = mindmateStageSize(width, height)
      const cluster = welcomeClusterHeight(height, stageHeight)
      const composer = welcomeComposerWidth(stageWidth)

      expect(stageHeight).toBeGreaterThan(0)
      expect(cluster).toBeLessThanOrEqual(stageHeight)
      expect(composer + 24).toBeLessThanOrEqual(stageWidth)
      expect(sidebarAccountFits(height)).toBe(true)
      expect(welcomeFitsViewport(width, height)).toBe(true)
    }
  )

  it('uses most of the iPad landscape stage for the composer', () => {
    const { stageWidth } = mindmateStageSize(1024, 768)
    const composer = welcomeComposerWidth(stageWidth)
    expect(composer).toBeGreaterThanOrEqual(600)
    expect(composer / stageWidth).toBeGreaterThan(0.7)
  })
})
