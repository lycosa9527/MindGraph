# Script to kill processes using COM6
# Usage: .\kill_com6.ps1

$port = "COM6"

Write-Host "Searching for processes using $port..." -ForegroundColor Yellow

# Method 1: Try to find processes by name that commonly use serial ports
$commonSerialProcesses = @(
    "idf_monitor",
    "idf.py",
    "python",
    "putty",
    "teraterm",
    "minicom",
    "screen",
    "cu",
    "picocom"
)

$foundProcesses = @()

# Check for common serial port processes
foreach ($procName in $commonSerialProcesses) {
    $procs = Get-Process -Name $procName -ErrorAction SilentlyContinue
    if ($procs) {
        foreach ($proc in $procs) {
            $foundProcesses += $proc
            Write-Host "Found process: $($proc.ProcessName) (PID: $($proc.Id))" -ForegroundColor Cyan
        }
    }
}

# Method 2: Try using netstat to find processes (though COM ports don't always show up)
# This is more for TCP/UDP ports, but worth trying
try {
    $netstatOutput = netstat -ano | Select-String ":$port"
    if ($netstatOutput) {
        Write-Host "Found network connections on port $port" -ForegroundColor Cyan
    }
} catch {
    # Ignore errors
}

# Method 3: Check all processes and try to identify serial port usage
# This is a fallback - kill processes that might be holding the port
if ($foundProcesses.Count -eq 0) {
    Write-Host "No common serial processes found. Checking all processes..." -ForegroundColor Yellow
    
    # Get all processes and check command line arguments
    $allProcs = Get-Process | Where-Object { $_.ProcessName -match "python|idf|putty|screen" }
    foreach ($proc in $allProcs) {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
            if ($cmdLine -and $cmdLine -match "COM6|com6|$port") {
                $foundProcesses += $proc
                Write-Host "Found process with COM6 in command line: $($proc.ProcessName) (PID: $($proc.Id))" -ForegroundColor Cyan
            }
        } catch {
            # Ignore errors accessing process info
        }
    }
}

# Kill found processes
if ($foundProcesses.Count -gt 0) {
    Write-Host "`nAttempting to kill $($foundProcesses.Count) process(es)..." -ForegroundColor Yellow
    
    foreach ($proc in $foundProcesses) {
        try {
            Write-Host "Killing process: $($proc.ProcessName) (PID: $($proc.Id))" -ForegroundColor Red
            Stop-Process -Id $proc.Id -Force -ErrorAction Stop
            Write-Host "Successfully killed $($proc.ProcessName) (PID: $($proc.Id))" -ForegroundColor Green
        } catch {
            Write-Host "Failed to kill $($proc.ProcessName) (PID: $($proc.Id)): $_" -ForegroundColor Red
        }
    }
    
    Write-Host "`nDone!" -ForegroundColor Green
} else {
    Write-Host "`nNo processes found using $port." -ForegroundColor Yellow
    Write-Host "The port might be free, or the process might not be detectable by name." -ForegroundColor Yellow
    Write-Host "You may need to manually check Task Manager or use:" -ForegroundColor Yellow
    Write-Host "  Get-Process | Where-Object { `$_.ProcessName -match 'python|idf' }" -ForegroundColor Gray
}
