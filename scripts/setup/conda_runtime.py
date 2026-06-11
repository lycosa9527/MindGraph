"""Resolve the active miniconda environment for MindGraph setup and pip installs."""

from __future__ import annotations

import os
import subprocess
import sys
import sysconfig
from typing import Callable, List, Optional

DEFAULT_CONDA_ENV = "mindgraph"


class CondaRuntimeError(Exception):
    """Raised when the miniconda environment cannot be resolved."""


def conda_env_name() -> str:
    """Conda environment name (override with ``MINDGRAPH_CONDA_ENV``)."""
    configured = os.environ.get("MINDGRAPH_CONDA_ENV", DEFAULT_CONDA_ENV).strip()
    return configured or DEFAULT_CONDA_ENV


def is_conda_env_active() -> bool:
    """Return True when the current interpreter runs inside a conda environment."""
    prefix = os.environ.get("CONDA_PREFIX", "").strip()
    if not prefix:
        return False
    try:
        real_exe = os.path.realpath(sys.executable)
        real_root = os.path.realpath(prefix)
        if real_exe == os.path.join(real_root, "bin", "python"):
            return True
        if real_exe == os.path.join(real_root, "Scripts", "python.exe"):
            return True
        return real_exe.startswith(real_root + os.sep)
    except OSError:
        return False


def _runtime_sudo_user() -> str:
    return os.environ.get("SUDO_USER", "").strip()


def _running_as_root() -> bool:
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def _conda_install_roots(home: str) -> List[str]:
    return [
        os.path.join(home, name)
        for name in ("miniconda3", "anaconda3", "miniforge3", "mambaforge")
    ]


def find_conda_python(home: str, env_name: str) -> Optional[str]:
    """Return the conda env Python path for ``home`` and ``env_name`` when present."""
    for base in _conda_install_roots(home):
        if env_name == "base":
            candidate = os.path.join(base, "bin", "python")
            if os.path.isfile(candidate):
                return candidate
            continue
        candidate = os.path.join(base, "envs", env_name, "bin", "python")
        if os.path.isfile(candidate):
            return candidate
    return None


def _command_as_project_user(command: List[str]) -> List[str]:
    """Prefix command with ``sudo -u`` when setup was started with sudo."""
    sudo_user = _runtime_sudo_user()
    if sudo_user and _running_as_root():
        return ["sudo", "-u", sudo_user, "-H", *command]
    return command


def run_as_project_user(
    command: List[str],
    *,
    cwd: Optional[str] = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command as the invoking user when setup was started with sudo."""
    return subprocess.run(
        _command_as_project_user(command),
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def run_as_project_user_streaming(
    command: List[str],
    *,
    cwd: Optional[str] = None,
    on_line: Optional[Callable[[str], None]] = None,
) -> int:
    """Run a command with live stdout, optionally invoking ``on_line`` per line."""
    process = subprocess.Popen(
        _command_as_project_user(command),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    stdout = process.stdout
    if stdout is not None:
        for output in stdout:
            line = output.rstrip("\n")
            if on_line is not None:
                on_line(line)
    return process.wait()


def _externally_managed_marker_paths() -> List[str]:
    """Candidate EXTERNALLY-MANAGED marker paths for the active interpreter."""
    markers: List[str] = []
    version_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for prefix in (sys.prefix, sys.base_prefix):
        markers.append(
            os.path.join(prefix, "lib", version_dir, "EXTERNALLY-MANAGED")
        )
    stdlib = sysconfig.get_path("stdlib", vars=sysconfig.get_config_vars())
    if stdlib:
        markers.append(os.path.join(stdlib, "EXTERNALLY-MANAGED"))
    return markers


def is_externally_managed_environment() -> bool:
    """Return True when PEP 668 blocks system-wide pip installs."""
    for marker in _externally_managed_marker_paths():
        if marker and os.path.isfile(marker):
            return True
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--dry-run", "pip"],
        check=False,
        capture_output=True,
        text=True,
    )
    combined = f"{result.stdout}\n{result.stderr}".lower()
    return "externally-managed-environment" in combined


def _conda_activation_hint() -> str:
    env_name = conda_env_name()
    return (
        f"Activate the miniconda env first: conda activate {env_name}\n"
        "Create it if needed: conda create -n mindgraph python=3.13 -y\n"
        "With sudo for system packages:\n"
        f'  conda activate {env_name} && sudo -E env PATH="$PATH" '
        '"$(which python)" scripts/setup/setup.py'
    )


def resolve_python_for_project(project_root: str) -> str:
    """Return the conda Python executable for pip and runtime checks."""
    del project_root
    if is_conda_env_active():
        return sys.executable

    sudo_user = _runtime_sudo_user()
    if sudo_user and _running_as_root():
        home = os.path.expanduser(f"~{sudo_user}")
        found = find_conda_python(home, conda_env_name())
        if found:
            return found

    raise CondaRuntimeError(_conda_activation_hint())


def ensure_pip_available(python_executable: str, project_root: str) -> None:
    """Verify pip is available for the chosen interpreter."""
    result = run_as_project_user(
        [python_executable, "-m", "pip", "--version"],
        cwd=project_root,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise CondaRuntimeError(
            f"pip is not available for {python_executable}. {details}"
        )


def prepare_project_python(project_root: str) -> str:
    """
    Resolve the conda Python for dependency installs.

    Returns:
        Absolute path to the Python executable to use for pip and runtime checks.
    """
    python_executable = resolve_python_for_project(project_root)
    if python_executable != sys.executable:
        print(f"[INFO] Using conda Python: {python_executable}")
    else:
        print(f"[INFO] Using active conda environment: {python_executable}")
    ensure_pip_available(python_executable, project_root)
    return python_executable
