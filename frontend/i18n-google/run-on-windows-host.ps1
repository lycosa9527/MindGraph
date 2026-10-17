# Run the Google i18n gap-fill CLI with Windows Node (VPN / system proxy).
# WSL cannot reach Google. From WSL (automatic via npm run i18n:gap-fill):
#   npm run i18n:gap-fill -- --locale=ta
# Or explicitly:
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File i18n-google/run-on-windows-host.ps1 --locale=ta
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontend = Split-Path -Parent $here
# npm from WSL passes a UNC frontend path; pushd assigns a drive letter for Node cwd.
pushd $frontend | Out-Null

function Resolve-WindowsNodeExe {
  $candidates = @(
    'C:\Program Files\nodejs\node.exe',
    'C:\Program Files (x86)\nodejs\node.exe'
  )
  if ($env:NVM_HOME) {
    $candidates += @(
      (Join-Path $env:NVM_HOME 'nodejs.exe'),
      (Join-Path $env:NVM_HOME 'node.exe')
    )
  }
  if ($env:NVM_SYMLINK) {
    $candidates += (Join-Path $env:NVM_SYMLINK 'node.exe')
  }
  if ($env:FNM_DIR) {
    $candidates += (Join-Path $env:FNM_DIR 'node.exe')
  }
  $localNode = Join-Path $env:LOCALAPPDATA 'Programs\node\node.exe'
  if ($localNode) {
    $candidates += $localNode
  }
  foreach ($path in $candidates) {
    if ($path -and (Test-Path -LiteralPath $path)) {
      return (Resolve-Path -LiteralPath $path).Path
    }
  }
  $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
  if ($null -ne $nodeCmd -and $nodeCmd.Source) {
    return $nodeCmd.Source
  }
  $prevEap = $ErrorActionPreference
  $ErrorActionPreference = 'SilentlyContinue'
  $whereLines = @(where.exe node 2>$null)
  $ErrorActionPreference = $prevEap
  if ($whereLines.Count -gt 0) {
    $first = $whereLines[0].Trim()
    if ($first -and (Test-Path -LiteralPath $first)) {
      return (Resolve-Path -LiteralPath $first).Path
    }
  }
  return $null
}

$node = Resolve-WindowsNodeExe
if (-not $node) {
  Write-Error @"
Windows node.exe not found. Install Node.js on Windows (see frontend/.nvmrc), or add node to PATH.
Gap-fill needs Windows Node so Google Translate uses the host VPN / system proxy (127.0.0.1:7078).
WSL Node cannot be used for live fill.
"@
}

Write-Host "[i18n:gap-fill] node=$node cwd=$(Get-Location)"
try {
  & $node (Join-Path $here 'cli.ts') @args
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
  popd | Out-Null
}
