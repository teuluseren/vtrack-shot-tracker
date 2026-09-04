#ifndef AppVersion
  #error AppVersion must be supplied with /DAppVersion=x.y.z
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\VTrackShotTracker"
#endif
#ifndef NumericVersion
  #error NumericVersion must be supplied with /DNumericVersion=x.y.z.0
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

#define AppName "vTrack Shot Tracker"
#define AppExeName "VTrackShotTracker.exe"

[Setup]
AppId={{13DB1622-C477-4BDC-95F0-16D00E5AA99B}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName}
AppPublisher=teuluseren
AppPublisherURL=https://github.com/teuluseren/vtrack-shot-tracker
AppSupportURL=https://github.com/teuluseren/vtrack-shot-tracker/issues
AppUpdatesURL=https://github.com/teuluseren/vtrack-shot-tracker/releases
DefaultDirName={autopf}\VTrack Shot Tracker
DefaultGroupName=vTrack Shot Tracker
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
SetupIconFile=..\assets\vtrack-app-icon.ico
OutputDir={#OutputDir}
OutputBaseFilename=VTrackShotTracker-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
VersionInfoVersion={#NumericVersion}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Start-VTrackShotTracker.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "Stop-VTrackShotTracker.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Start-VTrack.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Stop-VTrack.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Start vTrack Shot Tracker"; Filename: "{app}\{#AppExeName}"; Parameters: "start"
Name: "{group}\Shot Review"; Filename: "{app}\{#AppExeName}"; Parameters: "review"
Name: "{group}\Check for Updates"; Filename: "{app}\{#AppExeName}"; Parameters: "update"
Name: "{group}\Stop vTrack Shot Tracker"; Filename: "{app}\{#AppExeName}"; Parameters: "stop"
Name: "{group}\Uninstall vTrack Shot Tracker"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExeName}"; Parameters: "start"; Description: "Start vTrack Shot Tracker"; Flags: postinstall nowait skipifsilent unchecked

[UninstallRun]
Filename: "{app}\{#AppExeName}"; Parameters: "stop"; Flags: runhidden waituntilterminated; RunOnceId: "StopVTrackShotTracker"


[Code]
procedure StopInstalledTracker;
var
  ResultCode: Integer;
  ExePath: String;
begin
  ExePath := ExpandConstant('{app}\{#AppExeName}');
  if FileExists(ExePath) then
  begin
    Exec(ExePath, 'stop', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(250);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  { Stop the installed copy before Restart Manager checks files in use. }
  StopInstalledTracker;
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  { Stop the tracker before uninstallation begins, not after an in-use warning. }
  StopInstalledTracker;
  Result := True;
end;
