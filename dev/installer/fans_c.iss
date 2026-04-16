; fans_c.iss  --  Inno Setup 6 Installer Script for FANS-C
; ========================================================
;
; PURPOSE
; -------
; This script compiles a standard Windows installer (FANS-C-Setup.exe)
; for the FANS-C Facial Verification System.  The installer:
;
;   * Copies the packaged application (dist\FANS-C\) to the user's
;     local app data folder (no admin rights required).
;   * Creates a desktop shortcut pointing to FANS-C.exe.
;   * Creates a Start Menu group with a shortcut and an uninstall link.
;   * Registers a standard Add/Remove Programs entry for clean uninstall.
;   * Prompts the user to launch the app after installation completes.
;
; APPROACH  --  WHY INNO SETUP?
; --------------------------
; Inno Setup 6 is the simplest practical Windows installer tool:
;   * Free, no license costs.
;   * Single .iss script file  --  easy to review and modify.
;   * Handles %LocalAppData% installation (no UAC elevation required).
;   * Handles desktop + Start Menu shortcuts natively.
;   * NSIS is an alternative but requires a more complex scripting syntax.
;
; WHY {localappdata} AND NOT {autopf} (Program Files)?
; ----------------------------------------------------
; The packaged FANS-C application writes data at runtime:
;   * db.sqlite3 is created on first launch by `migrate`.
;   * media/ is written to as beneficiary photos are captured.
;   * .env is created by the user before first launch.
;
; Program Files requires administrator-level write access.  Attempting
; to write db.sqlite3 there would silently fail on a standard-user
; account.  Installing to %LocalAppData% (writable by the current user
; without UAC) avoids this entirely.  The trade-off is that each Windows
; user on a shared machine has a separate installation, but for a
; single-operator barangay workstation this is the correct behaviour.
;
; PREREQUISITES
; -------------
; * Inno Setup 6 must be installed on the BUILD machine.
;   Download: https://jrsoftware.org/isdl.php
; * PyInstaller must have already produced dist\FANS-C\ successfully.
;   Run .\build_exe.ps1 before opening this script.
;
; USAGE
; -----
;   1. Open Inno Setup Compiler (iscc.exe or the IDE).
;   2. File -> Open -> select installer\fans_c.iss.
;   3. Build -> Compile  (or press F9).
;   4. The installer is written to installer\Output\FANS-C-Setup.exe.
;
;   Command line (from project root):
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\fans_c.iss
;
; IMPORTANT NOTES FOR DISTRIBUTORS
; ---------------------------------
; * .env is NOT included in the installer.  The user must create .env
;   in the install directory before the first launch.  A .env.example
;   file is shipped alongside the executable as a reference.
; * db.sqlite3 is NOT included.  It is created automatically on first
;   launch when `migrate` runs.
; * FaceNet model weights (~90 MB) are downloaded from the internet on
;   the first launch.  Ensure the target machine has internet access.
; * The total install size is approximately 2-4 GB (mainly TensorFlow).


; ===========================================================================
; [Setup]  --  Installer metadata and global options
; ===========================================================================

[Setup]

; Application identity
AppName=FANS-C Facial Verification System
AppVersion=1.0.0
AppPublisher=FANS-C Capstone Project
AppPublisherURL=https://github.com
AppSupportURL=https://github.com
AppUpdatesURL=https://github.com

; Install directory  --  uses %LocalAppData%\Programs\FANS-C
; This is writable without UAC and is the standard location for
; user-scoped application installs (similar to VS Code, Slack, etc.)
DefaultDirName={localappdata}\Programs\FANS-C
DefaultGroupName=FANS-C

; No UAC elevation required because we install to %LocalAppData%
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Installer output
OutputDir=Output
OutputBaseFilename=FANS-C-Setup

; Optional: use custom icon if present (must be a .ico file)
; Uncomment and set the path if you have fans_c.ico in the project root.
; SetupIconFile=..\fans_c.ico

; Compression  --  LZMA solid is the best compression ratio for large files.
; TensorFlow has many compressible .py files; expect 30-50% reduction.
Compression=lzma
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Installer appearance
WizardStyle=modern
WizardSmallImageFile=
DisableDirPage=no
DisableProgramGroupPage=no

; Uninstaller  --  creates an entry in Add/Remove Programs
UninstallDisplayName=FANS-C Facial Verification System
UninstallDisplayIcon={app}\FANS-C.exe

; Version info embedded in the installer executable
VersionInfoVersion=1.0.0.0
VersionInfoCompany=FANS-C Capstone Project
VersionInfoDescription=FANS-C Facial Verification System Installer
VersionInfoProductName=FANS-C
VersionInfoProductVersion=1.0.0.0


; ===========================================================================
; [Languages]  --  Installer UI language
; ===========================================================================

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"


; ===========================================================================
; [Tasks]  --  Optional tasks the user can choose during install
; ===========================================================================

[Tasks]

; Desktop shortcut  --  unchecked by default.  The Start Menu shortcut is
; always created (in [Icons]).  Most users prefer not to clutter the desktop,
; but the option is offered.
Name: "desktopicon"; \
  Description: "Create a &desktop shortcut"; \
  GroupDescription: "Additional shortcuts:"


; ===========================================================================
; [Files]  --  Application files to install
; ===========================================================================

[Files]

; The entire packaged application produced by build_exe.ps1 / PyInstaller.
; Source is relative to the location of this .iss file (installer\).
; DestDir {app} = the install directory (e.g. %LocalAppData%\Programs\FANS-C).
;
; Flags:
;   ignoreversion      --  do not check file version stamps (our files have none)
;   recursesubdirs     --  include all subdirectories (templates/, static/, etc.)
;   createallsubdirs   --  recreate the directory tree at the destination

Source: "..\dist\FANS-C\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs; \
  Comment: "FANS-C application files (Django + TensorFlow + FaceNet)"


; ===========================================================================
; [Icons]  --  Shortcuts created by the installer
; ===========================================================================

[Icons]

; Start Menu shortcut  --  always created
Name: "{group}\FANS-C Facial Verification System"; \
  Filename: "{app}\FANS-C.exe"; \
  Comment: "Start the FANS-C Facial Verification System"

; Start Menu uninstall shortcut
Name: "{group}\Uninstall FANS-C"; \
  Filename: "{uninstallexe}"; \
  Comment: "Remove FANS-C from this computer"

; Desktop shortcut  --  only if the user chose the task above
Name: "{commondesktop}\FANS-C"; \
  Filename: "{app}\FANS-C.exe"; \
  Tasks: desktopicon; \
  Comment: "Start the FANS-C Facial Verification System"


; ===========================================================================
; [Run]  --  Actions performed after installation completes
; ===========================================================================

[Run]

; Launch FANS-C immediately after install.
;
; No manual .env setup is required before the first launch.
; launcher.py detects the missing .env automatically, generates unique
; SECRET_KEY and EMBEDDING_ENCRYPTION_KEY values, writes .env, and
; shows a confirmation dialog before the browser opens.
;
; The checkbox is checked by default because the app is ready to run.
; Users who are restoring an existing database should UN-CHECK this box,
; update EMBEDDING_ENCRYPTION_KEY in .env first, then launch manually.
;
; Flags:
;   nowait        -- do not block the installer waiting for FANS-C to exit
;   postinstall   -- show on the final wizard page
;   skipifsilent  -- skipped in silent (/SILENT) installs
Filename: "{app}\FANS-C.exe"; \
  Description: "Launch &FANS-C now"; \
  Flags: nowait postinstall skipifsilent; \
  Comment: "Start FANS-C -- .env will be created automatically on first launch"


; ===========================================================================
; [UninstallDelete]  --  Extra cleanup on uninstall
; ===========================================================================

[UninstallDelete]

; Remove files created at runtime that the standard uninstaller won't touch.
; Note: this deletes the database and all stored data.  The user is warned
; by the standard Inno Setup uninstall dialog before proceeding.
;
; If you want to preserve user data on uninstall, comment out these entries
; and instruct users to manually back up the install directory first.

; SQLite database (created on first launch, not part of the install)
Type: files; Name: "{app}\db.sqlite3"

; Runtime log files if any accumulate
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\fans\__pycache__"
Type: filesandordirs; Name: "{app}\accounts\__pycache__"
Type: filesandordirs; Name: "{app}\beneficiaries\__pycache__"
Type: filesandordirs; Name: "{app}\verification\__pycache__"
Type: filesandordirs; Name: "{app}\logs\__pycache__"


; ===========================================================================
; [Messages]  --  Custom installer messages
; ===========================================================================

[Messages]

; Finish page message.
;
; No manual .env setup is needed for a fresh install.  launcher.py generates
; the configuration automatically on first run.
;
; The message covers two cases:
;   * Fresh install / empty database  --  just click the checkbox and launch.
;   * Restoring existing data from another machine  --  replace the key first.
FinishedLabel=FANS-C has been installed successfully.%n%nFresh install (no existing data):%n  Check the box below and click Finish.  FANS-C will create%n  its configuration file automatically on first launch.%n%nRestoring an existing database from another machine:%n  1. Do NOT launch yet  --  uncheck the box below.%n  2. Open the installation folder and edit .env.%n  3. Set EMBEDDING_ENCRYPTION_KEY to the value from the original .env.%n  4. Then launch FANS-C from the Start Menu.%n%nIn both cases the encryption key is saved in .env inside the%n installation folder.  Back that file up securely.


; ===========================================================================
; [Code]  --  Pascal script for custom installer logic
; ===========================================================================

[Code]

{ ---------------------------------------------------------------------------
  PrepareToInstall
  ---------------
  Runs before the installer copies any files.

  Checks for an existing installation and informs the user what will be
  preserved vs. what the new launcher.py does automatically.

  Two cases are handled:

  Case A  --  existing .env found (upgrade of a working installation)
    Application files are updated; .env, db.sqlite3, and media/ are
    preserved unchanged.  The encryption key is unchanged, so all
    existing face data remains readable.

  Case B  --  db.sqlite3 found but no .env (unusual: data without config)
    The installer still proceeds.  On first launch, launcher.py will
    detect the missing .env and generate a new one -- but the new
    EMBEDDING_ENCRYPTION_KEY will NOT match the key used to encrypt the
    face data in the existing database.  The user is warned here and
    again by launcher.py at first launch.
  --------------------------------------------------------------------------- }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  existingEnv : String;
  existingDb  : String;
begin
  Result := '';  { empty string = no error, continue install }

  existingEnv := ExpandConstant('{app}\.env');
  existingDb  := ExpandConstant('{app}\db.sqlite3');

  if FileExists(existingEnv) then
  begin
    { Case A: upgrade of a working installation }
    MsgBox(
      'An existing FANS-C installation was detected.' + #13#10 +
      #13#10 +
      'Application files will be updated.  Your data files will be' + #13#10 +
      'preserved:' + #13#10 +
      '  * .env (encryption key, settings)' + #13#10 +
      '  * db.sqlite3 (beneficiary and log data)' + #13#10 +
      '  * media/ (captured images)' + #13#10 +
      #13#10 +
      'For a clean reinstall, delete the installation folder first.',
      mbInformation,
      MB_OK
    );
  end
  else if FileExists(existingDb) then
  begin
    { Case B: database exists but .env is missing }
    MsgBox(
      'A database was found but no .env configuration file was detected.' + #13#10 +
      #13#10 +
      'On first launch, FANS-C will create .env automatically with a NEW' + #13#10 +
      'encryption key.  This new key CANNOT decrypt face data stored with' + #13#10 +
      'the previous key.' + #13#10 +
      #13#10 +
      'If you want to keep existing face data:' + #13#10 +
      '  After installation, edit .env in the installation folder and' + #13#10 +
      '  set EMBEDDING_ENCRYPTION_KEY to the original value before' + #13#10 +
      '  launching FANS-C.',
      mbConfirmation,
      MB_OK
    );
  end;
end;
