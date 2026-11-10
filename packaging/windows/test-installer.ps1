# Explicit install/uninstall test for a Windows x64 account without an existing
# managed ZENO installation. Run in a new PowerShell process.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$exe = Join-Path $root 'installers\ZENO-Setup-x64.exe'
$expected = (Get-Content "$exe.sha256").Split(' ')[0]
if ((Get-FileHash $exe).Hash -ne $expected) { throw 'Installer checksum mismatch.' }
if (Test-Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ZENODesktopPreview_is1') {
    throw 'Use a separate Windows account to avoid changing the existing installation.'
}
$scratch = Join-Path $env:TEMP ('zeno-installer-test-' + [guid]::NewGuid())
New-Item -ItemType Directory $scratch | Out-Null
$appDir = Join-Path $scratch 'ZENO Desktop'
$env:ZENO_DATA_DIR = Join-Path $scratch 'test-profile'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:AWARENESS_ENABLED = 'false'
$argsList = '/VERYSILENT /SP- /SUPPRESSMSGBOXES /NORESTART /NOICONS /MERGETASKS=!speech,!localai,!desktopicon'
$p = Start-Process $exe -ArgumentList "$argsList /DIR=""$appDir"" /LOG=""$scratch\install.log""" -WindowStyle Hidden -PassThru -Wait
if ($p.ExitCode) { throw "Setup failed. See $scratch\install.log and $env:TEMP\ZENO-setup.log." }
try {
    Push-Location $appDir
    try {
        if (!(Test-Path 'docs\setup.md') -or !(Test-Path 'docs\desktop.md')) { throw 'Missing guides.' }
        Get-Content -Raw (Join-Path $PSScriptRoot 'smoke-desktop.py') | & '.\.venv\Scripts\python.exe' -
        if ($LASTEXITCODE) { throw 'Installed desktop failed to open its dashboard.' }
        Set-Content 'user-note.txt' 'installer test marker'
    } finally { Pop-Location }
} finally {
    $p = Start-Process "$appDir\unins000.exe" -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' -WindowStyle Hidden -PassThru -Wait
    if ($p.ExitCode -ne 0 -or (Test-Path "$appDir\main.py")) { throw 'Uninstall failed.' }
}
if (!(Test-Path "$appDir\user-note.txt")) { throw 'Uninstall removed user data.' }
Write-Output "Verified EXE checksum, private Python, desktop/dashboard startup, guides, uninstall, and data retention."
