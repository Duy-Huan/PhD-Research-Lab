; PhD Research Lab per-user Windows installer (v6.6.2). Built by scripts/build_installers.py, never by hand:
;   ISCC /DAppVersion=<x.y.z> /DStageDir=<staged folder> /DOutputDir=<folder> packaging\windows\phdlab.iss
; The application (embedded Python + app) lives in {app}; research data lives in %LOCALAPPDATA%\PhDLab and in the
; project folders the researcher chooses, so uninstalling or upgrading never removes data.
#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef StageDir
  #error StageDir is required
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif

[Setup]
AppId={{6C1F3F2B-8E7A-4C5D-9B1E-3D5A2F7C9E41}
AppName=PhD Research Lab
AppVersion={#AppVersion}
AppVerName=PhD Research Lab {#AppVersion}
AppPublisher=PhD Research Lab
DefaultDirName={localappdata}\Programs\PhDLab
DefaultGroupName=PhD Research Lab
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=phdlab-{#AppVersion}-windows-x64-setup
SetupIconFile={#StageDir}\phdlab.ico
UninstallDisplayIcon={app}\phdlab.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PhD Research Lab"; Filename: "{app}\python\python.exe"; Parameters: """{app}\app\start.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\phdlab.ico"
Name: "{group}\Uninstall PhD Research Lab"; Filename: "{uninstallexe}"
Name: "{autodesktop}\PhD Research Lab"; Filename: "{app}\python\python.exe"; Parameters: """{app}\app\start.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\phdlab.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\python\python.exe"; Parameters: """{app}\app\start.py"""; WorkingDir: "{app}\app"; Description: "{cm:LaunchProgram,PhD Research Lab}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; Only files the application itself created inside {app} (bytecode caches); never the data folder.
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\python"
