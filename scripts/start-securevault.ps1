$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot

function Find-Docker {
    $command = Get-Command docker -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    $bundled = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
    if (Test-Path -LiteralPath $bundled) { return $bundled }

    throw 'Docker was not found. Install Docker Desktop before starting SecureVault.'
}

function Test-DockerEngine([string]$docker) {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        & $docker info --format '{{.ServerVersion}}' *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Test-SecureVaultFrontend {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:3000' -TimeoutSec 2 -UseBasicParsing
        return $response.StatusCode -eq 200 -and $response.Content -match '<title>SecureVault'
    } catch {
        return $false
    }
}

$docker = Find-Docker
if (-not (Test-DockerEngine $docker)) {
    $desktop = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'
    if (-not (Test-Path -LiteralPath $desktop)) {
        throw 'Docker Desktop is installed in an unexpected location. Open it manually and run this task again.'
    }

    Write-Host 'Starting Docker Desktop...'
    Start-Process -FilePath $desktop
    $ready = $false
    for ($attempt = 0; $attempt -lt 45; $attempt++) {
        Start-Sleep -Seconds 2
        if (Test-DockerEngine $docker) { $ready = $true; break }
    }
    if (-not $ready) {
        throw 'Docker Desktop did not become ready. Check its window for a startup message, then run this task again.'
    }
}

if (-not (Test-Path -LiteralPath '.env.docker')) {
    $python = Join-Path $projectRoot 'backend\venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python -ErrorAction Stop).Source }
    Write-Host 'First run: generating local secrets (.env.docker)...'
    & $python 'backend\scripts\init_docker_env.py'
    if ($LASTEXITCODE -ne 0) { throw 'Could not generate .env.docker.' }
}
git config core.hooksPath .githooks 2>$null  # enable the pre-commit quality gate

Write-Host 'Starting the SecureVault database and API...'
& $docker compose --env-file '.env.docker' up -d --wait
if ($LASTEXITCODE -ne 0) {
    throw 'SecureVault could not start its database and API. Review the message above and try again.'
}

if (Test-SecureVaultFrontend) {
    Write-Host ''
    Write-Host 'SecureVault is ready: http://127.0.0.1:3000' -ForegroundColor Cyan
    return
}

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$node = if ($nodeCommand) { $nodeCommand.Source } else {
    Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
}
if (-not (Test-Path -LiteralPath $node)) {
    throw 'Node.js was not found. Install Node.js 22 or later, then run this task again.'
}

Write-Host ''
Write-Host 'SecureVault is ready: http://127.0.0.1:3000' -ForegroundColor Cyan
Start-Process 'http://127.0.0.1:3000'
Write-Host 'Keep this terminal open. Press Ctrl+C when your demonstration is finished.'
& $node (Join-Path $projectRoot 'frontend\server.mjs')
