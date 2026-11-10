# Build the Windows preview installer

On Windows x64, install Inno Setup 6.4.3 and Git. Commit the application and
packaging sources to the revision you want to distribute. From the repository
root, run the following in PowerShell, using the installed compiler location.

```powershell
.\packaging\windows\build.ps1 -Compiler "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

The build exports an allowlist from Git HEAD and produces
`installers/ZENO-Setup-x64.exe` and its SHA-256 file. Commit both together.
The wizard records the source revision as its version. It downloads the private
Python runtime and dependencies during installation, so an internet connection
is required. When requirements change, regenerate `requirements.lock` on
Windows x64 with the uv command recorded at the top of that file and rebuild.
Check the [release gates](../../docs/launch-readiness.md) before any commercial release.

To verify the actual EXE on another Windows x64 test account without an installed
copy of ZENO Desktop, run the following from the repository root:

```powershell
powershell.exe -NoProfile -File .\packaging\windows\test-installer.ps1
```

The check installs to a fresh temporary folder, opens the installed dashboard
using the private runtime, and checks that uninstall keeps a user-created file.
Speech and Ollama downloads are separate optional checks.
