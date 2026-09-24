import { describe, expect, it } from 'vitest'

import {
  cancelSwissGlassPrompt,
  getSwissGlassPromptState,
  swissGlassPrompt,
  trySettleSwissGlassPrompt,
} from '@/composables/common/useSwissGlassPrompt'
import { promptArchiveFolderName } from '@/composables/sidebar/promptSwissGlassName'

describe('swissGlassPrompt', () => {
  it('resolves the trimmed name and rejects a cancel', async () => {
    const pending = swissGlassPrompt('请输入文件夹名称', '新建文件夹', {
      inputValue: '  课堂  ',
      inputPattern: /\S+/,
      inputErrorMessage: '名称不能为空',
      inputMaxLength: 100,
    })
    expect(getSwissGlassPromptState().open).toBe(true)
    expect(trySettleSwissGlassPrompt('   ')).toBe('名称不能为空')
    expect(getSwissGlassPromptState().open).toBe(true)
    expect(trySettleSwissGlassPrompt('  课堂  ')).toBe('')
    await expect(pending).resolves.toBe('课堂')

    const cancelled = swissGlassPrompt('请输入文件夹名称', '新建文件夹')
    cancelSwissGlassPrompt()
    await expect(cancelled).rejects.toBe('cancel')
    expect(getSwissGlassPromptState().open).toBe(false)
  })

  it('returns null when the folder prompt is dismissed', async () => {
    const pending = promptArchiveFolderName(
      (key) => key,
      'sidebar.diagramHistory.folderCreateTitle',
      'sidebar.diagramHistory.folderCreatePrompt',
      'sidebar.diagramHistory.foldersSection'
    )
    cancelSwissGlassPrompt()
    await expect(pending).resolves.toBeNull()
  })
})
