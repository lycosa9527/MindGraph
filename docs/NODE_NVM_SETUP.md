# Node.js via nvm (Ubuntu)

Install a clean Node.js toolchain when system `npm` is broken (for example `MODULE_NOT_FOUND: promise-retry`).

**Policy:** Use the **latest** Node.js and **latest** npm (local dev, servers, and CI). Re-run the upgrade commands below when you set up a new machine or want to refresh versions.

## Prerequisites

- Ubuntu shell access (SSH or local)
- `curl` installed

## Steps

### 1. Check current state

```bash
node -v 2>/dev/null || echo "no node"
npm -v 2>/dev/null || echo "npm broken"
which node npm
```

If `npm` fails, do not run `npm install -g` until nvm is set up.

### 2. Remove broken apt Node (recommended)

```bash
sudo apt remove -y nodejs npm 2>/dev/null || true
sudo apt autoremove -y
```

### 3. Install nvm

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm --version
```

### 4. Install latest Node and npm

```bash
nvm install node
nvm use node
nvm alias default node
npm install -g npm@latest
node -v
npm -v
which node npm
```

`which npm` should point under `~/.nvm/`, not `/usr/lib/node_modules/npm`.

### 5. MindGraph frontend

```bash
cd ~/MindGraph/frontend
npm install
```

`frontend/package.json` includes an **`allowScripts`** allowlist (pinned versions) for dependencies that run install/postinstall scripts (`esbuild`, `vue-demi`, `core-js`, and optional `fsevents` on macOS). This satisfies npm 11+ install-script policy and avoids `npm warn allow-scripts` noise.

If you still see allow-script warnings after `git pull`, either your tree is behind or a dependency bump added a new script package. Fix it:

```bash
cd ~/MindGraph/frontend
npm approve-scripts --allow-scripts-pending   # list unreviewed (npm >= 11.16)
npm approve-scripts esbuild vue-demi core-js  # or: npm approve-scripts --all
git diff package.json                         # commit updated allowScripts if changed
```

Without `npm approve-scripts` (older npm 11.x), open `package-lock.json`, search for `"hasInstallScript": true`, and add matching `"name@version": true` entries under `allowScripts` in `package.json`.

Run `npm run build` when you need a production build.

**WSL-only `node_modules`:** Always run `npm install` inside WSL at `~/MindGraph/frontend`. Do not reuse `node_modules` from a Windows checkout on `/mnt/c` — native packages (`esbuild`, `@rolldown/binding-*`) are platform-specific and will break cross-platform copies.

**WSL dev on `/mnt/c`:** If the repo lives under `/mnt/c/...`, `npm run dev` can fail with `EACCES` when Vite updates `node_modules/.vite`. [`vite.config.ts`](../frontend/vite.config.ts) redirects the optimizer cache to `~/.cache/mindgraph-vite` on Linux when the project root is on `/mnt/`. Override with `VITE_CACHE_DIR=/path/to/cache` if needed. Prefer a native WSL clone under `~/` for best performance.

**Vite 8 HMR (hot reload):** After the Vite 8 upgrade, dev uses `host: 0.0.0.0` for LAN/WSL access. Browsers cannot open `ws://0.0.0.0`, so [`vite.config.ts`](../frontend/vite.config.ts) sets `server.hmr.host` to `localhost` when you use `http://localhost:41732` on the same machine. If the terminal logs `[vite] hmr update` but the browser never changes, open DevTools → Console and look for WebSocket errors; restart `npm run dev` after pulling this fix.

| Symptom | Fix |
| --- | --- |
| HMR works in terminal, browser stuck | Use `http://localhost:41732` (not `0.0.0.0` in the address bar) or set `VITE_HMR_HOST` to your LAN IP when testing from another device |
| Saves from Windows/Cursor, no terminal line on WSL `/mnt/c` | Enabled automatically via polling; force with `VITE_USE_POLLING=1` |
| Debug circular deps / full reloads | `npm run dev -- --debug hmr` |

**CLI scripts:** Frontend maintenance scripts run with **Node native type stripping** (`node scripts/foo.ts`). The `tsx` package is not used. Relative imports in locale bundles use explicit `.ts` suffixes for Node ESM.

**DEP0205 check:** After install, verify no deprecated `module.register()` warnings:

```bash
npm run check:dep0205
```

Requires Node **≥ 22.18** (type stripping; Node 26 recommended). See `frontend/.nvmrc` and `engines` in `frontend/package.json`.

### 6. New shells

The nvm installer adds lines to `~/.bashrc`. Open a new session and verify:

```bash
node -v && npm -v
```

## Keep up to date

On an existing nvm setup:

```bash
nvm install node
nvm use node
nvm alias default node
npm install -g npm@latest
node -v && npm -v
```

## Line endings (WSL + Windows / `/mnt/c`)

The repo stores **LF** (see `.gitattributes`, `frontend/prettier.config.js`, `.editorconfig`).
Prettier/ESLint `Delete ␍` errors mean your **working copy** has CRLF — not that the repo is wrong.

**Cause:** Windows Git with `core.autocrlf=true` and/or Cursor saving CRLF on `C:` / `/mnt/c`.

**One-time machine setup** (run once per clone):

```bash
# Stop Git from converting LF → CRLF on checkout
git config core.autocrlf false

# Refresh working tree from the LF git index (only if you have no uncommitted edits you need)
# git restore frontend/
```

If you have local edits, normalize endings without changing code (WSL):

```bash
sudo apt install -y dos2unix
find frontend \( -name '*.ts' -o -name '*.vue' -o -name '*.js' -o -name '*.css' -o -name '*.scss' \) -exec dos2unix {} +
find frontend/tests -name '*.ts' -exec dos2unix {} +
```

**Ongoing:** `.vscode/settings.json` and `.editorconfig` force editors to save LF.
Do **not** rely on `npm run lint:fix` to mass-convert the tree — fix Git + editor once, then `npm run check` should pass.

| Check | Expected |
|-------|----------|
| `git config core.autocrlf` | `false` |
| `git ls-files --eol frontend/src/App.vue` | `i/lf  w/lf` |
| `npm run check` in WSL | no `Delete ␍` errors |

## Success checklist

| Check | Expected |
|-------|----------|
| `node -v` | Current Node release (not an old apt package) |
| `npm -v` | Current npm, no error |
| `which npm` | path under `~/.nvm/` |
| `npm install` in `frontend/` | completes without errors |
| `npm install` in `frontend/` | no `allow-scripts` warnings (or `allowScripts` updated) |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `nvm: command not found` | Run the export/load lines from step 3, or log out and back in |
| `node` still from `/usr/bin` | Repeat step 2; confirm `which node` shows nvm |
| Global npm upgrade still fails | Fix step 4 first; ensure `npm -v` works before `npm install -g npm@latest` |
| `npm warn allow-scripts` after install | Pull latest `frontend/package.json`, or run `npm approve-scripts` / update `allowScripts` (see step 5) |
