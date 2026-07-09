#!/usr/bin/env python3
"""
JEB Pro Skill Setup Script

This script validates the environment and configures dependencies required for
the JEB Pro scripting skill. Run this before using the skill for the first time.

Unlike Binary Ninja (whose Python package ships with the app), JEB Pro is a
Java application. This script locates the JEB installation, creates a uv-managed
virtual environment for this skill's own Python needs, and writes `_jeb_config.json`
so that run.py can locate the JEB runtime.

Usage:
    uv run python setup.py

Steps performed:
    1. Check that uv package manager is installed
    2. Locate the JEB Pro installation
    3. Run uv sync to create the virtual environment
    4. Write _jeb_config.json (consumed by run.py)
    5. Verify JEB can be launched

Exit codes:
    0 - Success, setup complete
    1 - Error occurred (check output for details)
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ANSI color codes for terminal output
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_step(step_num: int, message: str) -> None:
    """Print a numbered step header."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}[{step_num}/5]{Colors.RESET} {message}")


def print_warning(message: str) -> None:
    print(f"  {Colors.YELLOW}!{Colors.RESET} {message}")


def print_success(message: str) -> None:
    print(f"  {Colors.GREEN}✓{Colors.RESET} {message}")


def print_error(message: str) -> None:
    print(f"  {Colors.RED}✗{Colors.RESET} {message}")


def print_info(message: str) -> None:
    print(f"  {Colors.YELLOW}→{Colors.RESET} {message}")


def get_skill_dir() -> Path:
    """Get the directory containing this setup script."""
    return Path(__file__).parent.resolve()


def check_uv() -> bool:
    """Step 1: Check that uv package manager is installed."""
    print_step(1, "Checking for uv package manager...")

    try:
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        version = result.stdout.strip()
        print_success(f"uv is installed ({version})")
        return True
    except FileNotFoundError:
        print_error("uv is not installed")
        print()
        print("  Please install uv using one of these methods:")
        print()
        print(f"  {Colors.BOLD}macOS/Linux:{Colors.RESET}")
        print("    curl -LsSf https://astral.sh/uv/install.sh | sh")
        print()
        print(f"  {Colors.BOLD}Windows:{Colors.RESET}")
        print('    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"')
        print()
        print("  For more options, see: https://docs.astral.sh/uv/getting-started/installation/")
        return False
    except subprocess.CalledProcessError as e:
        print_error(f"uv check failed: {e.stderr.strip()}")
        return False
    except subprocess.TimeoutExpired:
        print_error("uv version check timed out after 30 seconds")
        return False


# Default JEB Pro install locations
DEFAULT_JEB_INSTALL_DIRS = [
    # Linux common
    "/opt/jeb",
    "/opt/jeb-pro",
    "/opt/jebpro",
    os.path.expanduser("~/jeb"),
    os.path.expanduser("~/jeb-pro"),
    # macOS common
    "/Applications/JEB.app",
    "/Applications/JEB Pro.app",
    os.path.expanduser("~/Applications/JEB.app"),
    os.path.expanduser("~/Applications/JEB Pro.app"),
    # Windows (Git Bash / WSL)
    "C:/Program Files/JEB",
    "C:/Program Files/JEB Pro",
    "C:/jeb",
]


def _jeb_exec_is_valid(install_dir: Path) -> bool:
    """True if the install dir contains a valid JEB launcher."""
    candidates = [
        install_dir / "bin" / "jeb",
        install_dir / "jeb",
        install_dir / "bin" / "jeb.sh",
        install_dir / "bin" / "jeb.exe",
        install_dir / "jeb_macos.sh",
        install_dir / "jeb_linux.sh",
        install_dir / "jeb_wincon.bat",
    ]
    for c in candidates:
        if c.exists():
            return True
    return False


def detect_jeb_install() -> Optional[Path]:
    """
    Step 2: Locate the JEB Pro installation.

    Order of resolution:
      1. JEB_DIR environment variable
      2. jeb on PATH (check if it's a script pointing to a JEB install)
      3. A set of well-known default locations per OS

    Returns:
        Path to the JEB install dir, or None.
    """
    print_step(2, "Locating JEB Pro installation...")

    # 1. Env var
    env_dir = os.environ.get("JEB_DIR")
    if env_dir:
        candidate = Path(env_dir).expanduser()
        if _jeb_exec_is_valid(candidate):
            print_success(f"Found via JEB_DIR: {candidate}")
            return candidate
        print_warning(f"JEB_DIR={env_dir} does not contain a valid JEB launcher (bin/jeb)")

    # 2. Check PATH for jeb
    try:
        result = subprocess.run(
            ["which", "jeb"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            jeb_path = Path(result.stdout.strip()).resolve()
            # jeb is usually a symlink: .../jeb/bin/jeb -> install_dir = .../jeb
            install_dir = jeb_path.parent.parent if jeb_path.parent.name == "bin" else jeb_path.parent
            if _jeb_exec_is_valid(install_dir):
                print_success(f"Found via PATH: {install_dir} (from {jeb_path})")
                return install_dir
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 3. Default locations
    for d in DEFAULT_JEB_INSTALL_DIRS:
        candidate = Path(d).expanduser()
        if _jeb_exec_is_valid(candidate):
            print_success(f"Found at default location: {candidate}")
            return candidate

    print_error("Could not locate the JEB Pro installation.")
    print()
    print("  Set JEB_DIR to the directory containing bin/jeb:")
    print()
    print(f"  {Colors.BOLD}Linux:{Colors.RESET}     export JEB_DIR=\"/opt/jeb\"")
    print(f"  {Colors.BOLD}macOS:{Colors.RESET}     export JEB_DIR=\"/Applications/JEB.app\"")
    print(f"  {Colors.BOLD}Windows:{Colors.RESET}   set JEB_DIR=C:\\\\jeb")
    print()
    print("  Tip: The JEB installation directory is the one containing")
    print("  bin/jeb (launcher) and bin/app/ (JAR files).")
    return None


def run_uv_sync() -> bool:
    """Step 3: Run uv sync to create the virtual environment."""
    print_step(3, "Creating virtual environment with uv sync...")

    skill_dir = get_skill_dir()
    try:
        subprocess.run(
            ["uv", "sync"],
            cwd=skill_dir,
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
        )
        print_success("Virtual environment created")
        return True
    except subprocess.CalledProcessError as e:
        print_error("uv sync failed")
        print()
        print("  Error output:")
        for line in (e.stderr or e.stdout or "Unknown error").strip().split("\n"):
            print(f"    {line}")
        return False
    except subprocess.TimeoutExpired:
        print_error("uv sync timed out after 5 minutes")
        return False


def write_jeb_config(install_dir: Path) -> bool:
    """Step 4: Write _jeb_config.json (consumed by run.py)."""
    print_step(4, "Writing _jeb_config.json...")

    skill_dir = get_skill_dir()
    config = {
        "install_dir": str(install_dir),
    }
    config_path = skill_dir / "_jeb_config.json"
    try:
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print_success(f"Wrote {config_path}")
        print_info(f"install_dir: {config['install_dir']}")
        return True
    except OSError as e:
        print_error(f"Failed to write config: {e}")
        return False


def check_java() -> bool:
    """Check that Java is available."""
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Java prints version to stderr
        version_output = result.stderr or result.stdout
        if result.returncode == 0 or "version" in version_output.lower():
            # Extract first line
            version_line = version_output.strip().split("\n")[0] if version_output else "unknown"
            print_success(f"Java found: {version_line}")
            return True
        return False
    except FileNotFoundError:
        print_warning("java not found on PATH — JEB requires a JDK 11+")
        return False
    except subprocess.TimeoutExpired:
        print_warning("Java version check timed out")
        return False


def run_validation_test(install_dir: Path) -> bool:
    """Step 5: Verify JEB can launch (version check only, no license needed)."""
    print_step(5, "Running JEB validation test...")

    # Find the jeb executable
    candidates = [
        install_dir / "bin" / "jeb",
        install_dir / "jeb",
        install_dir / "bin" / "jeb.sh",
        install_dir / "jeb_macos.sh",
        install_dir / "jeb_linux.sh",
        install_dir / "jeb_wincon.bat",
    ]
    jeb_exec = None
    for c in candidates:
        if c.exists():
            jeb_exec = c
            break

    if jeb_exec is None:
        print_error("JEB executable not found in installation directory")
        return False

    # Check Java first
    java_ok = check_java()

    # Try to launch JEB with --version or just check it exists
    try:
        # JEB might not have a --version flag; just check the file is executable
        if os.access(jeb_exec, os.X_OK):
            print_success(f"JEB launcher found: {jeb_exec}")
            if java_ok:
                print_info("JEB should be able to launch. Verify by running:")
                print_info(f"  {jeb_exec} -c --help")
            else:
                print_warning("Java not detected. Install JDK 11+ to use JEB.")
            return True
        else:
            # Try running it as a shell script
            result = subprocess.run(
                ["sh", str(jeb_exec), "--help"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode in (0, 1, 2):  # --help often returns non-zero
                print_success(f"JEB launcher found: {jeb_exec}")
                return True
            return False
    except subprocess.TimeoutExpired:
        print_warning("JEB launch check timed out — launcher may work but took too long")
        return True
    except Exception as e:
        print_warning(f"Could not validate JEB launch: {e}")
        print_info(f"JEB launcher found at: {jeb_exec}")
        return True  # Not a hard error; user can try manually


def main() -> int:
    print(f"\n{Colors.BOLD}JEB Pro Skill Setup{Colors.RESET}")
    print("=" * 50)

    if not check_uv():
        return 1

    install_dir = detect_jeb_install()
    if install_dir is None:
        return 1

    if not run_uv_sync():
        return 1

    if not write_jeb_config(install_dir):
        return 1

    if not run_validation_test(install_dir):
        return 1

    print()
    print("=" * 50)
    print(f"{Colors.GREEN}{Colors.BOLD}Setup complete! Ready to use.{Colors.RESET}")
    print()
    print("Next steps:")
    print("  - Write scripts to /tmp/jeb-<timestamp>-<name>/script.py")
    print("  - Execute with: uv run python run.py <work_dir>/script.py -f <binary>")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
