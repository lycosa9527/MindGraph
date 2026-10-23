import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function readSrc(rel: string): string {
  return readFileSync(resolve(root, rel), 'utf8')
}

describe('quick registration school picker', () => {
  it('filters schools by typing, like the school dashboard select', () => {
    const modal = readSrc('src/components/mindgraph/QuickRegisterModal.vue')
    expect(modal).toContain('class="quick-reg-org-select"')
    expect(modal).toContain('filterable')
    expect(modal).toContain('v-model="selectedOrgId"')
    expect(modal).toContain(':label="o.display_name || o.name"')
    expect(modal).not.toContain('onAdminOrgDropdownCommand')
    expect(modal).toContain('watch(selectedOrgId')
  })
})
