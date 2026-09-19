import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { CLASSROOM_REMOTE_TABS } from '@/canvas-ribbon/mindMapClassroomRemoteTypes'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function readSrc(rel: string): string {
  return readFileSync(resolve(root, rel), 'utf8')
}

describe('mind map classroom remote', () => {
  it('adds a tabbed floating remote beside the status-bar zoom cluster', () => {
    const remote = readSrc('src/canvas-ribbon/MindMapClassroomRemote.vue')
    const page = readSrc('src/pages/CanvasPage.vue')
    const status = readSrc('src/canvas-ribbon/MindMapStatusBar.vue')
    expect(page).toContain('<MindMapClassroomRemote')
    expect(page).toContain(':hand-tool-active="handToolActive"')
    expect(remote).toContain('data-testid="mindmap-classroom-remote"')
    expect(remote).toContain("'mindmap-classroom-remote-hand-tool'")
    expect(remote).toContain("'mindmap-classroom-remote-zoom-out'")
    expect(remote).toContain("'mindmap-classroom-remote-fit-view'")
    expect(remote).toContain('mindmap-classroom-remote-tab-')
    expect(remote).toContain('useClassroomRemotePosition')
    expect(status).toContain('mindmap-ribbon-floating-toolbar')
    expect(status).toContain('toggleClassroomRemote')
    expect(page).toContain('!classroomRemoteHidden')
    expect(status).toContain('mindmap-ribbon-zoom-out')
    expect([...CLASSROOM_REMOTE_TABS]).toEqual(['view', 'edit', 'teaching', 'topics', 'ai', 'file'])
    expect(remote).toContain("position.activeTab.value === 'topics'")
    expect(remote).not.toContain('showTopicsAiPair')
    expect(remote).not.toContain('mm-remote--pair')
    expect(remote).not.toContain('onToggleCollapsed')
    expect(remote).not.toContain('is-collapsed')
    expect(remote).not.toContain('classroomRemote.collapse')
    expect(remote).toContain('mindmap-classroom-remote-close')
    expect(remote).toContain('onClose')
    expect(readSrc('src/canvas-ribbon/mindMapClassroomRemote.css')).toContain(
      'grid-template-columns: repeat(3, auto)'
    )
  })

  it('keeps usual classroom tools on the remote tabs', () => {
    const remote = readSrc('src/canvas-ribbon/MindMapClassroomRemote.vue')
    expect(remote).toContain('canvas.toolbar.addChildNode')
    expect(remote).toContain('<MindMapClassroomRemoteTopics')
    expect(remote).toContain('canvas.ribbon.topicGenerate')
    expect(readSrc('src/canvas-ribbon/MindMapClassroomRemoteTopics.vue')).toContain(
      'applyClassroomRemoteTopic'
    )
    expect(remote).toContain('canvas.mindMapSideToolbar.learningSheet')
    expect(remote).toContain('canvas.mindMapSideToolbar.mindClassroom')
    expect(remote).toContain('common.save')
    expect(remote).toContain('canvas.zoomControls.hand')
  })
})
