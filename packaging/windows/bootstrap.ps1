param([Parameter(Mandatory=$true)][string]$AppDir, [switch]$Speech, [switch]$LocalAI)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Start-Transcript -Path (Join-Path $env:TEMP 'ZENO-setup.log') -Force | Out-Null
try {
    function Run([string]$File, [string[]]$Arguments) {
        & $File @Arguments
        if ($LASTEXITCODE -ne 0) { throw "$([IO.Path]::GetFileName($File)) failed (exit $LASTEXITCODE)." }
    }
    $AppDir = [IO.Path]::GetFullPath($AppDir)
    $runtime = Join-Path $AppDir 'runtime'
    New-Item -ItemType Directory -Force -Path $runtime | Out-Null
    $uv = Join-Path $runtime 'uv.exe'
    $wheel = Join-Path $PSScriptRoot 'uv-wheel.zip'
    Write-Host 'Downloading verified Python setup tools...'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://files.pythonhosted.org/packages/c2/5d/8e0b84503b77ead843ef57e4f9305eb32a95cac6806c0e0d54b9404a5f7b/uv-0.12.19-py3-none-win_amd64.whl' -OutFile $wheel
    $stream = [IO.File]::OpenRead($wheel)
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        $digest = [BitConverter]::ToString($sha256.ComputeHash($stream)).Replace('-', '')
    } finally {
        $sha256.Dispose()
        $stream.Dispose()
    }
    if ($digest -ne 'dcbc531a96762569bbfe9639b4f45f00aabff51f427540711f63e7c23f225fdf') { throw 'Python setup tool checksum mismatch.' }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($wheel)
    try {
        $entry = $zip.Entries | Where-Object Name -eq 'uv.exe' | Select-Object -First 1
        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $uv, $true)
    } finally { $zip.Dispose() }
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $runtime 'python'
    $env:UV_NO_CONFIG = '1'
    $env:UV_INDEX_URL = 'https://pypi.org/simple'
    $env:UV_LINK_MODE = 'copy'
    Run $uv @('python','install','3.11.16','--no-bin','--no-registry')
    $venv = Join-Path $AppDir '.venv'
    $previous = Join-Path $runtime 'zeno-previous-env'
    if (!(Test-Path -LiteralPath $venv) -and (Test-Path -LiteralPath $previous)) {
        [IO.Directory]::Move($previous, $venv)
    }
    $candidate = Join-Path $AppDir ('.zeno-env-' + [guid]::NewGuid())
    Run $uv @('venv','--managed-python','--python','3.11.16','--relocatable',$candidate)
    $python = Join-Path $candidate 'Scripts\python.exe'
    Write-Host 'Installing desktop, speech and integration dependencies...'
    Run $uv @('pip','install','--python',$python,'--require-hashes','-r',(Join-Path $PSScriptRoot 'requirements.lock'))
    Run $python @('-c','import PySide6.QtWebEngineWidgets, faster_whisper, winrt.windows.media.control')
    if ($Speech) {
        Write-Host 'Preparing the local speech model...'
        $models = Join-Path $env:LOCALAPPDATA 'ZENO\models'
        Run $python @('-c',"import sys; from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8', download_root=sys.argv[1])",$models)
    }
    if ($LocalAI) {
        Write-Host 'Preparing Ollama and downloading qwen3:4b...'
        $ollama = @("$env:LOCALAPPDATA\ZENO\ollama\ollama.exe","$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",(Get-Command ollama.exe -ErrorAction SilentlyContinue).Source) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
        if (-not $ollama) {
            Run 'winget.exe' @('install','--exact','--id','Ollama.Ollama','--source','winget','--silent','--accept-package-agreements','--accept-source-agreements')
            $ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
        }
        $env:OLLAMA_HOST = '127.0.0.1:11434'
        $env:OLLAMA_NO_CLOUD = '1'
        function ServerReady {
            try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2; return $true } catch { return $false }
        }
        if (-not (ServerReady)) {
            Start-Process $ollama -ArgumentList 'serve' -WindowStyle Hidden
            for ($i=0; $i -lt 30 -and -not (ServerReady); $i++) { Start-Sleep -Seconds 1 }
        }
        Run $ollama @('pull','qwen3:4b')
    }
    if (Test-Path -LiteralPath $previous) {
        $old = Get-Item -LiteralPath $previous
        if ($old.FullName -ne (Join-Path $runtime 'zeno-previous-env') -or
            $old.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint) -or
            !(Test-Path -LiteralPath (Join-Path $previous 'pyvenv.cfg'))) {
            throw 'Cannot identify previous ZENO environment. Check the setup log.'
        }
        Remove-Item -LiteralPath $old.FullName -Recurse -Force
    }
    if (Test-Path -LiteralPath $venv) {
        if (!(Test-Path -LiteralPath (Join-Path $venv 'pyvenv.cfg'))) { throw 'Unexpected existing .venv directory.' }
        [IO.Directory]::Move($venv, $previous)
    }
    try {
        [IO.Directory]::Move($candidate, $venv)
        Run (Join-Path $venv 'Scripts\python.exe') @('-c','import PySide6.QtWebEngineWidgets, faster_whisper, winrt.windows.media.control')
    } catch {
        if (Test-Path -LiteralPath $venv) { [IO.Directory]::Move($venv, $candidate) }
        if (Test-Path -LiteralPath $previous) { [IO.Directory]::Move($previous, $venv) }
        throw
    }
} catch {
    Write-Host "Setup failed: $_"
    exit 1
} finally {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
        $unused = Get-Item -LiteralPath $candidate
        if ($unused.Parent.FullName -eq $AppDir -and $unused.Name -match '^\.zeno-env-[a-f0-9-]{36}$' -and
            !$unused.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) {
            Remove-Item -LiteralPath $unused.FullName -Recurse -Force
        }
    }
    Stop-Transcript | Out-Null
}
