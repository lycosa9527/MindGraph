import { defineConfig, Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve, dirname, join } from 'path'
import { readFileSync, copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from 'fs'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

// Helper function to recursively copy directory
function copyDir(src: string, dest: string): void {
  if (!existsSync(src)) {
    return
  }
  
  mkdirSync(dest, { recursive: true })
  
  const entries = readdirSync(src, { withFileTypes: true })
  
  for (const entry of entries) {
    const srcPath = join(src, entry.name)
    const destPath = join(dest, entry.name)
    
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath)
    } else {
      copyFileSync(srcPath, destPath)
    }
  }
}

// Plugin to copy PDF.js worker to public/pdfjs/ folder (served via StaticFiles mount)
function copyPdfjsWorker(): Plugin {
  return {
    name: 'copy-pdfjs-worker',
    buildStart() {
      // Copy to public/pdfjs/ for dev server
      const possiblePaths = [
        resolve(__dirname, 'node_modules/pdfjs-dist/build/pdf.worker.min.mjs'),
        resolve(__dirname, 'node_modules/pdfjs-dist/build/pdf.worker.min.js'),
      ]
      const pdfjsDir = resolve(__dirname, 'public/pdfjs')
      const publicDest = resolve(pdfjsDir, 'pdf.worker.min.js')

      // Create pdfjs directory if it doesn't exist
      if (!existsSync(pdfjsDir)) {
        mkdirSync(pdfjsDir, { recursive: true })
      }

      for (const src of possiblePaths) {
        if (existsSync(src)) {
          try {
            copyFileSync(src, publicDest)
            console.log(`[Vite] Copied PDF.js worker to public/pdfjs/: ${src}`)
            break
          } catch (error) {
            console.warn(`[Vite] Failed to copy PDF.js worker to public/pdfjs/:`, error)
          }
        }
      }
    },
    writeBundle() {
      // Vite automatically copies public/pdfjs/ → dist/pdfjs/ during build
      // Just verify it exists (don't copy again - rely on Vite's automatic copying)
      const distDest = resolve(__dirname, 'dist/pdfjs/pdf.worker.min.js')
      const publicDest = resolve(__dirname, 'public/pdfjs/pdf.worker.min.js')

      // Verify the file was copied by Vite
      if (!existsSync(distDest)) {
        console.error('[Vite] ❌ ERROR: PDF.js worker file not found in dist/pdfjs/ after build!')
        console.error(`[Vite] Expected location: ${distDest}`)
        console.error(`[Vite] Source should be: ${publicDest}`)
        console.error('[Vite] Vite should have automatically copied it from public/pdfjs/')
        console.error('[Vite] This will cause 404 errors in production.')
        throw new Error('PDF.js worker file missing in dist/pdfjs/ directory')
      }

      // Verify file is not empty
      const stats = statSync(distDest)
      if (stats.size === 0) {
        console.error('[Vite] ❌ ERROR: PDF.js worker file is empty!')
        console.error(`[Vite] File location: ${distDest}`)
        throw new Error('PDF.js worker file is empty')
      }

      // Verify file size is reasonable (should be > 100KB for minified worker)
      if (stats.size < 100 * 1024) {
        console.warn(`[Vite] ⚠ WARNING: PDF.js worker file seems too small (${(stats.size / 1024).toFixed(1)}KB)`)
        console.warn(`[Vite] Expected size: > 100KB. File location: ${distDest}`)
      } else {
        console.log(`[Vite] ✓ Verified PDF.js worker file: ${(stats.size / 1024).toFixed(1)}KB at ${distDest}`)
      }
    },
  }
}

// Plugin to copy PDF.js cmaps to public folder
function copyPdfjsCmaps(): Plugin {
  return {
    name: 'copy-pdfjs-cmaps',
    buildStart() {
      const srcDir = resolve(__dirname, 'node_modules/pdfjs-dist/cmaps')
      const destDir = resolve(__dirname, 'public/cmaps')
      
      if (existsSync(srcDir)) {
        try {
          copyDir(srcDir, destDir)
          console.log(`[Vite] Copied PDF.js cmaps from ${srcDir} to ${destDir}`)
        } catch (error) {
          console.warn(`[Vite] Failed to copy PDF.js cmaps:`, error)
        }
      } else {
        console.warn('[Vite] PDF.js cmaps directory not found in node_modules')
      }
    },
  }
}

// Read version from VERSION file (single source of truth)
const version = readFileSync(resolve(__dirname, '../VERSION'), 'utf-8').trim()

// Get backend host from environment variable (for WSL/remote scenarios)
// Default to localhost for normal development
// For WSL: Use Windows host IP (e.g., VITE_BACKEND_HOST=http://172.x.x.x:9527)
const backendHost = process.env.VITE_BACKEND_HOST || 'http://localhost:9527'
const backendHostWs = backendHost.replace('http://', 'ws://').replace('https://', 'wss://')

export default defineConfig({
  plugins: [vue(), tailwindcss(), copyPdfjsWorker(), copyPdfjsCmaps()],
  define: {
    __APP_VERSION__: JSON.stringify(version),
    __BUILD_TIME__: JSON.stringify(Date.now()),
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173, // Use Vite's default port 5173 to avoid conflicts
    host: process.env.VITE_HOST || '127.0.0.1', // Default to 127.0.0.1 (IPv4) to avoid IPv6 permission issues in WSL; set VITE_HOST=0.0.0.0 for WSL/remote access
    strictPort: false, // Allow Vite to use another port if 5173 is taken
    proxy: {
      '/api': {
        target: backendHost,
        changeOrigin: true,
      },
      '/ws': {
        target: backendHostWs,
        ws: true,
      },
      '/static': {
        target: backendHost,
        changeOrigin: true,
      },
      '/health': {
        target: backendHost,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    // Element Plus is ~1MB (expected for a full UI framework)
    // Suppress warning since we've already split vendors optimally
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        // Split vendor libraries into separate chunks for better caching
        manualChunks: {
          // Vue core libraries
          'vendor-vue': ['vue', 'vue-router', 'pinia'],
          // UI framework (largest dependency)
          'vendor-element-plus': ['element-plus', '@element-plus/icons-vue'],
          // VueFlow (diagram visualization)
          'vendor-vueflow': [
            '@vue-flow/core',
            '@vue-flow/background',
            '@vue-flow/controls',
            '@vue-flow/minimap',
          ],
          // Utilities
          'vendor-utils': ['axios', '@vueuse/core', 'mitt', 'dompurify', 'markdown-it'],
        },
      },
    },
  },
})
