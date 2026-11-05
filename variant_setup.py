"""First-run installation shared by the three optional game frontends."""
from __future__ import annotations

import importlib
from importlib import metadata
import re
import os
from pathlib import Path
import shlex
import subprocess
import sys

ENV_DIR = Path(__file__).resolve().parent / '.venv-variants'


def _ready(requirements: dict[str, str]) -> bool:
    os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
    for module, requirement in requirements.items():
        try:
            match = re.fullmatch(r'([A-Za-z0-9_.-]+)(?:>=([0-9]+(?:\.[0-9]+)*))?', requirement)
            if match is None:
                raise ValueError(f'Unsupported dependency specification: {requirement}')
            distribution, minimum = match.groups()
            if minimum:
                installed = metadata.version(distribution)
                release = re.match(r'([0-9]+(?:\.[0-9]+)*)(.*)', installed)
                if release is None:
                    return False
                current = tuple(int(part) for part in release.group(1).split('.'))
                required = tuple(int(part) for part in minimum.split('.'))
                length = max(len(current), len(required))
                current += (0,) * (length-len(current))
                required += (0,) * (length-len(required))
                if current < required or (current == required and re.search(r'(?:a|b|rc|dev)', release.group(2))):
                    return False
            imported = importlib.import_module(module)
            if module == 'pygame' and not getattr(imported, 'IS_CE', False):
                return False
        except (ImportError, OSError, metadata.PackageNotFoundError):
            return False
    return True


def _stream(command: list[str]) -> bool:
    """Inherit stdout/stderr so package download/build logs remain visible."""
    try:
        return subprocess.run(command, check=False).returncode == 0
    except OSError as error:
        print(f'Setup error: {error}', flush=True)
        return False


def ensure_runtime(requirements: dict[str, str]) -> None:
    """Check modules, install missing runtimes in an isolated venv, then restart.

    Never invokes pip against system Python. The same invocation works on later
    launches and reuses its environment without installing packages again.
    """
    if sys.version_info < (3, 10):
        raise SystemExit('Python 3.10 or newer is required.')
    if _ready(requirements):
        return
    python = ENV_DIR / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    in_managed_env = Path(sys.prefix).resolve() == ENV_DIR.resolve()
    if not in_managed_env and python.is_file():
        os.execv(str(python), [str(python), *sys.argv])
        return

    packages = list(dict.fromkeys(requirements.values()))
    print('\nNEON DOJO — dependency setup', flush=True)
    print('[###-------] 30% Preparing isolated Python environment', flush=True)
    if not in_managed_env and not _stream([sys.executable, '-m', 'venv', str(ENV_DIR)]):
        print('Install Python venv/ensurepip support (Debian/Ubuntu: sudo apt install python3-venv).')
        print('Then run: ' + shlex.join([sys.executable, '-m', 'venv', str(ENV_DIR)]))
        raise SystemExit(1)
    command = [str(python), '-m', 'pip', 'install', *packages]
    print('[######----] 60% Installing game dependencies', flush=True)
    print('Manual command: ' + shlex.join(command), flush=True)
    if not _stream(command):
        print('Installation failed. Run the manual command above, then launch again.')
        raise SystemExit(1)
    # A separate interpreter validates installed binaries rather than reusing
    # failed imports cached in this interpreter.
    check = (f'import sys; sys.path.insert(0, {str(Path(__file__).resolve().parent)!r}); '
             f'from variant_setup import _ready; sys.exit(0 if _ready({requirements!r}) else 1)')
    if not _stream([str(python), '-c', check]):
        raise SystemExit('Installed package could not load. Check the errors above.')
    print('[##########] 100% Ready — launching the game', flush=True)
    os.execv(str(python), [str(python), *sys.argv])
