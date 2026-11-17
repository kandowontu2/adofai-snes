#requires -Version 5.1
<#
Remove the retired full PCM release and redundant ADOFAI PCM build caches.
Run from PowerShell: .\cleanup-full-pcm.ps1
Preview instead:      .\cleanup-full-pcm.ps1 -WhatIf

Keeps hybrid/compressed releases, save files, source WAV/OGG/BRR assets,
compiled chart/graphics data, and the latest pack's song-start PCM.
Busy emulator folders are skipped; rerun after testing to clean those caches.
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param()

$ErrorActionPreference = 'Stop'
$cleanupRoot = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
if (-not (Test-Path -LiteralPath (Join-Path $cleanupRoot 'tools\community_catalog.json'))) {
    throw 'Keep this script in the ADOFAI SNES project folder.'
}
$protectedHybrid = Join-Path $cleanupRoot 'dist\adofai-msu-hybrid'
$protectedPack = Join-Path $cleanupRoot 'build\packs\sky-blue-master'
$cleanupFiles = New-Object 'System.Collections.Generic.List[string]'
$busyFolders = New-Object 'System.Collections.Generic.List[string]'
$emulatorCommands = @(Get-CimInstance Win32_Process -Filter "Name = 'Mesen.exe'" -ErrorAction SilentlyContinue |
    ForEach-Object { $_.CommandLine })

function Assert-ProjectPath([string]$Path) {
    $absolute = [IO.Path]::GetFullPath($Path)
    if (-not $absolute.StartsWith($cleanupRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing a path outside this project: $absolute"
    }
    $checkPath = $absolute
    while ($checkPath -and $checkPath -ne $cleanupRoot) {
        if (Test-Path -LiteralPath $checkPath) {
            $item = Get-Item -LiteralPath $checkPath -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing a link or junction: $checkPath"
            }
        }
        $checkPath = [IO.Path]::GetDirectoryName($checkPath)
    }
    return $absolute
}

function Test-EmulatorFolder([string]$Folder) {
    foreach ($commandLine in $emulatorCommands) {
        if ($commandLine -and $commandLine.IndexOf($Folder + '\', [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            return $true
        }
    }
    return $false
}

# Explicit retired release only; never recurse through dist or delete saves.
$retiredFolder = Assert-ProjectPath (Join-Path $cleanupRoot 'dist\adofai-msu-master')
if (Test-Path -LiteralPath $retiredFolder) {
    if (Test-EmulatorFolder $retiredFolder) {
        $busyFolders.Add($retiredFolder)
    } else {
        foreach ($item in Get-ChildItem -LiteralPath $retiredFolder -File -Force) {
            $knownReleaseFile = $item.Name -match '^adofai-\d+\.pcm$' -or
                $item.Name -match '^adofai-msu-master\.zip(?:\.new)?$' -or
                $item.Name -in @('adofai.msu', 'adofai.sfc', 'catalog.json', 'pcm-manifest.json',
                    'README.txt', 'RELEASE-NOTES.txt', 'SHA256SUMS.txt', 'verification.json') -or
                $item.Name -match '^(?:level\d+-pcm-hit-mix|msu-\d+)\.json$'
            if ($knownReleaseFile) { $cleanupFiles.Add((Assert-ProjectPath $item.FullName)) }
        }
    }
}

# These are generated PCM files, never original music or chart/graphics caches.
$packRoot = Assert-ProjectPath (Join-Path $cleanupRoot 'build\packs')
if (Test-Path -LiteralPath $packRoot) {
    foreach ($packDirectory in Get-ChildItem -LiteralPath $packRoot -Directory -Force) {
        $packPath = Assert-ProjectPath $packDirectory.FullName
        if (-not (Test-Path -LiteralPath (Join-Path $packPath 'pack.json'))) { continue }
        $numberedPcm = @(Get-ChildItem -LiteralPath $packPath -File -Filter 'adofai-*.pcm' |
            Where-Object { $_.Name -match '^adofai-\d+\.pcm$' })
        if (-not $numberedPcm.Count) { continue }
        if (Test-EmulatorFolder $packPath) {
            $busyFolders.Add($packPath)
            continue
        }
        foreach ($item in $numberedPcm) {
            [void]($item.Name -match '^adofai-(\d+)\.pcm$')
            $trackNumber = [int]$Matches[1]
            if ($trackNumber -lt 1000) {
                if ($packPath -eq $protectedPack) { continue }
                $hybridCopy = Join-Path $protectedHybrid $item.Name
                $latestCopy = Join-Path $protectedPack $item.Name
                if (-not (Test-Path -LiteralPath $hybridCopy) -and -not (Test-Path -LiteralPath $latestCopy)) {
                    Write-Warning "Keeping the only hybrid song-start copy: $($item.FullName)"
                    continue
                }
            }
            $cleanupFiles.Add((Assert-ProjectPath $item.FullName))
        }
    }
}

$cleanupBytes = 0L
foreach ($path in $cleanupFiles) { $cleanupBytes += (Get-Item -LiteralPath $path).Length }
Write-Host ('Selected {0} files, {1:N2} GiB logical size (hardlinks can share disk space).' -f
    $cleanupFiles.Count, ($cleanupBytes / 1GB))
$removedFiles = 0
$failedFiles = 0
foreach ($path in $cleanupFiles) {
    if ($PSCmdlet.ShouldProcess($path, 'Delete retired PCM release/cache file')) {
        try {
            Remove-Item -LiteralPath $path -Force
            $removedFiles++
        } catch {
            $failedFiles++
            Write-Warning "Could not remove $path : $($_.Exception.Message)"
        }
    }
}
if ((Test-Path -LiteralPath $retiredFolder) -and -not (Test-EmulatorFolder $retiredFolder)) {
    if (-not @(Get-ChildItem -LiteralPath $retiredFolder -Force).Count) {
        if ($PSCmdlet.ShouldProcess($retiredFolder, 'Remove empty retired release folder')) {
            Remove-Item -LiteralPath $retiredFolder
        }
    }
}
foreach ($folder in $busyFolders) { Write-Warning "Skipped an active Mesen folder; rerun after testing: $folder" }
Write-Host "Removed $removedFiles files. Hybrid/compressed releases and saves are preserved."
if ($failedFiles) { throw "$failedFiles files could not be removed. Close the program using them and rerun." }
