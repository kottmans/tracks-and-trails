; Inno Setup script for the Windows installer (`T-322`, per `REL-001`).
;
; Built on `STARBASE`, where Inno Setup is installed **by hand, once**: a self-hosted runner must
; not provision itself as a side effect of a build (`OPS-012` §3, and the `setup-python` incident
; it cites).
;
;   ISCC.exe /DAppVersion=0.1.0 /DSourceDir=..\dist\tracks-and-trails packaging\tracks-and-trails.iss
;
; **Every default below is a decision, and each is reversible by ruling** — an installer is the
; first thing a user judges, and a default nobody chose is still a choice.

#ifndef AppVersion
  #error Pass /DAppVersion=X.Y.Z — the version comes from __init__.py via REL-003, never from here
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\tracks-and-trails"
#endif

#define AppName "Tracks & Trails"
#define AppExe "tracks-and-trails.exe"
#define AppPublisher "Sean Kottman"
#define AppUrl "https://github.com/kottmans/tracks-and-trails"

[Setup]
AppId={{8F3C4A21-6D5E-4B7A-9C12-3E8D5A7B1F40}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
VersionInfoVersion={#AppVersion}

; **Per-user, no administrator prompt** (`NFR-004`). The application writes nothing beside itself,
; so it needs no elevation — and a per-machine install would add an admin prompt on top of the
; SmartScreen warning `REL-005` already accepts, which is two warnings before the first launch.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

OutputDir=..\dist
OutputBaseFilename=Tracks-and-Trails-{#AppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\src\tracks_and_trails\resources\icons\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; `REL-005`: `0.1.0` ships unsigned. Named here rather than left blank so that adding a certificate
; is an edit to a line that exists.
; SignTool=standard

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; **Start Menu always; desktop shortcut opt-in and unchecked.** A desktop icon nobody asked for is
; the most common complaint about Windows installers, and the Start Menu entry is what makes the
; application findable.
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The whole one-dir tree, including `licenses\` — `LIC-001`'s obligation, gated by `T-323`.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; **Only what the installer created.** `DAT-001` keeps the user's settings, queue database and
; downloads: an uninstaller that deleted a download history would be destroying data the user
; never put here. `T-039` asserts both halves separately — leftovers under the install root are a
; failure, leftovers under the user directories are the intended behaviour.
Type: filesandordirs; Name: "{app}"

[Messages]
; Said on the uninstaller's own final page, because a user deciding whether to uninstall is
; entitled to know what survives it.
ConfirmUninstall=Remove %1?%n%nYour settings, download history and downloaded files are kept. Remove them by hand if you want them gone.

; **No file associations and no protocol handler in 0.1.0** (`T-322` scope). `T-104` — handing a
; second launch's URL to the running instance — is not built, so an association would open a
; message box rather than start a download. A known omission rather than a surprise.
