import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

/**
 * Minimal Vitest config for unit-testing pure helpers & composable logic.
 *
 * Kept separate from ``vite.config.ts`` so the dev/build pipeline isn't
 * affected.  Install dev deps with:
 *
 *   npm install -D vitest @vue/test-utils jsdom
 *
 * Then run: ``npx vitest run`` or ``npx vitest --watch``.
 */
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@data': resolve(__dirname, '../data'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: false,
    include: ['tests/**/*.spec.ts'],
    clearMocks: true,
    restoreMocks: true,
  },
})
