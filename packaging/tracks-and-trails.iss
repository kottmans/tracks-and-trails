; Inno Setup script for the Windows installer (`T-322`, per `REL-001`).
;
; Built on `STARBASE`, where Inno Setup is installed **by hand, once**: a self-hosted runner must
; not provision itself as a side effect of a build (`OPS-012` §3, and the `setup-python` incident
; it cites).
;
;   ISCC.exe /DAppVersion=0.1.0 /DSourceDir=..\dist\tracks-and-trails packaging\tracks-and-trails.iss
;
; **`ISCC.exe` is not on `PATH` and its location depends on how it was installed.** `winget
; install JRSoftware.InnoSetup` puts it **per-user** under
; `%LOCALAPPDATA%\Programs\Inno Setup 6\`, not in `C:\Program Files (x86)\` — measured on
; `STARBASE` 2026-09-12, where a workflow step looking only at Program Files reported it missing
; on a machine that had it.
;
; **Every default below is a decision, and each is reversible by ruling** — an installer is the
; first thing a user judges, and a default nobody chose is still a choice.

#ifndef AppVersion
  #error Pass /DAppVersion=X.Y.Z — the version comes from __init__.py via REL-003, never from here
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\tracks-and-trails"
#endif

; **`VersionInfoVersion` will not take a PEP 440 version, and the first compile proved it**
; (`T-322`). `AppVersion` comes straight from `__init__.py` via `REL-003`, which between releases
; is `0.1.0.dev0` — and Inno rejects that outright: *"Value of [Setup] section directive
; VersionInfoVersion is invalid"*, compile aborted. The file's own numeric resource has to be
; numeric.
;
; **Derived here rather than passed in**, so there is still exactly one version input. A second
; `/D` define would be a second opinion about the version, which is the thing `REL-003` and this
; script's `#error` above exist to prevent. `.dev0` becomes a fourth numeric component —
; `0.1.0.dev0` → `0.1.0.0` — and a release version passes through untouched.
;
; Anything else fails the compile rather than being guessed at: if a pre-release channel is ever
; adopted (`v0.1.0-rc1`, which `tools/version_tag_check.py` currently refuses), this stops and
; asks, instead of stamping the binary with a version nobody chose.
#define NumericVersion StringChange(AppVersion, ".dev", ".")
#if NumericVersion != Trim(NumericVersion) || Pos("-", NumericVersion) > 0 || Pos("+", NumericVersion) > 0
  #error VersionInfoVersion must be numeric; AppVersion has a suffix this script cannot map. Decide the mapping rather than letting Inno guess.
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
VersionInfoVersion={#NumericVersion}

; **Per-user, no administrator prompt** (`NFR-004`). The application writes nothing beside itself,
; so it needs no elevation — and a per-machine install would add an admin prompt on top of the
; SmartScreen warning `REL-005` already accepts, which is two warnings before the first launch.
PrivilegesRequired=lowest
; **No install-mode question on a double-click** (maintainer ruling, 2026-09-12). This was
; `dialog`, which asked "for me only / for all users" before anything else -- found in the
; maintainer's first interactive install, since every automated run is `/VERYSILENT` and never
; sees a dialog. It contradicted the comment above: one more question before first launch, and
; "all users" is an admin prompt. `commandline` keeps the escape hatch for an administrator
; (`/ALLUSERS`) without asking everyone else a question most people cannot answer.
PrivilegesRequiredOverridesAllowed=commandline
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

OutputDir=..\dist
OutputBaseFilename=Tracks-and-Trails-{#AppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\src\tracks_and_trails\resources\icons\icon.ico
; **Our logo, not Inno's stock box-and-disc** (`T-322`). Setting `SetupIconFile` covered the
; .exe's own icon and nothing else, so every page of the wizard carried the default artwork.
; Rendered from the logo masters by `tools/icons/render_installer_art.py`; Inno picks the size
; nearest the display's DPI from each list, so a high-DPI screen gets a sharp logo, not a scaled one.
WizardSmallImageFile=installer-art\wizard-small-58x58.png,installer-art\wizard-small-77x77.png,installer-art\wizard-small-97x97.png,installer-art\wizard-small-116x116.png,installer-art\wizard-small-124x124.png,installer-art\wizard-small-143x143.png,installer-art\wizard-small-159x159.png
WizardImageFile=installer-art\wizard-large-202x386.png,installer-art\wizard-large-269x515.png,installer-art\wizard-large-336x643.png,installer-art\wizard-large-403x772.png,installer-art\wizard-large-430x824.png,installer-art\wizard-large-498x953.png,installer-art\wizard-large-534x1022.png
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

; **No `[UninstallDelete]` section, and that is the rule rather than an omission** (`T322-R1`).
; It held `Type: filesandordirs; Name: "{app}"`, under a comment saying *only what the installer
; created* — and `filesandordirs` is recursive deletion of the **whole directory**, including
; anything the user put there or that was there before this installed into it. Inno's own
; documentation warns against exactly that. Inno already removes every file its log says it
; installed, and the directory itself once it is empty, so nothing is lost by having none.
; The application writes nothing beside itself (`NFR-004`), so there is nothing else of ours to
; name. `tests/unit/test_windows_packaging.py` refuses a wildcard or recursive entry under `{app}`,
; and `T-039`'s Sandbox run plants a user file inside the install directory and requires it to
; survive.

[Messages]
; Shown only if `[Code]`'s single dialog could not restart the uninstaller, in which case nothing of
; the user's is removed, so this says so.
ConfirmUninstall=Remove %1?%n%nYour settings, download queue and downloaded files are kept, and so is anything you saved in its folder.

; **No file associations and no protocol handler in 0.1.0** (`T-322` scope). `T-104` — handing a
; second launch's URL to the running instance — is not built, so an association would open a
; message box rather than start a download. A known omission rather than a surprise.

[Code]
// **One question, asked once, before anything is removed** (`T-322`, the maintainer's rulings in
// `T-327` on 2026-09-13: a user should not have to delete settings by hand, and should not be
// asked twice). Inno's own "Remove this app?" box cannot be switched off from here: its source
// (`Setup.Uninstall.pas`) shows it whenever the run is not `/SILENT` or `/VERYSILENT`. So an
// interactive run shows this dialog instead, then starts the uninstaller again with `/SILENT`,
// which skips Inno's box, and ends itself. `/REMOVEDATA` carries a ticked box to that second run;
// `/ASKED` tells it the user has already been asked, so it says when it has finished.
//
// **Silent runs never ask, and keep the data unless told otherwise.** `T-039`'s Sandbox run
// uninstalls with `/VERYSILENT` and fingerprints the data before and after, so only an explicit
// `/REMOVEDATA` removes anything.
//
// **If the second run cannot be started**, the uninstall carries on in the usual way: Inno's box,
// whose message below says the settings are kept, and nothing is removed.
//
// **Named, application-owned items only, never the folder wholesale** (`T322-R1`'s rule, carried
// over from `{app}`). Every path below is one the application itself writes under `platformdirs`
// with `appauthor=False`, which on Windows puts config, data and cache in
// %LOCALAPPDATA%\tracksandtrails. Anything else found there, a video someone chose to save into
// it included, survives, and `RemoveDir` then leaves the folder because it is not empty.
// Downloads are never here: they go to the folder chosen in Preferences.
// `tests/unit/test_windows_packaging.py` pins each name against the code that writes it.

const
  RemoveDataSwitch = '/REMOVEDATA';
  AskedSwitch = '/ASKED';

function ApplicationDataFolder: String;
begin
  Result := ExpandConstant('{localappdata}\tracksandtrails');
end;

function HasSwitch(const Switch: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Switch) = 0 then
      Result := True;
end;

procedure RemoveApplicationData;
var
  Folder: String;
begin
  Folder := ApplicationDataFolder;
  DeleteFile(Folder + '\settings.toml');
  DeleteFile(Folder + '\settings.toml.writing');
  DeleteFile(Folder + '\window.toml');
  DeleteFile(Folder + '\library.sqlite3');
  DeleteFile(Folder + '\library.sqlite3-wal');
  DeleteFile(Folder + '\library.sqlite3-shm');
  DelTree(Folder + '\ytdlp', True, True, True);
  DelTree(Folder + '\Cache', True, True, True);
  RemoveDir(Folder);
end;

// The dialog. True when the user chose Uninstall; `RemoveData` is the tick box.
function AskHowToUninstall(var RemoveData: Boolean): Boolean;
var
  Form: TSetupForm;
  Question: TNewStaticText;
  RemoveBox: TNewCheckBox;
  UninstallButton, CancelButton: TNewButton;
  ButtonWidth: Integer;
begin
  // Four arguments: Inno Setup 6.7.3 on `STARBASE` refuses the older no-argument form.
  Form := CreateCustomForm(ScaleX(420), ScaleY(142), False, False);
  try
    Form.Caption := 'Uninstall {#AppName}';

    Question := TNewStaticText.Create(Form);
    Question.Parent := Form;
    Question.ShowAccelChar := False;
    Question.AutoSize := False;
    Question.WordWrap := True;
    Question.Left := ScaleX(16);
    Question.Top := ScaleY(16);
    Question.Width := Form.ClientWidth - ScaleX(32);
    Question.Height := ScaleY(36);
    Question.Caption := 'Remove {#AppName} from this computer? Your downloaded files are kept.';

    RemoveBox := TNewCheckBox.Create(Form);
    RemoveBox.Parent := Form;
    RemoveBox.Left := ScaleX(16);
    RemoveBox.Top := ScaleY(60);
    RemoveBox.Width := Form.ClientWidth - ScaleX(32);
    RemoveBox.Height := ScaleY(20);
    RemoveBox.Caption := 'Also remove my settings and download queue';
    RemoveBox.Checked := False;

    ButtonWidth := Form.CalculateButtonWidth(['Uninstall', 'Cancel']);

    CancelButton := TNewButton.Create(Form);
    CancelButton.Parent := Form;
    CancelButton.Caption := 'Cancel';
    CancelButton.ModalResult := mrCancel;
    CancelButton.Cancel := True;
    CancelButton.Width := ButtonWidth;
    CancelButton.Height := ScaleY(23);
    CancelButton.Left := Form.ClientWidth - ScaleX(16) - ButtonWidth;
    CancelButton.Top := Form.ClientHeight - ScaleY(16) - CancelButton.Height;

    UninstallButton := TNewButton.Create(Form);
    UninstallButton.Parent := Form;
    UninstallButton.Caption := 'Uninstall';
    UninstallButton.ModalResult := mrOk;
    UninstallButton.Default := True;
    UninstallButton.Width := ButtonWidth;
    UninstallButton.Height := CancelButton.Height;
    UninstallButton.Left := CancelButton.Left - ScaleX(8) - ButtonWidth;
    UninstallButton.Top := CancelButton.Top;

    Form.ActiveControl := UninstallButton;
    Result := Form.ShowModal = mrOk;
    RemoveData := RemoveBox.Checked;
  finally
    Form.Free;
  end;
end;

function InitializeUninstall: Boolean;
var
  RemoveData: Boolean;
  Switches: String;
  ResultCode: Integer;
begin
  Result := True;
  if UninstallSilent then
    Exit;
  if not AskHowToUninstall(RemoveData) then
  begin
    Result := False;
    Exit;
  end;
  Switches := '/SILENT ' + AskedSwitch;
  if RemoveData then
    Switches := Switches + ' ' + RemoveDataSwitch;
  // Ends this run only once the second one has started; otherwise Inno's own box follows.
  if Exec(ExpandConstant('{uninstallexe}'), Switches, '', SW_SHOWNORMAL, ewNoWait, ResultCode) then
    Result := False;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;
  if HasSwitch(RemoveDataSwitch) then
    RemoveApplicationData;
  if HasSwitch(AskedSwitch) then
    MsgBox('{#AppName} was removed from this computer.', mbInformation, MB_OK);
end;
