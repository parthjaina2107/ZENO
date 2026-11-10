[Setup]
AppId=ZENODesktopPreview
AppName=ZENO Desktop
AppVersion={#BuildRevision}
DefaultDirName={localappdata}\Programs\ZENO Desktop
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
MinVersion=10.0
WizardStyle=modern
DisableProgramGroupPage=yes
Compression=lzma2
SolidCompression=yes
OutputBaseFilename=ZENO-Setup-x64
OutputDir={#OutputPath}
UninstallDisplayName=ZENO Desktop
SetupLogging=yes

[Tasks]
Name: speech; Description: "Download the local speech recognition model"; GroupDescription: "Model downloads:"
Name: localai; Description: "Install Ollama and download qwen3:4b for local AI (several GB)"; GroupDescription: "Model downloads:"; Flags: unchecked
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "bootstrap.ps1"; Flags: dontcopy
Source: "requirements.lock"; Flags: dontcopy

[Icons]
Name: "{userprograms}\ZENO Desktop"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\main.py"" --desktop"; WorkingDir: "{app}"
Name: "{userdesktop}\ZENO Desktop"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\main.py"" --desktop"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\main.py"" --desktop"; WorkingDir: "{app}"; Description: "Open ZENO Desktop"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\runtime"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Args: String;
  Code: Integer;
begin
  ExtractTemporaryFile('bootstrap.ps1');
  ExtractTemporaryFile('requirements.lock');
  Args := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{tmp}\bootstrap.ps1') + '" -AppDir "' + ExpandConstant('{app}') + '"';
  if WizardIsTaskSelected('speech') then Args := Args + ' -Speech';
  if WizardIsTaskSelected('localai') then Args := Args + ' -LocalAI';
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    Args, ExpandConstant('{tmp}'), SW_SHOW, ewWaitUntilTerminated, Code) or (Code <> 0) then
    Result := 'Dependency or model setup failed. See %TEMP%\ZENO-setup.log. ' +
      'Check the connection or go back and uncheck optional downloads, then retry.';
end;
