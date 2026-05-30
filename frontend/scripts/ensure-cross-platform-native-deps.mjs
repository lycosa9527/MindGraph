/**
 * WSL and Windows often share frontend/node_modules on /mnt/c. npm only installs
 * optional native bindings for the current OS, so a later install from the other
 * side removes the binding the build needs. Install Linux + Windows bindings when
 * either is missing.
 */
import { execSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')

const PLATFORM_OPTIONALS = [
  { parent: 'rolldown', optional: '@rolldown/binding-linux-x64-gnu' },
  { parent: 'rolldown', optional: '@rolldown/binding-win32-x64-msvc' },
  { parent: 'lightningcss', optional: 'lightningcss-linux-x64-gnu' },
  { parent: 'lightningcss', optional: 'lightningcss-win32-x64-msvc' },
  { parent: '@tailwindcss/oxide', optional: '@tailwindcss/oxide-linux-x64-gnu' },
  { parent: '@tailwindcss/oxide', optional: '@tailwindcss/oxide-win32-x64-msvc' },
]

function packageDir(name) {
  if (name.startsWith('@')) {
    const slash = name.indexOf('/', 1)
    return join(root, 'node_modules', name.slice(0, slash), name.slice(slash + 1))
  }
  return join(root, 'node_modules', name)
}

function readOptionalVersion(parentName, optionalName) {
  const parentDir = packageDir(parentName)
  if (!existsSync(join(parentDir, 'package.json'))) {
    return null
  }
  const parentPkg = JSON.parse(readFileSync(join(parentDir, 'package.json'), 'utf8'))
  return parentPkg.optionalDependencies?.[optionalName] ?? null
}

function resolveInstallSpecs() {
  const specs = []
  for (const { parent, optional } of PLATFORM_OPTIONALS) {
    const version = readOptionalVersion(parent, optional)
    if (!version) {
      continue
    }
    specs.push(`${optional}@${version}`)
  }
  return specs
}

function ensureInstalled(specs) {
  const missing = specs.filter((spec) => {
    const at = spec.lastIndexOf('@')
    const name = spec.slice(0, at)
    return !existsSync(packageDir(name))
  })
  if (missing.length === 0) {
    return
  }
  execSync(`npm install ${missing.join(' ')} --no-save --force`, {
    cwd: root,
    stdio: 'inherit',
  })
}

// Windows npm install --force prunes Linux optional deps from shared /mnt/c trees.
// WSL can install both Linux and Windows bindings; Windows npm already installs win32.
if (process.platform !== 'linux') {
  process.exit(0)
}

ensureInstalled(resolveInstallSpecs())
