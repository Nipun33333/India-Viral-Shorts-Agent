[CmdletBinding()]
param(
    [string]$Serial = "",
    [string]$OutputPath = ".runtime\yt_create_ui.xml"
)

$ErrorActionPreference = "Stop"
$Package = "com.google.android.apps.youtube.producer"

function Invoke-Adb {
    param([string[]]$AdbArgs)
    $output = & adb -s $Serial @AdbArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ("ADB command failed: adb -s $Serial " + ($AdbArgs -join " ") + [Environment]::NewLine + $output)
    }
    return ($output | Out-String).Trim()
}

if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
    throw "ADB not found. Install Android SDK Platform-Tools and add its platform-tools folder to PATH."
}

$deviceOutput = & adb devices -l
if ($LASTEXITCODE -ne 0) { throw "Could not query ADB devices." }

$rows = @()
foreach ($line in ($deviceOutput | Select-Object -Skip 1)) {
    if ($line -match '^\s*(\S+)\s+(\S+)') {
        $rows += [pscustomobject]@{ Serial = $Matches[1]; State = $Matches[2]; Details = $line.Trim() }
    }
}

if ($Serial) {
    $selected = $rows | Where-Object { $_.Serial -eq $Serial } | Select-Object -First 1
} else {
    $online = @($rows | Where-Object { $_.State -eq "device" })
    if ($online.Count -eq 1) {
        $selected = $online[0]
        $Serial = $selected.Serial
    } elseif ($online.Count -gt 1) {
        throw "More than one Android device is connected. Re-run with -Serial <device-id>."
    } else {
        if ($rows | Where-Object { $_.State -eq "unauthorized" }) {
            throw "Phone is unauthorized. Unlock it and tap Allow on the USB debugging RSA prompt, then run this script again."
        }
        throw "No Android device is online. Connect the phone by USB, enable USB debugging, and check adb devices -l."
    }
}

if (-not $selected -or $selected.State -ne "device") {
    throw "Selected device is not online/authorized. Check USB debugging and run adb devices -l."
}

$Serial = $selected.Serial
$model = Invoke-Adb @("shell", "getprop", "ro.product.model")
$android = Invoke-Adb @("shell", "getprop", "ro.build.version.release")
$packageList = Invoke-Adb @("shell", "pm", "list", "packages", $Package)

if ($packageList -notmatch [regex]::Escape("package:$Package")) {
    throw "YouTube Create is not installed on $model. Install it from Google Play on the phone, sign in there, then run this script again."
}

Write-Host ""
Write-Host "Connected Android device:" -ForegroundColor Cyan
Write-Host "  Model: $model"
Write-Host "  Android: $android"
Write-Host "  Serial: $Serial"
Write-Host "  App: YouTube Create is installed"
Write-Host ""
Write-Host "Launching YouTube Create..."
Invoke-Adb @("shell", "monkey", "-p", $Package, "1") | Out-Null
Start-Sleep -Seconds 8

Write-Host "Capturing the current app accessibility hierarchy..."
Invoke-Adb @("shell", "uiautomator", "dump", "--compressed", "/sdcard/yt-create-ui.xml") | Out-Null

$fullOutput = Join-Path (Get-Location) $OutputPath
$outputDirectory = Split-Path -Parent $fullOutput
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
& adb -s $Serial pull "/sdcard/yt-create-ui.xml" $fullOutput
if ($LASTEXITCODE -ne 0) { throw "Could not copy the UI hierarchy from the phone." }

[xml]$ui = Get-Content -Raw -Path $fullOutput
$labels = @(
    $ui.SelectNodes("//node") | ForEach-Object {
        $text = $_.GetAttribute("text")
        $desc = $_.GetAttribute("content-desc")
        if ($text) { $text } elseif ($desc) { $desc }
    } | Where-Object { $_ } | Select-Object -Unique
)

Write-Host ""
Write-Host "Screen labels detected:" -ForegroundColor Cyan
$labels | ForEach-Object { Write-Host "  - $_" }

Write-Host ""
Write-Host "Saved private device UI snapshot to: $fullOutput"
Write-Host "Do not commit or share this file publicly; it can contain on-screen account or project text."
Write-Host "The script did not read, export, or store your Google password, OTP, or session tokens."
