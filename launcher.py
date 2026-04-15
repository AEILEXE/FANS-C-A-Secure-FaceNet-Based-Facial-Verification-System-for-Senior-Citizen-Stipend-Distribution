"""
launcher.py  --  FANS-C Windows Desktop Launcher
=================================================

PURPOSE
-------
This is the entry point for the packaged Windows desktop application.
It replaces the developer workflow of manually activating a venv and
running `python manage.py runserver`. When the user double-clicks
FANS-C.exe (or its shortcut), this script:

    1. Initialises or validates .env (generates SECRET_KEY and
       EMBEDDING_ENCRYPTION_KEY automatically if they are absent)
    2. Applies any pending Django database migrations
    3. Starts the Django web server in a background thread
    4. Waits until the server is actually accepting connections
    5. Opens the system in the user's default browser
    6. Keeps running until the server exits (keeps the process alive)

FIRST-RUN BEHAVIOUR
-------------------
On a fresh install where no .env exists yet:
  * A new .env is created automatically with safe defaults.
  * A unique EMBEDDING_ENCRYPTION_KEY is generated with Fernet.generate_key().
  * A unique SECRET_KEY is generated with secrets.token_urlsafe(50).
  * The user is shown an info dialog confirming setup and reminding them
    to back up the .env file.
  * If an existing db.sqlite3 is found alongside a missing .env (e.g. a
    reinstall over an existing database), a warning is shown explaining
    that the new key cannot decrypt existing face data and the original
    key must be restored.

On subsequent launches .env is already present; the launcher just
validates that EMBEDDING_ENCRYPTION_KEY is a valid Fernet key and
starts normally.

APPROACH
--------
- When packaged by PyInstaller (sys.frozen == True), waitress is used as
  the WSGI server. waitress is a pure-Python production WSGI server that
  works reliably inside a PyInstaller bundle. Django's runserver is NOT
  used for packaged builds because its autoreloader uses multiprocessing
  internally, which is incompatible with frozen executables.

- When run from source (dev mode), Django's built-in runserver is used
  with --noreload, so developer behaviour is unchanged.

- A port of 8765 is used deliberately to avoid conflicts with common dev
  servers (8000, 8080, 3000, 5000).

PACKAGING COMPATIBILITY
-----------------------
This file is the PyInstaller entry point (fans_c.spec -> Analysis(['launcher.py'])).
It must NOT import heavy dependencies (tensorflow, cv2, etc.) at the top level --
those are imported lazily by Django when the first request arrives.
"""

import os
import sys
import time
import socket
import secrets
import threading
import webbrowser
from pathlib import Path

# ---------------------------------------------------------------------------
# Base directory resolution
# ---------------------------------------------------------------------------
# In PyInstaller onedir mode, sys.executable is the FANS-C.exe file inside
# the installed/dist directory.  All bundled project files (fans/, templates/,
# static/, staticfiles/) are siblings of that executable.
#
# In source mode, __file__ is launcher.py at the project root.
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent

# Make sure all Django apps are importable.
_base_dir_str = str(BASE_DIR)
if _base_dir_str not in sys.path:
    sys.path.insert(0, _base_dir_str)

# ---------------------------------------------------------------------------
# Server configuration
# ---------------------------------------------------------------------------
# Port 8765 is an unusual port that is very unlikely to be in use.
# Change only if you know another service occupies 8765 on target machines.
HOST = '127.0.0.1'
PORT = 8765
APP_URL = f'http://{HOST}:{PORT}/'

# ---------------------------------------------------------------------------
# Dialog helpers
# ---------------------------------------------------------------------------

def _show_error(title, message):
    """
    Show a blocking error dialog (tkinter) and mirror to stderr.
    Blocking is intentional -- the user must acknowledge before the
    launcher exits with a non-zero code.
    """
    print(f'\n[FANS-C ERROR] {title}\n{message}\n', file=sys.stderr)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        pass


def _show_warning(title, message):
    """Show a non-fatal warning dialog and mirror to stderr."""
    print(f'\n[FANS-C WARNING] {title}\n{message}\n', file=sys.stderr)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        messagebox.showwarning(title, message)
        root.destroy()
    except Exception:
        pass


def _show_info(title, message):
    """Show an informational dialog and mirror to stdout."""
    print(f'\n[FANS-C INFO] {title}\n{message}\n')
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        messagebox.showinfo(title, message)
        root.destroy()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Key generation helpers
# ---------------------------------------------------------------------------

def _new_secret_key():
    """
    Generate a strong, URL-safe Django SECRET_KEY.
    Uses the standard-library secrets module -- no extra dependencies.
    """
    return secrets.token_urlsafe(50)


def _new_fernet_key():
    """
    Generate a new Fernet symmetric encryption key as a plain ASCII string.
    Fernet keys are URL-safe base64-encoded 32-byte values.
    Raises ImportError if the cryptography package is missing (should not
    happen in a packaged build).
    """
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


# ---------------------------------------------------------------------------
# .env template written on a completely fresh install
# ---------------------------------------------------------------------------
# {secret_key} and {embedding_key} are replaced with generated values.
# All other settings are sensible defaults for a packaged deployment.
# DEBUG is False because the packaged app uses whitenoise in production mode.

_ENV_TEMPLATE = """\
# FANS-C Configuration  --  auto-generated on first run
# =======================================================
# KEEP THIS FILE SAFE AND BACKED UP.
#
# EMBEDDING_ENCRYPTION_KEY encrypts every stored face embedding.
# If this key is lost or changed, all registered face data becomes
# permanently unreadable and beneficiaries must re-register from scratch.
#
# To use this installation alongside an existing database from another
# machine, replace EMBEDDING_ENCRYPTION_KEY with the key from that
# machine's .env file BEFORE registering any new beneficiaries.
# =======================================================

# Django core
SECRET_KEY={secret_key}
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# Database  --  SQLite is correct for single-workstation deployments
USE_SQLITE=True
DB_NAME=fans_db
DB_USER=fans_user
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432

# Face embedding encryption  --  DO NOT CHANGE after first use
EMBEDDING_ENCRYPTION_KEY={embedding_key}

# Face matching
DEMO_MODE=True
DEMO_THRESHOLD=0.60
VERIFICATION_THRESHOLD=0.75
MAX_RETRY_ATTEMPTS=2

# Liveness
LIVENESS_REQUIRED=False
ANTI_SPOOF_THRESHOLD=0.15

# Media storage
MEDIA_ROOT=media

# Offline sync (leave SYNC_API_URL empty for standalone operation)
SYNC_API_URL=
SYNC_API_KEY=
SYNC_TIMEOUT=30
SYNC_BATCH_SIZE=50
"""

# Secret key values that are known placeholder strings (from settings.py).
# If found in .env we replace them with a generated key.
_SECRET_KEY_PLACEHOLDERS = frozenset({
    '',
    'django-insecure-change-this-immediately',
    'your-secret-key-here-change-this-in-production',
})


# ---------------------------------------------------------------------------
# Environment initialisation
# ---------------------------------------------------------------------------

def _init_env():
    """
    Ensure .env exists and contains valid SECRET_KEY and EMBEDDING_ENCRYPTION_KEY.

    Handles three scenarios:

    1. No .env, no database (clean first install)
       - Generate both keys, write a complete .env, show an info dialog.

    2. No .env, database already exists (reinstall / machine migration)
       - Generate both keys, write .env, but show a WARNING explaining that
         the EMBEDDING_ENCRYPTION_KEY must be replaced with the original key
         if the existing database contains face data.

    3. .env already exists (normal subsequent launch, or partial config)
       - Load .env.
       - If SECRET_KEY is missing or is a placeholder value, generate and
         save a new one silently (does not affect face data).
       - If EMBEDDING_ENCRYPTION_KEY is missing or empty, generate one,
         save it, and warn if a database already exists (same reason as #2).
       - Validate that EMBEDDING_ENCRYPTION_KEY is a well-formed Fernet key.

    Returns True on success, False if a fatal error occurred (e.g. the
    install directory is not writable or the cryptography package is broken).
    """
    env_path = BASE_DIR / '.env'
    db_path  = BASE_DIR / 'db.sqlite3'
    print(f'[FANS-C] Initializing .env at: {env_path}')

    # -- Load python-dotenv.  It is always bundled; an ImportError here
    #    means the package is genuinely missing from the frozen build.
    try:
        from dotenv import load_dotenv, set_key as _dotenv_set_key
    except ImportError:
        _show_error(
            'FANS-C  --  Missing Dependency',
            'python-dotenv is not installed.\n\n'
            'This should not happen in a packaged build.\n'
            'Please reinstall the application.'
        )
        return False

    # -----------------------------------------------------------------------
    # Scenario 1 & 2: .env does not exist yet  --  write it from scratch
    # -----------------------------------------------------------------------
    if not env_path.is_file():
        print('[FANS-C] .env not found -- running first-run initialisation.')

        try:
            new_secret    = _new_secret_key()
            new_embed_key = _new_fernet_key()
        except Exception as exc:
            _show_error(
                'FANS-C  --  Key Generation Failed',
                f'Could not generate encryption keys:\n\n{exc}\n\n'
                'Check that the cryptography package is installed correctly.'
            )
            return False

        # Build .env content: try .env.example as template first so that all
        # the comment documentation is preserved for the operator; fall back
        # to the internal _ENV_TEMPLATE if the example is not present.
        example_path = BASE_DIR / '.env.example'
        if example_path.is_file():
            print(f'[FANS-C] Using .env.example as template: {example_path}')
            try:
                raw_lines = example_path.read_text(encoding='utf-8').splitlines(keepends=True)
                out_lines = []
                for line in raw_lines:
                    stripped = line.strip()
                    if stripped.startswith('SECRET_KEY='):
                        out_lines.append(f'SECRET_KEY={new_secret}\n')
                    elif stripped.startswith('EMBEDDING_ENCRYPTION_KEY='):
                        out_lines.append(f'EMBEDDING_ENCRYPTION_KEY={new_embed_key}\n')
                    elif stripped.startswith('DEBUG='):
                        # Packaged builds must run with DEBUG=False
                        out_lines.append('DEBUG=False\n')
                    else:
                        out_lines.append(line)
                content = ''.join(out_lines)
            except OSError:
                # Unreadable example -- fall back to internal template
                content = _ENV_TEMPLATE.format(
                    secret_key=new_secret, embedding_key=new_embed_key)
        else:
            content = _ENV_TEMPLATE.format(
                secret_key=new_secret, embedding_key=new_embed_key)

        try:
            env_path.write_text(content, encoding='utf-8')
        except OSError as exc:
            _show_error(
                'FANS-C  --  Cannot Write Configuration',
                f'Could not create .env at:\n  {env_path}\n\n'
                f'Error: {exc}\n\n'
                'Check that the installation folder is writable.\n'
                'Try running FANS-C as the same Windows user who installed it.'
            )
            return False

        # Scenario 2: an existing database was found alongside the missing .env
        db_exists = db_path.is_file()
        if db_exists:
            _show_warning(
                'FANS-C  --  First-Run Setup: Action May Be Required',
                '.env was created automatically with a NEW encryption key.\n\n'
                'An existing database was detected:\n'
                f'  {db_path}\n\n'
                'If this database already contains registered face data,\n'
                'the new key CANNOT decrypt it.  Verification will fail\n'
                'for all previously registered beneficiaries.\n\n'
                'To keep existing face data:\n'
                '  1. Locate the original .env from the previous installation.\n'
                '  2. Copy the EMBEDDING_ENCRYPTION_KEY value from it.\n'
                '  3. Open .env in the installation folder.\n'
                '  4. Replace EMBEDDING_ENCRYPTION_KEY with the original value.\n'
                '  5. Restart FANS-C.\n\n'
                'To start completely fresh (no existing data to preserve):\n'
                '  Delete db.sqlite3 and the media/ folder, then restart.\n'
                '  The newly generated key will work correctly.'
            )
        else:
            # Scenario 1: clean first install -- just inform the user
            _show_info(
                'FANS-C  --  First-Run Setup Complete',
                'FANS-C has been configured automatically.\n\n'
                'A unique encryption key and server secret have been\n'
                'generated and saved to:\n'
                f'  {env_path}\n\n'
                'IMPORTANT: Back up this file.\n\n'
                'The EMBEDDING_ENCRYPTION_KEY in .env is the only way\n'
                'to decrypt stored face embeddings.  If it is lost,\n'
                'all registered beneficiaries must re-register.'
            )

        # Load the freshly written values into the current process
        load_dotenv(dotenv_path=env_path, override=True)
        print('[FANS-C] .env created and loaded successfully.')
        return True

    # -----------------------------------------------------------------------
    # Scenario 3: .env already exists  --  load it and fill any gaps
    # -----------------------------------------------------------------------
    load_dotenv(dotenv_path=env_path, override=True)

    patched = []

    # -- Patch SECRET_KEY if it is missing or is a known placeholder ----------
    # SECRET_KEY does not affect face data; replacing it only invalidates
    # existing Django sessions (users will be logged out once).
    current_secret = os.getenv('SECRET_KEY', '').strip()
    if current_secret in _SECRET_KEY_PLACEHOLDERS:
        new_secret = _new_secret_key()
        try:
            # quote_mode='never' keeps the key unquoted, matching .env convention
            _dotenv_set_key(env_path, 'SECRET_KEY', new_secret, quote_mode='never')
            os.environ['SECRET_KEY'] = new_secret
            patched.append('SECRET_KEY')
        except Exception as exc:
            # Non-fatal: Django will use the placeholder, triggering its own warning
            print(f'[FANS-C] Could not update SECRET_KEY in .env: {exc}', file=sys.stderr)

    # -- Patch EMBEDDING_ENCRYPTION_KEY if it is missing or empty ------------
    # This key DOES affect face data; generate with a warning if needed.
    current_enc = os.getenv('EMBEDDING_ENCRYPTION_KEY', '').strip()
    if not current_enc:
        try:
            new_embed_key = _new_fernet_key()
        except Exception as exc:
            _show_error(
                'FANS-C  --  Key Generation Failed',
                f'EMBEDDING_ENCRYPTION_KEY is missing and could not be\n'
                f'generated automatically:\n\n{exc}'
            )
            return False

        try:
            _dotenv_set_key(env_path, 'EMBEDDING_ENCRYPTION_KEY', new_embed_key,
                            quote_mode='never')
            os.environ['EMBEDDING_ENCRYPTION_KEY'] = new_embed_key
            patched.append('EMBEDDING_ENCRYPTION_KEY')
        except Exception as exc:
            _show_error(
                'FANS-C  --  Cannot Update Configuration',
                f'Could not write EMBEDDING_ENCRYPTION_KEY to .env:\n\n{exc}\n\n'
                f'File: {env_path}\n\n'
                'Check that the installation folder is writable.'
            )
            return False

        # Warn if a database exists -- the new key cannot decrypt its data
        if db_path.is_file():
            _show_warning(
                'FANS-C  --  New Encryption Key Generated',
                'EMBEDDING_ENCRYPTION_KEY was missing from .env.\n'
                'A new key has been generated and saved automatically.\n\n'
                'An existing database was detected:\n'
                f'  {db_path}\n\n'
                'If this database contains face data encrypted with a\n'
                'previous key, that data is no longer readable.\n\n'
                'To recover existing data:\n'
                '  Replace EMBEDDING_ENCRYPTION_KEY in .env with the\n'
                '  original key, then restart FANS-C.'
            )

    if patched:
        print(f'[FANS-C] .env updated: {", ".join(patched)} generated.')

    # -- Validate that EMBEDDING_ENCRYPTION_KEY is a well-formed Fernet key --
    # This catches cases where the user pasted a corrupted or truncated key.
    enc_key = os.getenv('EMBEDDING_ENCRYPTION_KEY', '').strip()
    if not enc_key:
        # Should be unreachable after the patch above, but guard defensively
        _show_error(
            'FANS-C  --  Missing Encryption Key',
            'EMBEDDING_ENCRYPTION_KEY is still empty after attempting to\n'
            'generate it automatically.  The installation folder may not\n'
            f'be writable.\n\n'
            f'Installation folder:\n  {BASE_DIR}'
        )
        return False

    try:
        from cryptography.fernet import Fernet
        Fernet(enc_key.encode() if isinstance(enc_key, str) else enc_key)
    except Exception as exc:
        _show_error(
            'FANS-C  --  Invalid Encryption Key',
            f'EMBEDDING_ENCRYPTION_KEY in .env is not a valid Fernet key:\n\n'
            f'  {exc}\n\n'
            'To generate a valid key, open a terminal and run:\n'
            '  python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"\n\n'
            'Paste the output into .env as:\n'
            '  EMBEDDING_ENCRYPTION_KEY=<the-key>\n\n'
            'WARNING: changing the key makes all stored face data unreadable.\n'
            'Beneficiaries will need to re-register if you replace the key.'
        )
        return False

    print('[FANS-C] Environment validated.')
    return True


# ---------------------------------------------------------------------------
# Django setup and migrations
# ---------------------------------------------------------------------------

def _setup_django():
    """
    Configure Django for the packaged environment and apply migrations.

    Why DEBUG=False for packaged builds?
      In packaged mode, whitenoise serves static files from staticfiles/.
      whitenoise's CompressedManifestStaticFilesStorage requires DEBUG=False
      to serve the hashed/compressed files correctly.  In source mode the
      developer controls DEBUG via .env as usual.

    Returns True on success, False if Django setup or migrations failed.
    """
    # Force production-like settings when running as a frozen bundle.
    # The auto-generated .env already sets DEBUG=False, but this setdefault
    # ensures correctness even if the user has not yet set it explicitly.
    if getattr(sys, 'frozen', False):
        os.environ.setdefault('DEBUG', 'False')

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fans.settings')

    try:
        import django
        django.setup()
        print('[FANS-C] Django setup complete.')
    except Exception as exc:
        _show_error(
            'FANS-C  --  Django Initialisation Failed',
            f'Django could not initialise:\n\n{exc}\n\n'
            'Check that .env contains valid settings.\n'
            'See the console for a full traceback.'
        )
        import traceback
        traceback.print_exc()
        return False

    # Apply pending migrations (creates db.sqlite3 if it does not exist yet)
    try:
        from django.core.management import call_command
        print('[FANS-C] Applying database migrations ...')
        call_command('migrate', '--noinput', verbosity=1)
        print('[FANS-C] Migrations complete.')
    except Exception as exc:
        # Warn but do not abort -- the server may still start if the DB is intact
        _show_warning(
            'FANS-C  --  Migration Warning',
            f'Database migration encountered an error:\n\n{exc}\n\n'
            'The application will still attempt to start.\n'
            'Some features may not work correctly until migrations succeed.'
        )

    return True


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------

def _start_server_thread():
    """
    Start the Django application server in a background daemon thread.

    Packaged build  -> waitress WSGI server (reliable inside PyInstaller)
    Source / dev    -> Django runserver with --noreload

    The thread is a daemon so it dies automatically when the main process
    exits (e.g. the user closes the console window or sends Ctrl+C).
    """
    def _serve():
        if getattr(sys, 'frozen', False):
            # -- Packaged: use waitress ---------------------------------------
            # waitress is a pure-Python threaded WSGI server.  It does not use
            # multiprocessing or autoreload, making it safe inside PyInstaller.
            try:
                from waitress import serve
                from fans.wsgi import application
                print(f'[FANS-C] Starting waitress on {APP_URL} ...')
                serve(
                    application,
                    host=HOST,
                    port=PORT,
                    threads=4,
                    # Suppress waitress's own banner to avoid duplicate messages
                    _quiet=True,
                )
            except ImportError:
                # waitress not available -- fall back to Django runserver
                print('[FANS-C] waitress not found, falling back to runserver --noreload')
                _run_devserver()
            except Exception as exc:
                _show_error('FANS-C  --  Server Error', f'The web server crashed:\n\n{exc}')
                import traceback
                traceback.print_exc()
        else:
            _run_devserver()

    def _run_devserver():
        """Use Django's built-in server (development / fallback)."""
        from django.core.management import call_command
        print(f'[FANS-C] Starting Django runserver on {APP_URL} ...')
        # use_reloader=False is critical: the autoreloader uses subprocess.Popen
        # to re-launch the process, which breaks inside a PyInstaller bundle.
        call_command('runserver', f'{HOST}:{PORT}', '--noreload', use_reloader=False)

    t = threading.Thread(target=_serve, name='fans-c-server', daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------------------
# Port availability poll
# ---------------------------------------------------------------------------

def _wait_for_server(timeout=60):
    """
    Poll HOST:PORT until the server is accepting TCP connections.

    Why poll instead of just sleeping?
      On slower machines TensorFlow can take 10-20 seconds to load on the
      first request.  A fixed sleep would either be too short (browser opens
      to an error page) or too long (wastes time on fast machines).

    Returns True if the server became available within `timeout` seconds.
    """
    print('[FANS-C] Waiting for server to become ready ...')
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                print('[FANS-C] Server is ready.')
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    """
    Full startup sequence for FANS-C.

    Exits with a non-zero code if a fatal error occurs at any step.
    """
    print()
    print('  ================================================================')
    print('   FANS-C  |  FaceNet Facial Verification System  |  Starting ...  ')
    print('  ================================================================')
    print()

    # Step 1  --  ensure .env exists with valid keys
    # On a clean first install this creates .env automatically.
    # On subsequent launches it validates the existing file.
    if not _init_env():
        sys.exit(1)

    # Step 2  --  Django setup + migrations
    if not _setup_django():
        sys.exit(1)

    # Step 3  --  start the server
    server_thread = _start_server_thread()

    # Step 4  --  wait for the server port to open
    if not _wait_for_server(timeout=90):
        _show_error(
            'FANS-C  --  Startup Timeout',
            f'The server did not start within 90 seconds.\n\n'
            f'Check the console output for error messages.\n\n'
            f'Common causes:\n'
            f'  * TensorFlow failed to load (check .venv / Python 3.11)\n'
            f'  * Port {PORT} is already in use by another application\n'
            f'  * A missing dependency (see console for ImportError)'
        )
        sys.exit(1)

    # Step 5  --  open the browser
    print(f'[FANS-C] Opening browser at {APP_URL}')
    webbrowser.open(APP_URL)

    print()
    print(f'  FANS-C is running at {APP_URL}')
    print('  Close this window to stop the server.')
    print()

    # Step 6  --  keep the main thread alive while the server thread runs
    # The server thread is a daemon; when the user closes the console window
    # (or sends Ctrl+C), the OS kills all threads including this one.
    try:
        while server_thread.is_alive():
            server_thread.join(timeout=1.0)
    except KeyboardInterrupt:
        print('\n[FANS-C] Shutting down ...')


if __name__ == '__main__':
    main()
