import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const srcPath = resolve(dirname(fileURLToPath(import.meta.url)), '../src/utils/renderPdfPreview.ts')

describe('renderPdfPreview', () => {
  it('loads pdfjs-dist only when a PDF is rendered', () => {
    const src = readFileSync(srcPath, 'utf8')
    expect(src).not.toMatch(/import\s+\{[^}]*\}\s+from\s+['"]pdfjs-dist['"]/)
    expect(src).toMatch(/import\(\s*['"]pdfjs-dist['"]\s*\)/)
  })
})
