<#
.SYNOPSIS
    Development shortcut script to initialize secrets and run the backend + standalone frontend.

.DESCRIPTION
    DISCLAIMER: This shortcut does not respect production security principles; for the sake of
    simplicity and velocity in local development, this script automates .env secret generation,
    starts the backend Docker Compose stack, and builds and runs the standalone frontend container.
#>

param(
    [switch]$Stop,
    [switch]$ResetVolumes
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Disclaimer = @"
==============================================================================
[DEV SHORTCUT DISCLAIMER]
This shortcut does not respect security principles; for the sake of simplicity
and velocity, this script automatically initializes local .env secrets, starts
the backend stack, and builds/runs the standalone frontend container.
Do NOT use this workflow in production environments.
==============================================================================
"@
Write-Host $Disclaimer -ForegroundColor Yellow

function Invoke-DockerQuiet {
    param([string[]]$Arguments)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker @Arguments *> $null
    } finally {
        $ErrorActionPreference = $prev
    }
}

if ($Stop -or $ResetVolumes) {
    Write-Host "Stopping standalone frontend container..."
    Invoke-DockerQuiet @("rm", "-f", "monster-tamer-frontend")

    if ($ResetVolumes) {
        Write-Host "Stopping backend stack and removing persisted volumes..."
        docker compose down -v
    } else {
        Write-Host "Stopping backend stack..."
        docker compose down
    }
    exit $LASTEXITCODE
}

function New-UrlSafeSecret {
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return ([Convert]::ToBase64String($bytes)) -replace '\+', '-' -replace '/', '_' -replace '=', ''
}

$envExample = Join-Path $PSScriptRoot ".env.example"
$envFile = Join-Path $PSScriptRoot ".env"

if (-not (Test-Path $envExample)) {
    throw "Missing .env.example in $PSScriptRoot"
}

$secretsUpdated = $false

if (-not (Test-Path $envFile)) {
    Write-Host "Creating .env from .env.example with generated local secrets..."
    $lines = Get-Content $envExample | ForEach-Object {
        if ($_ -match '^([A-Z0-9_]+)=change-me\s*$') {
            "$($Matches[1])=$(New-UrlSafeSecret)"
        } else {
            $_
        }
    }
    [System.IO.File]::WriteAllLines($envFile, $lines)
    $secretsUpdated = $true
} else {
    Write-Host "Checking existing .env for missing or 'change-me' variables..."
    $existing = @{}
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([A-Z0-9_]+)=(.*)$') {
            $existing[$Matches[1]] = $Matches[2]
        }
    }
    $updated = New-Object System.Collections.Generic.List[string]
    foreach ($line in (Get-Content $envFile)) {
        if ($line -match '^([A-Z0-9_]+)=change-me\s*$') {
            $k = $Matches[1]
            $val = New-UrlSafeSecret
            $existing[$k] = $val
            $updated.Add("$k=$val")
            $secretsUpdated = $true
        } else {
            $updated.Add($line)
        }
    }
    foreach ($line in (Get-Content $envExample)) {
        if ($line -match '^([A-Z0-9_]+)=(.*)$') {
            $k = $Matches[1]
            if (-not $existing.ContainsKey($k)) {
                $val = if ($Matches[2].Trim() -eq 'change-me') { New-UrlSafeSecret } else { $Matches[2] }
                $updated.Add("$k=$val")
                $secretsUpdated = $true
            }
        }
    }
    if ($secretsUpdated) {
        [System.IO.File]::WriteAllLines($envFile, $updated)
    }
}

if ($secretsUpdated) {
    Write-Host "New secrets generated; resetting any stale Docker DB volumes so passwords match..."
    Invoke-DockerQuiet @("compose", "down", "-v")
}

Write-Host "`nStarting backend microservices with Docker Compose..."
$ErrorActionPreference = "Continue"
docker compose up --build -d --wait
$composeExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($composeExit -ne 0) {
    throw "Backend stack failed to start."
}

Write-Host "`nBuilding and starting standalone frontend container..."
$ErrorActionPreference = "Continue"
docker build -t monster-tamer-frontend ./frontend_service
$buildExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($buildExit -ne 0) {
    throw "Frontend image build failed."
}
Invoke-DockerQuiet @("rm", "-f", "monster-tamer-frontend")
$ErrorActionPreference = "Continue"
docker run -d --name monster-tamer-frontend -p 127.0.0.1:8080:8080 monster-tamer-frontend | Out-Null
$runExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($runExit -ne 0) {
    throw "Frontend container failed to start."
}

Write-Host "`nAll services are up and running:" -ForegroundColor Green
Write-Host "  - Frontend:    http://localhost:8080"
Write-Host "  - API Gateway: https://localhost:5005"
Write-Host "`nTip: if your browser warns about the local self-signed CA certificate,"
Write-Host "visit https://127.0.0.1:5005/health once and accept it before playing."
Write-Host "To stop everything: .\start-dev.ps1 -Stop"
