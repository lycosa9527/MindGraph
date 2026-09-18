import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const vuePath = join(
  dirname(fileURLToPath(import.meta.url)),
  '../src/components/admin/AdminDatabaseTab.vue',
)

describe('admin database merge actions', () => {
  it('places clear-orphans immediately before merge into live DB', () => {
    const src = readFileSync(vuePath, 'utf8')
    const clearAt = src.indexOf("t('admin.database.pgClearOrphans')")
    const mergeAt = src.indexOf("t('admin.database.pgExecuteMerge')")
    expect(clearAt).toBeGreaterThan(-1)
    expect(mergeAt).toBeGreaterThan(clearAt)
  })
})
