param(
    [switch]$KeepExisting,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogDir = Join-Path $Root "workspace\logs"
$FrontendDir = Join-Path $Root "frontend"
$BackendPython = Join-Path $Root ".venv313\Scripts\python.exe"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $Root

function Stop-ProcessSafe {
    param([int]$ProcessId)

    if ($ProcessId -eq $PID) {
        return
    }

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -ne $process) {
        Write-Host "Stopping PID=$ProcessId NAME=$($process.ProcessName)"
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Stop-PortListener {
    param([int]$Port)

    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        Stop-ProcessSafe -ProcessId $listener.OwningProcess
    }
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [System.Diagnostics.Process]$Process,
        [string]$Name,
        [string]$ErrorLog,
        [int]$TimeoutSeconds = 90
    )

    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        if ($Process.HasExited) {
            throw "$Name exited early. Check log: $ErrorLog"
        }

        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
            Write-Host "$Name ready: $Url"
            return
        } catch {
            Start-Sleep -Seconds 1
            $Process.Refresh()
        }
    }

    throw "$Name did not become ready in $TimeoutSeconds seconds. Check log: $ErrorLog"
}

if (-not (Test-Path $BackendPython)) {
    throw "CUDA backend Python not found: $BackendPython"
}

if (-not $KeepExisting) {
    Stop-PortListener -Port 8000
    if (-not $SkipFrontend) {
        Stop-PortListener -Port 5173
    }

    Get-CimInstance Win32_Process -Filter "name='python.exe'" |
        Where-Object { $_.CommandLine -like "*godtier-shorts*backend.main*" } |
        ForEach-Object { Stop-ProcessSafe -ProcessId $_.ProcessId }

    Get-CimInstance Win32_Process -Filter "name='ffmpeg.exe'" |
        Where-Object { $_.CommandLine -like "*godtier-shorts*workspace*" } |
        ForEach-Object { Stop-ProcessSafe -ProcessId $_.ProcessId }
}

Write-Host "Verifying CUDA backend runtime..."
& $BackendPython -c "import torch; print('torch', torch.__version__); print('cuda', torch.cuda.is_available()); print('gpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'); raise SystemExit(0 if torch.cuda.is_available() else 2)"
if ($LASTEXITCODE -ne 0) {
    throw "CUDA is not available in .venv313. Backend was not started."
}

$env:PYTORCH_NVML_BASED_CUDA_CHECK = "1"
$env:CUDA_DEVICE_ORDER = "PCI_BUS_ID"
$env:LOG_ACCELERATOR_STATUS_ON_STARTUP = "1"

$BackendOut = Join-Path $LogDir "backend_cuda_$Stamp.out.log"
$BackendErr = Join-Path $LogDir "backend_cuda_$Stamp.err.log"
$Backend = Start-Process `
    -FilePath $BackendPython `
    -ArgumentList @("-m", "backend.main") `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $BackendOut `
    -RedirectStandardError $BackendErr `
    -PassThru

Write-Host "Backend PID: $($Backend.Id)"
Write-Host "Backend logs: $BackendOut | $BackendErr"
Wait-HttpReady -Url "http://127.0.0.1:8000/docs" -Process $Backend -Name "Backend" -ErrorLog $BackendErr

if (-not $SkipFrontend) {
    $NpmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($null -eq $NpmCommand) {
        $NpmCommand = Get-Command npm -ErrorAction Stop
    }

    $FrontendOut = Join-Path $LogDir "frontend_dev_$Stamp.out.log"
    $FrontendErr = Join-Path $LogDir "frontend_dev_$Stamp.err.log"
    $Frontend = Start-Process `
        -FilePath $NpmCommand.Source `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort") `
        -WorkingDirectory $FrontendDir `
        -RedirectStandardOutput $FrontendOut `
        -RedirectStandardError $FrontendErr `
        -PassThru

    Write-Host "Frontend PID: $($Frontend.Id)"
    Write-Host "Frontend logs: $FrontendOut | $FrontendErr"
    Wait-HttpReady -Url "http://127.0.0.1:5173" -Process $Frontend -Name "Frontend" -ErrorLog $FrontendErr
}

Write-Host "GodTier Shorts dev stack is running."
