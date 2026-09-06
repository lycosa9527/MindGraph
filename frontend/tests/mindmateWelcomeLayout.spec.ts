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
})
