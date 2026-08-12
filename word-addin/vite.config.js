import { existsSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join, resolve } from 'node:path'
import { defineConfig } from 'vite'

const root = resolve(import.meta.dirname ?? resolve('.'))

async function loadOfficeDevHttps() {
  const certDir = join(homedir(), '.office-addin-dev-certs')
  const keyPath = join(certDir, 'localhost.key')
  const certPath = join(certDir, 'localhost.crt')
  const caPath = join(certDir, 'ca.crt')

  if (existsSync(keyPath) && existsSync(certPath)) {
    return {
      key: readFileSync(keyPath),
      cert: readFileSync(certPath),
      ca: existsSync(caPath) ? readFileSync(caPath) : undefined,
    }
  }

  // Generates cert files and installs the CA (needs an interactive Windows/Mac shell).
  const { getHttpsServerOptions } = await import('office-addin-dev-certs')
  return getHttpsServerOptions()
}

export default defineConfig(async () => {
  // Same certs as `npm run signin` — Word blocks Vite's default self-signed cert.
  let https
  try {
    https = await loadOfficeDevHttps()
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    throw new Error(
      `${message}\n\nRun this once on Windows (accept the CA prompt):\n  npm run signin\nThen restart: npm run dev`
    )
  }

  return {
    root,
    server: {
      port: 3000,
      strictPort: true,
      https,
      headers: {
        'Access-Control-Allow-Origin': '*',
      },
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true,
      rollupOptions: {
        input: {
          commands: resolve(root, 'src/commands/commands.html'),
          mindmate: resolve(root, 'src/taskpane/mindmate.html'),
          mindgraph: resolve(root, 'src/taskpane/mindgraph.html'),
          voice: resolve(root, 'src/taskpane/voice.html'),
          showcase: resolve(root, 'src/taskpane/showcase.html'),
          manual: resolve(root, 'src/taskpane/manual.html'),
          settings: resolve(root, 'src/taskpane/settings.html'),
        },
      },
    },
  }
})
