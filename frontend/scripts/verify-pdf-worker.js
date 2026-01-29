#!/usr/bin/env node
/**
 * Verification script for PDF.js worker file
 * Checks that the worker file exists and is valid in both public/ and dist/
 * Can be run independently or as part of CI/CD pipeline
 */

import { existsSync, statSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const projectRoot = resolve(__dirname, '..')

const publicPath = resolve(projectRoot, 'public/pdfjs/pdf.worker.min.js')
const distPath = resolve(projectRoot, 'dist/pdfjs/pdf.worker.min.js')

let hasErrors = false
let hasWarnings = false

console.log('[Verify] Checking PDF.js worker file...\n')

// Check public/ directory (for dev server)
console.log(`[Verify] Checking public/: ${publicPath}`)
if (existsSync(publicPath)) {
  const stats = statSync(publicPath)
  if (stats.size === 0) {
    console.error('  ❌ ERROR: File exists but is empty!')
    hasErrors = true
  } else if (stats.size < 100 * 1024) {
    console.warn(`  ⚠ WARNING: File seems too small (${(stats.size / 1024).toFixed(1)}KB)`)
    hasWarnings = true
  } else {
    console.log(`  ✓ Found: ${(stats.size / 1024).toFixed(1)}KB`)
  }
} else {
  console.warn('  ⚠ WARNING: File not found in public/')
  console.warn('  This will cause issues in dev mode')
  hasWarnings = true
}

// Check dist/ directory (for production)
console.log(`\n[Verify] Checking dist/: ${distPath}`)
if (existsSync(distPath)) {
  const stats = statSync(distPath)
  if (stats.size === 0) {
    console.error('  ❌ ERROR: File exists but is empty!')
    hasErrors = true
  } else if (stats.size < 100 * 1024) {
    console.warn(`  ⚠ WARNING: File seems too small (${(stats.size / 1024).toFixed(1)}KB)`)
    hasWarnings = true
  } else {
    console.log(`  ✓ Found: ${(stats.size / 1024).toFixed(1)}KB`)
  }
} else {
  console.error('  ❌ ERROR: File not found in dist/')
  console.error('  This will cause 404 errors in production!')
  console.error('  Run: npm run build')
  hasErrors = true
}

// Summary
console.log('\n' + '='.repeat(60))
if (hasErrors) {
  console.error('[Verify] ❌ VERIFICATION FAILED')
  console.error('[Verify] Please fix the errors above before deploying.')
  process.exit(1)
} else if (hasWarnings) {
  console.warn('[Verify] ⚠ VERIFICATION COMPLETED WITH WARNINGS')
  console.warn('[Verify] Please review the warnings above.')
  process.exit(0)
} else {
  console.log('[Verify] ✓ VERIFICATION PASSED')
  console.log('[Verify] PDF.js worker file is ready for deployment.')
  process.exit(0)
}
