import vue from '@vitejs/plugin-vue'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'
import { defineConfig } from 'vitest/config'

const __dirname = dirname(fileURLToPath(import.meta.url))

const sharedPlugins = [vue()]
const sharedDefine = {
  __APP_VERSION__: JSON.stringify('test'),
}
const sharedResolve = {
  alias: {
    '@': resolve(__dirname, 'src'),
    '@data': resolve(__dirname, '../data'),
  },
}
const sharedTestOptions = {
  environment: 'jsdom' as const,
  globals: false,
  clearMocks: true,
  restoreMocks: true,
}

/**
 * Minimal Vitest config for unit-testing pure helpers & composable logic.
 *
 * Kept separate from ``vite.config.ts`` so the dev/build pipeline isn't
 * affected.  Install dev deps with:
 *
 *   npm install -D vitest @vue/test-utils jsdom
 *
 * Then run: ``npx vitest run`` or ``npx vitest --watch``.
 *
 * Interop smoke tests run in a dedicated project with a higher timeout because
 * cold dynamic imports of large ESM trees (Element Plus) can exceed 20s on
 * /mnt/c when Vitest loads many files in parallel.
 */
export default defineConfig({
  plugins: sharedPlugins,
  define: sharedDefine,
  resolve: sharedResolve,
  test: {
    projects: [
      {
        extends: true,
        test: {
          ...sharedTestOptions,
          name: 'unit',
          include: ['tests/**/*.spec.ts'],
          exclude: ['tests/vite8ModuleInterop.spec.ts'],
        },
      },
      {
        extends: true,
        test: {
          ...sharedTestOptions,
          name: 'vite8-interop',
          include: ['tests/vite8ModuleInterop.spec.ts'],
          testTimeout: 60_000,
        },
      },
    ],
  },
})
