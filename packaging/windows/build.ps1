param([string]$Compiler = 'ISCC.exe')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$stage = Join-Path ([IO.Path]::GetTempPath()) ('zeno-build-' + [guid]::NewGuid())
$payload = Join-Path $stage 'app'
$output = Join-Path $root 'installers'
New-Item -ItemType Directory -Force $stage,$output | Out-Null
try {
    $revision = git -C $root rev-parse --short=12 HEAD
    if ($LASTEXITCODE) { throw 'Cannot identify the source revision.' }
    # Export only committed application files. Local credentials, models, logs,
    # scratch experiments and the builder's virtual environment stay out.
    $files = @('awareness','brain','desktop','executor','server','tunnel','voice',
        'app_access.py','config.py','main.py','user_paths.py','.env.example',
        'Start-ZENO.cmd','requirements*.txt','docs/setup.md','docs/desktop.md',
        'docs/awareness.md','docs/privacy.md','packaging/windows')
    git -C $root archive --format=zip "--output=$stage\source.zip" HEAD -- @files
    if ($LASTEXITCODE) { throw 'Source export failed.' }
    Expand-Archive -LiteralPath "$stage\source.zip" -DestinationPath $payload
    Move-Item -LiteralPath "$payload\packaging" -Destination $stage
    & $Compiler "/DBuildRevision=$revision" "/DPayload=$payload" "/DOutputPath=$output" "$stage\packaging\windows\zeno.iss"
    if ($LASTEXITCODE) { throw 'Installer compilation failed.' }
    $exe = Join-Path $output 'ZENO-Setup-x64.exe'
    $hash = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  ZENO-Setup-x64.exe" | Set-Content -Encoding ascii "$exe.sha256"
} finally {
    $resolved = (Resolve-Path -LiteralPath $stage).Path
    if ([IO.Path]::GetDirectoryName($resolved) -eq [IO.Path]::GetTempPath().TrimEnd('\') -and
        [IO.Path]::GetFileName($resolved) -match '^zeno-build-[a-f0-9-]{36}$') {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
