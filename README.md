# (unsafe) Reverse Engineering with Code Evaluation and the JEB Pro API

> warning: this plugin generates and evaluates code on the current system, so it should only be used in a sandboxed environment.

Analyze binaries using JEB Pro's Python API in headless mode. Use when examining program structure, functions,
disassembly, cross-references, decompilation (native C / Dalvik Java / WASM), or strings without the GUI.

Provides:
- agent `jeb-expert`: Senior JEB Pro Python developer and reverse engineer. Use proactively when writing JEB scripts,
  debugging JEB API issues, analyzing binary analysis problems, or when the user needs expert guidance on reverse
  engineering tasks with JEB Pro.
- skill `jeb-scripting`: Write and execute Python scripts using the JEB Pro API for reverse engineering. Analyze
  binaries, extract functions, strings, cross-references, decompile code (native/Dalvik/WASM), work with JEB databases
  (.jdb2). Use when user wants to analyze binaries, reverse engineer executables, or automate JEB Pro tasks.

## Installation

This plugin is local (not in a marketplace). From this directory:

```bash
# Claude Code (local plugin install)
claude plugin install $REPO_DIR

# Or symlink the skill into each CLI's discovery dir (cross-CLI):
# Codex:   ln -s $REPO_DIR/skills/jeb-scripting ~/.codex/skills/jeb-scripting
# zcode:   ln -s $REPO_DIR/skills/jeb-scripting ~/.agents/skills/jeb-scripting
```

First-time setup (per skill dir):

```bash
cd $REPO_DIR/skills/jeb-scripting && uv run python setup.py
```

## Requirements

- **uv** package manager
- **JEB Pro 5.0+** (Jython scripting engine)
- **JDK 11+** for running JEB
- A valid JEB Pro license on this machine

Set `JEB_DIR` if setup can't auto-detect your JEB installation:

```bash
export JEB_DIR="/opt/jeb"               # Linux
export JEB_DIR="/Applications/JEB.app"  # macOS
```

## Usage

Once the skill is loaded, ask the AI agent to analyze a binary:

```
"Analyze sample.exe — list all functions and their addresses"
"Find all strings containing URLs in app.apk"
"Decompile the main function in firmware.bin"
```

The agent will automatically write the appropriate JEB script and execute it.

## Architecture

```
jeb-agent/
├── .claude-plugin/plugin.json    # Plugin registration
├── agents/jeb-expert.md          # Agent persona and expertise
├── commands/jeb-skill/
│   └── bootstrap.md              # API_REFERENCE.md generator
├── README.md
└── skills/jeb-scripting/
    ├── SKILL.md                  # Skill definition and usage patterns
    ├── API_REFERENCE.md          # JEB API quick reference
    ├── run.py                    # Universal script executor (headless wrapper)
    ├── setup.py                  # Environment setup and JEB detection
    ├── pyproject.toml            # Python project metadata (uv)
    └── .venv/                    # uv-managed virtual environment
```

### How It Works

1. The AI agent writes a Python analysis script to `/tmp/jeb-<timestamp>-<name>/script.py`
2. `run.py` wraps the script as a JEB IScript implementation with `ctx`/`prj` context
3. JEB is launched in headless mode: `jeb_macos.sh -c --script=<script> --infile=<binary>`
4. Output is captured and displayed in real-time
5. Temp scripts are auto-cleaned
