#!/usr/bin/env python3
"""
JEB Pro Universal Script Executor

Executes Python scripts that use the JEB Pro API with automatic boilerplate
wrapping. This is the main entry point for AI-generated analysis scripts.

The executor wraps user scripts as JEB IScript implementations, launches JEB
in headless mode (Jython runtime), and captures the output.

IMPORTANT: JEB uses Jython (Python 2.7 compatible). Generated wrapper code
must be Jython-compatible - no f-strings, no type hints, no Python 3 features.
The IScript class name must match the script filename (without .py extension).

Usage:
    # 1. Execute a script file
    uv run python run.py <work_dir>/script.py -f /path/to/binary.exe

    # 2. Execute inline code
    uv run python run.py -c "for u in prj.getUnits(): print(u.getName())" -f binary.exe

Command-line flags:
    -f, --file      Target binary or .jdb2 file (required)
    -c, --code      Inline code string
    -s, --save      Persist the .jdb2 after execution (default: False)
    --no-wrap       Skip auto-wrapping (for complete IScript implementations)
    --timeout       Execution timeout in seconds (default: 1800, 0 for no timeout)

Exit codes:
    0 - Success
    1 - Error (setup, parsing, execution)
    124 - Timeout
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path


# ANSI color codes for terminal output
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_error(message: str) -> None:
    print(f"{Colors.RED}Error:{Colors.RESET} {message}", file=sys.stderr)


def print_warning(message: str) -> None:
    print(f"{Colors.YELLOW}Warning:{Colors.RESET} {message}", file=sys.stderr)


def print_info(message: str) -> None:
    print(f"{Colors.BLUE}Info:{Colors.RESET} {message}", file=sys.stderr)


def get_skill_dir() -> Path:
    """Get the directory containing this run script."""
    return Path(__file__).parent.resolve()


def load_jeb_config() -> dict:
    """Read _jeb_config.json written by setup.py (contains JEB install path)."""
    cfg_path = get_skill_dir() / "_jeb_config.json"
    if not cfg_path.exists():
        return {}
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def check_venv_exists() -> bool:
    """Check if the virtual environment exists."""
    venv_path = get_skill_dir() / ".venv"
    return venv_path.exists() and venv_path.is_dir()


def prompt_setup() -> None:
    """Print instructions to run setup if venv is missing."""
    skill_dir = get_skill_dir()
    print_error("Virtual environment not found.")
    print()
    print("Please run setup first:")
    print()
    print(f"  cd {skill_dir}")
    print("  uv run python setup.py")
    print()


def find_jeb_executable(jeb_dir: Path) -> Path | None:
    """Find the JEB launcher executable in the JEB installation directory."""
    candidates = [
        jeb_dir / "bin" / "jeb",
        jeb_dir / "jeb",
        jeb_dir / "bin" / "jeb.sh",
        jeb_dir / "bin" / "jeb.exe",  # Windows (wsl/git-bash)
        jeb_dir / "jeb_macos.sh",
        jeb_dir / "jeb_linux.sh",
        jeb_dir / "jeb_wincon.bat",
    ]
    for candidate in candidates:
        if candidate.exists() and (os.access(candidate, os.X_OK) or candidate.suffix == '.exe'):
            return candidate
    return None


def cleanup_old_temp_files() -> int:
    """Remove temp files and dirs older than 1 hour from crashed/abandoned runs."""
    cleaned = 0
    cutoff_time = time.time() - 3600  # 1 hour ago
    temp_dir = tempfile.gettempdir()

    # Old flat script files (legacy)
    for filepath in glob.glob(str(Path(temp_dir) / "jeb_*.py")):
        try:
            p = Path(filepath)
            if p.is_file() and p.stat().st_mtime < cutoff_time:
                p.unlink()
                cleaned += 1
        except (OSError, PermissionError):
            pass

    # Abandoned run directories
    for dirpath in glob.glob(str(Path(temp_dir) / "jeb-run-*")):
        try:
            p = Path(dirpath)
            if p.is_dir() and p.stat().st_mtime < cutoff_time:
                shutil.rmtree(p)
                cleaned += 1
        except (OSError, PermissionError):
            pass

    return cleaned


def get_user_code(args: argparse.Namespace) -> tuple[str, str]:
    """Get user code from input modes."""
    has_script_file = args.script is not None
    has_inline_code = args.code is not None
    has_stdin = not sys.stdin.isatty()

    input_count = sum([has_script_file, has_inline_code, has_stdin])

    if input_count == 0:
        raise ValueError("No script provided. Use a script file, -c for inline code, or pipe from stdin.")

    if input_count > 1:
        if has_script_file and has_stdin:
            has_stdin = False
        elif has_inline_code and has_stdin:
            has_stdin = False
        elif has_script_file and has_inline_code:
            raise ValueError("Cannot use both script file and -c inline code. Choose one.")

    if has_script_file:
        script_path = Path(args.script)
        if not script_path.exists():
            raise ValueError(f"Script file not found: {script_path}")
        if not script_path.is_file():
            raise ValueError(f"Not a file: {script_path}")
        code = script_path.read_text(encoding="utf-8")
        return code, f"file: {script_path}"

    if has_inline_code:
        return args.code, "inline code (-c)"

    if has_stdin:
        code = sys.stdin.read()
        if not code.strip():
            raise ValueError("Empty input from stdin.")
        return code, "stdin"

    raise ValueError("No script provided.")


def wrap_code(user_code: str, save_on_close: bool, class_name: str,
              failure_token: str) -> str:
    """
    Wrap user code with JEB IScript boilerplate (Jython-compatible).

    The wrapper:
    - Implements IScript interface with class named after the script file
      (JEB requires the IScript class to match the filename stem)
    - Exposes ctx (IClientContext) and prj (IProject) variables
    - Handles project save on close if requested

    IMPORTANT: JEB uses Jython (Python 2.7). Generated code must be
    Jython-compatible - no f-strings, no type hints, no Python 3 features.
    """
    indented_code = "\n".join(
        "            " + line if line.strip() else line for line in user_code.split("\n")
    )

    save_block = ""
    if save_on_close:
        save_block = (
            "            # Save the project before exiting\n"
            "            try:\n"
            "                prj.save()\n"
            '                print("[JEB run.py] Project saved.")\n'
            "            except Exception as _save_err:\n"
            '                print("[JEB run.py] Warning: failed to save project: %%s" %% _save_err)\n'
        )

    wrapper = (
        "# Auto-wrapped by JEB run.py (Jython-compatible)\n"
        "import os as _os\n"
        "import sys as _sys\n"
        "import traceback as _traceback\n"
        "\n"
        "# Import JEB client API\n"
        "try:\n"
        "    from com.pnfsoftware.jeb.client.api import IScript\n"
        "except ImportError:\n"
        '    _sys.stderr.write("[JEB run.py] Error: Could not import JEB API.\\n")\n'
        "    _sys.exit(1)\n"
        "\n"
        "\n"
        "class %s(IScript):\n"
        '    """Auto-generated JEB analysis script."""\n'
        "\n"
        "    def run(self, ctx):\n"
        '        """Main entry point for JEB scripts."""\n'
        "        prj = ctx.getMainProject()\n"
        "        if prj is None:\n"
        '            _sys.stderr.write("[JEB run.py] Error: No project loaded.\\n")\n'
        "            return\n"
        "\n"
        "        try:\n"
        "            # === User code starts here ===\n"
        "%s\n"
        "            # === User code ends here ===\n"
        "%s"
        "        except Exception as _e:\n"
        '            _sys.stderr.write("__JEB_RUNPY_SCRIPT_FAILED__:%s: %%s\\n" %% str(_e))\n'
        "            _traceback.print_exc(file=_sys.stderr)\n"
        "            raise\n"
        % (class_name, indented_code, save_block, failure_token)
    )
    return wrapper


def execute_script(code: str, target_file: str, jeb_exec: Path,
                   script_name: str = "jeb_script",
                   failure_token: str = "",
                   timeout: int | None = None) -> int:
    """Execute the script via JEB headless mode.

    script_name is the Python identifier stem for the temp file.
    JEB (Jython) requires the IScript class name to match the filename stem.
    failure_token is a UUID embedded in the wrapper's error output so run.py
    can reliably detect script failures regardless of user output.
    """
    skill_dir = get_skill_dir()

    # Write script into a private 0700 temp directory to avoid
    # predictable-stem collisions in the shared temp root.
    run_dir = tempfile.mkdtemp(prefix="jeb-run-", dir=tempfile.gettempdir())
    os.chmod(run_dir, 0o700)
    temp_script = os.path.join(run_dir, "%s.py" % script_name)

    # Write the wrapped script to the temp file
    with open(temp_script, "w", encoding="utf-8") as f:
        f.write(code)

    try:
        # Build command: jeb -c --script=<temp_script> --infile=<target_file>
        cmd = [
            str(jeb_exec),
            "-c",               # Console/headless mode
            "--script=%s" % temp_script,
            "--infile=%s" % target_file,
        ]
        print_info("Launching JEB headless: %s" % " ".join(cmd))

        # JEB is a Java app and may have significant startup time.
        process = subprocess.Popen(
            cmd,
            cwd=skill_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "JEB_HEADLESS": "1"},
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout)
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            print_error("Script execution timed out after %d seconds." % timeout)
            print()
            print("To increase the timeout, use the --timeout flag:")
            print("  uv run python run.py --timeout 3600 ...")
            print()
            print("To disable the timeout entirely, use --timeout 0")
            return 124

        # Print all captured output
        if stdout:
            print(stdout.rstrip())
        if stderr:
            print(stderr.rstrip(), file=sys.stderr)

        # JEB always exits 0 even on script errors. Two-tier detection:
        # 1. UUID sentinel from wrapped scripts (reliable, no false positives)
        # 2. JEB's own fatal thread-crash pattern (fallback for --no-wrap scripts)
        if failure_token:
            sentinel = "__JEB_RUNPY_SCRIPT_FAILED__:%s" % failure_token
            if (stdout and sentinel in stdout) or (stderr and sentinel in stderr):
                return 1
        # 2. JEB's own fatal thread-crash pattern, matched per-line
        #    to avoid false positives from user output containing the words.
        _crash_re = re.compile(r"^\[C\] Thread.*terminated unexpectedly$")
        if stdout and any(_crash_re.match(line) for line in stdout.splitlines()):
            return 1

        return returncode

    except FileNotFoundError:
        print_error("JEB executable not found: %s" % jeb_exec)
        print()
        print("Please run setup to detect JEB installation:")
        print("  cd %s && uv run python setup.py" % skill_dir)
        print()
        print("Or set JEB_DIR to your JEB installation directory:")
        print('  export JEB_DIR="/opt/jeb"')
        return 1
    except KeyboardInterrupt:
        print_warning("Execution interrupted by user.")
        return 130
    finally:
        try:
            shutil.rmtree(run_dir)
        except OSError:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute JEB Pro scripts with automatic IScript wrapping.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Execute a script file
  uv run python run.py /tmp/analyze.py -f /path/to/binary.exe

  # Execute inline code
  uv run python run.py -c "for u in prj.getUnits(): print(u.getName())" -f binary.exe

  # Execute from stdin
  cat /tmp/analyze.py | uv run python run.py -f binary.exe

  # Execute without wrapping (complete IScript)
  uv run python run.py /tmp/full_script.py --no-wrap -f binary.exe

  # Execute and persist a .jdb2
  uv run python run.py -c "..." -f binary.exe -s
""",
    )

    parser.add_argument("script", nargs="?", help="Path to Python script file to execute")
    parser.add_argument("-f", "--file", dest="target", required=True,
                        help="Target binary or .jdb2 file (required)")
    parser.add_argument("-c", "--code", dest="code", help="Inline Python code to execute")
    parser.add_argument("-s", "--save", dest="save", action="store_true", default=False,
                        help="Persist a .jdb2 after execution (default: False)")
    parser.add_argument("--no-wrap", dest="no_wrap", action="store_true", default=False,
                        help="Skip auto-wrapping (for complete IScript implementations)")
    parser.add_argument("--timeout", dest="timeout", type=int, default=1800,
                        help="Execution timeout in seconds (default: 1800 = 30 minutes, 0 for no timeout)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not check_venv_exists():
        prompt_setup()
        return 1

    cleaned_files = cleanup_old_temp_files()
    if cleaned_files > 0:
        print_info("Cleaned up %d old temp file(s)." % cleaned_files)

    target_path = Path(args.target).expanduser()
    if not target_path.exists():
        print_error("Target file not found: %s" % args.target)
        return 1
    if not target_path.is_file():
        print_error("Target is not a file: %s" % args.target)
        return 1

    original_path = target_path.resolve()

    # Load JEB config
    jeb_cfg = load_jeb_config()
    jeb_dir_str = jeb_cfg.get("install_dir", "")
    if not jeb_dir_str:
        print_error("JEB installation not configured.")
        print()
        print("Please run setup first:")
        print("  cd %s && uv run python setup.py" % get_skill_dir())
        return 1

    jeb_dir = Path(jeb_dir_str)
    if not jeb_dir.exists():
        print_error("JEB installation directory not found: %s" % jeb_dir)
        print()
        print("The configured JEB_DIR no longer exists. Re-run setup:")
        print("  cd %s && uv run python setup.py" % get_skill_dir())
        return 1

    jeb_exec = find_jeb_executable(jeb_dir)
    if jeb_exec is None:
        print_error("JEB executable not found in: %s" % jeb_dir)
        print()
        print("Set JEB_DIR to the directory containing bin/jeb:")
        print('  export JEB_DIR="/opt/jeb"')
        return 1

    try:
        user_code, source_desc = get_user_code(args)
    except ValueError as e:
        print_error(str(e))
        return 1

    timeout = args.timeout if args.timeout > 0 else None
    failure_token = uuid.uuid4().hex

    if args.no_wrap:
        final_code = user_code
        # For --no-wrap, the temp filename stem must match the user's IScript
        # class name. Extract it from the script filename if available.
        if args.script:
            script_name = Path(args.script).stem
        else:
            print_error("--no-wrap with inline code (-c) or stdin is not supported. "
                        "Use a script file whose filename stem matches the IScript class name.")
            return 1
        print_info("Executing %s without wrapping (class=%s)..." % (source_desc, script_name))
        exit_code = execute_script(final_code, str(original_path), jeb_exec,
                                   script_name=script_name, timeout=timeout)
    else:
        # Generate a unique Python identifier for the IScript class name.
        # JEB (Jython) requires the class name to match the filename stem.
        # The timestamp is used both in main() for class_name and in
        # execute_script() for the temp filename.
        ts = int(time.time() * 1000000)
        script_name = "jeb_script_%d" % ts
        final_code = wrap_code(user_code, args.save, script_name, failure_token)
        print_info("Executing wrapped %s..." % source_desc)
        exit_code = execute_script(final_code, str(original_path), jeb_exec,
                                   script_name=script_name,
                                   failure_token=failure_token, timeout=timeout)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
