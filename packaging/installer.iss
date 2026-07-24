#define MyAppName "pyCapCut Studio"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "pyCapCut"
#define MyAppExeName "pyCapCutStudio.exe"

[Setup]
AppId={{A3AA37AD-07D2-4D8F-BBCF-5A878EC3B08A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\pyCapCut Studio
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=output
OutputBaseFilename=pyCapCut-Studio-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\dist\pyCapCutStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
const
  WebView2Url = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';

function WebView2Installed: Boolean;
var
  Version: String;
begin
  Result :=
    (RegQueryStringValue(HKCU32, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) and
      (Version <> '') and (Version <> '0.0.0.0')) or
    (RegQueryStringValue(HKLM32, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) and
      (Version <> '') and (Version <> '0.0.0.0'));
end;

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  if ProgressMax <> 0 then
    Log(Format('Downloading WebView2: %d%%', [Progress * 100 div ProgressMax]));
  Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  InstallerPath: String;
  ResultCode: Integer;
begin
  Result := '';
  if WebView2Installed then
    exit;

  try
    InstallerPath := DownloadTemporaryFile(
      WebView2Url,
      'MicrosoftEdgeWebview2Setup.exe',
      '',
      @OnDownloadProgress
    );
  except
    Result := 'WebView2 Runtime download failed. Check the Internet connection and retry.';
    exit;
  end;

  if not Exec(InstallerPath, '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or
     (ResultCode <> 0) then
    Result := 'WebView2 Runtime installation failed with code ' + IntToStr(ResultCode) + '.';
end;
