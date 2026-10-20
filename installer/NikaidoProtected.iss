#define MyAppName "Nikaido DualSense"
#ifndef MyAppVersion
  #define MyAppVersion "2.9.8.13"
#endif
#ifndef SourceDir
  #define SourceDir "..\release_protected\Nikaido"
#endif

[Setup]
; El mismo AppId mantiene una sola instalación de Nikaido y permite actualizar
; una build normal con una protegida sin crear programas duplicados.
AppId={{54E59F0D-97E5-4A39-929A-01B21D9DD25F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Team Nikaido
AppCopyright=© Team Nikaido
VersionInfoCompany=Team Nikaido
VersionInfoCopyright=© Team Nikaido
DefaultDirName={localappdata}\Programs\Nikaido DualSense
DefaultGroupName=Nikaido DualSense
DisableProgramGroupPage=yes
OutputDir=..\release_protected
OutputBaseFilename=Nikaido_DualSense-{#MyAppVersion}-Protected-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\Nikaido.exe
SetupIconFile=..\assets\icon.ico
LicenseFile=..\EULA_NIKAIDO.txt
CloseApplications=yes
RestartApplications=yes
CloseApplicationsFilter=Nikaido.exe
ChangesAssociations=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked
Name: "autostart"; Description: "Iniciar Nikaido con Windows"; GroupDescription: "Inicio:"; Flags: unchecked

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Nikaido DualSense"; Filename: "{app}\Nikaido.exe"
Name: "{autodesktop}\Nikaido DualSense"; Filename: "{app}\Nikaido.exe"; Tasks: desktopicon
Name: "{userstartup}\Nikaido DualSense"; Filename: "{app}\Nikaido.exe"; Parameters: "--minimized"; Tasks: autostart

[Run]
Filename: "{app}\Nikaido.exe"; Description: "Abrir Nikaido DualSense"; Flags: nowait postinstall skipifsilent
