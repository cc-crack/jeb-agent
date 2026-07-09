---
name: jeb-scripting
description: Write and execute Python scripts using the JEB Pro API for reverse engineering. Analyze binaries, extract functions, strings, cross-references, decompile code (native/Dalvik/WASM), work with JEB databases (.jdb2). Use when user wants to analyze binaries, reverse engineer executables, or automate JEB Pro tasks.
---

**IMPORTANT - Path Resolution:**
This skill can be installed in different locations. Before executing any commands, determine the skill directory based
on where you loaded this SKILL.md file, and use that path in all commands below. Replace `$SKILL_DIR` with the actual
discovered path.

Common installation paths:

- Project-specific: `<project>/.claude/skills/jeb-scripting`
- Manual global: `~/.claude/skills/jeb-scripting`
- Local plugin: `$REPO_DIR/skills/jeb-scripting`

# JEB Pro Scripting

General-purpose binary analysis skill. I'll write custom JEB Python code for any reverse engineering task you
request and execute it via the universal executor.

**CRITICAL WORKFLOW - Follow these steps in order:**

1. **Create a work dir in /tmp with timestamp** - NEVER write scripts to skill directory; always create a workdir
   `/tmp/jeb-YYYYMMDD_HHMMSS_ffffff-<name>` with microseconds for uniqueness (e.g.,
   `/tmp/jeb-20260109_143052_847291-list-functions`). Generate timestamp with: `datetime.now().
   strftime
   ('%Y%m%d_%H%M%S_%f')`.
   This will always be referenced as <work_dir>

2. **Read API_REFERENCE.md** - Always read $SKILL_DIR/API_REFERENCE.md before writing scripts. It contains the
   authoritative API documentation based on the actual JEB installation.

3. **Execute from skill directory** - Always run:
   `cd $SKILL_DIR && uv run python run.py <work_dir>/script.py -f <binary>`

4. **Ask before saving** - Scripts that persist a .jdb2 require explicit user confirmation before using `--save`

## How It Works

1. You describe what you want to analyze/extract
2. I write custom JEB API code in `<work_dir>/script.py` (timestamped with microseconds for parallel execution)
3. I execute it via: `cd $SKILL_DIR && uv run python run.py <work_dir>/script.py -f <binary>`
4. Results displayed in real-time
5. Script files auto-cleaned from /tmp by your OS

## Setup (First Time)

```bash
cd $SKILL_DIR && uv run python setup.py
```

This locates the JEB Pro installation, creates a uv virtual environment, and writes `_jeb_config.json` (used by
`run.py` to locate the JEB runtime). Only needed once.

Requirements:

- uv package manager
- JEB Pro 5.0+ (requires Jython scripting engine)
- A valid JEB Pro license on this machine
- Java Runtime (JDK 11+)

If setup can't find JEB, set `JEB_DIR` to the JEB installation directory:

```bash
export JEB_DIR="/opt/jeb"               # Linux
export JEB_DIR="/Applications/JEB.app"  # macOS
```

## Execution Pattern

**Step 1: Write analysis script to <work_dir>**

```python
# <work_dir>/script.py
for unit in prj.getLiveArtifacts()[0].getUnits():
    print("Unit: %s" % unit.getName())
```

**Step 2: Execute from skill directory**

```bash
cd $SKILL_DIR && uv run python run.py <work_dir>/script.py -f /path/to/binary
```

**Step 3: Review results**

Scripts are auto-wrapped with JEB boilerplate. The `ctx` (IClientContext) and `prj` (IProject) variables are
available for accessing the project and all entities.

**IMPORTANT:** JEB uses Jython (Python 2.7). Use `%` formatting (not f-strings), `unicode()` for strings,
and plain `print`. Always consult [API_REFERENCE.md](API_REFERENCE.md) for correct method signatures —
the examples below illustrate concepts; use the reference for actual API names.

## Common Patterns

### List All Units

```python
# <work_dir>/script.py
art = prj.getLiveArtifacts()[0]
for unit in art.getUnits():
    name = unit.getName()
    fmt = unit.getFormatType()
    print("%s [%s]" % (name, fmt))
```

### List Functions in a Code Unit

```python
# <work_dir>/script.py
for unit in prj.getLiveArtifacts()[0].getUnits():
    # Check if it's a code unit (native, DEX, etc.)
    if hasattr(unit, 'getMethods'):
        print("\n=== %s ===" % unit.getName())
        for method in unit.getMethods():
            addr = method.getAddress()
            name = method.getName()
            print("  %s: 0x%08X" % (name, addr))
```

### Find Function by Name

```python
# <work_dir>/script.py
target = "main"
for unit in prj.getLiveArtifacts()[0].getUnits():
    if hasattr(unit, 'getMethods'):
        for method in unit.getMethods():
            if method.getName() == target:
                print("Found %s at 0x%08X in %s" % (target, method.getAddress(), unit.getName()))
```

### Search Strings

```python
# <work_dir>/script.py
import re

for unit in prj.getLiveArtifacts()[0].getUnits():
    if hasattr(unit, 'getStrings'):
        print("\n=== Strings in %s ===" % unit.getName())
        for s in unit.getStrings():
            try:
                content = s.getValue()
                print("  0x%08X: %s" % (s.getAddress(), content))
            except Exception:
                continue
```

### Analyze Cross-References

```python
# <work_dir>/script.py
target_addr = 0x401000
for unit in prj.getLiveArtifacts()[0].getUnits():
    if hasattr(unit, 'getCrossReferencesTo'):
        xrefs = unit.getCrossReferencesTo(target_addr)
        if xrefs:
            print("Xrefs to 0x%08X in %s:" % (target_addr, unit.getName()))
            for xref in xrefs:
                print("  From: 0x%08X" % xref.getFromAddress())
        else:
            print("No xrefs to 0x%08X found" % target_addr)
```

### Decompile a Function (Native)

```python
# <work_dir>/script.py
target = "main"
for unit in prj.getLiveArtifacts()[0].getUnits():
    if hasattr(unit, 'decompile'):
        for method in unit.getMethods():
            if method.getName() == target:
                try:
                    decomp = unit.decompile(method.getAddress())
                    if decomp:
                        print(decomp.getSource())
                    else:
                        print("Decompilation returned None for %s" % target)
                except Exception as e:
                    print("Decompilation failed: %s" % e)
```

### Decompile APK/DEX to Java

```python
# <work_dir>/script.py
for unit in prj.getLiveArtifacts()[0].getUnits():
    # Check for DEX/Dalvik units
    name = unit.getName().lower()
    if '.dex' in name or hasattr(unit, 'getClasses'):
        print("\n=== Decompiling %s ===" % unit.getName())
        if hasattr(unit, 'getClasses'):
            for cls in unit.getClasses():
                print("\n  Class: %s" % cls.getName())
                if hasattr(cls, 'getMethods'):
                    for method in cls.getMethods():
                        try:
                            decomp = unit.decompile(method.getAddress())
                            if decomp:
                                src = decomp.getSource()
                                print("    %s:" % method.getName())
                                for line in src.split('\n')[:5]:
                                    print("      %s" % line)
                        except Exception:
                            continue
```

### Analyze Function Complexity

```python
# <work_dir>/script.py
complex_funcs = []
for unit in prj.getLiveArtifacts()[0].getUnits():
    if hasattr(unit, 'getMethods'):
        for method in unit.getMethods():
            if hasattr(unit, 'getBasicBlocks'):
                blocks = unit.getBasicBlocks(method.getAddress())
                if blocks:
                    block_count = len(blocks)
                    edge_count = sum(len(b.getOutgoingEdges()) for b in blocks if hasattr(b, 'getOutgoingEdges'))
                    cyclomatic = max(1, edge_count - block_count + 2)
                    if cyclomatic > 10:
                        complex_funcs.append((method.getName(), method.getAddress(), cyclomatic))

complex_funcs.sort(key=lambda x: x[2], reverse=True)
print("Most complex functions:")
for name, addr, cc in complex_funcs[:10]:
    print("  %s: complexity=%d at 0x%08X" % (name, cc, addr))
```

### Search Byte Patterns

```python
# <work_dir>/script.py
# Search for x64 function prologue: push rbp; mov rbp, rsp
pattern = b"\x55\x48\x89\xE5"
for unit in prj.getLiveArtifacts()[0].getUnits():
    if hasattr(unit, 'findBinarySequence'):
        results = unit.findBinarySequence(pattern)
        for addr in results:
            print("Found prologue at 0x%08X in %s" % (addr, unit.getName()))
```

### Export to JSON

```python
# <work_dir>/script.py
import json

functions = []
for unit in prj.getLiveArtifacts()[0].getUnits():
    if hasattr(unit, 'getMethods'):
        for method in unit.getMethods():
            functions.append({
                "name": method.getName(),
                "address": "0x%08X" % method.getAddress(),
                "unit": unit.getName(),
            })

output = {"functions": functions}
with open("/tmp/functions.json", "w") as f:
    json.dump(output, f, indent=2)
print("Exported %d functions to /tmp/functions.json" % len(functions))
```

## Inline Execution (Simple Tasks)

For quick one-off tasks, you can execute code inline without creating files:

```bash
# Quick unit count
cd $SKILL_DIR && uv run python run.py -c "print('Units: %d' % len(prj.getLiveArtifacts()[0].getUnits()))" -f binary

# Get binary info
cd $SKILL_DIR && uv run python run.py -c "for u in prj.getLiveArtifacts()[0].getUnits(): print(u.getName())" -f binary
```

**When to use inline vs files:**

- **Inline**: Quick one-off tasks (count units, check names, test API calls)
- **Files**: Complex analysis, multi-step tasks, anything user might want to re-run

## Advanced Usage

For comprehensive JEB API documentation, see [API_REFERENCE.md](API_REFERENCE.md):

- Project and workspace management
- Unit enumeration and type detection
- Native code units: methods, basic blocks, cross-references
- DEX/Dalvik units: classes, methods, fields, strings
- Decompilation (native to C, DEX to Java)
- Byte pattern matching
- Control flow analysis
- Comments, renaming, types
- Saving projects (.jdb2)

## Tips

- **Default is read-only** - Use `--save` only when a .jdb2 should persist (and ask user first!)
- **Check unit type** - Not all units have the same API; check with `hasattr()` before using methods
- **Timeout** - Default 30 minutes; use `--timeout 0` for long-running analysis
- **No-wrap mode** - Use `--no-wrap` when your script already handles JEB context setup
- **Error handling** - Always use try-except for decompilation and string operations
- **Check for None** - Many JEB API methods return None if something isn't found

## Troubleshooting

**When encountering errors:**
Check the JEB API documentation at `$JEB_DIR/doc/apidoc/` or online at https://www.pnfsoftware.com/jeb/apidoc/.
The API may differ between JEB versions.

**Virtual environment not found:**

```bash
cd $SKILL_DIR && uv run python setup.py
```

**JEB fails to start / JEB_DIR error:**

```bash
export JEB_DIR=/path/to/jeb/installation
```

Verify JEB_DIR points to the directory containing `bin/jeb` (Linux/macOS) or `jeb.exe` (Windows).

**Script timeout:**

```bash
cd $SKILL_DIR && uv run python run.py --timeout 3600 ...  # 1 hour
cd $SKILL_DIR && uv run python run.py --timeout 0 ...     # No timeout
```

**Java error / JVM not found:**
Ensure JDK 11+ is installed. Set JAVA_HOME if JEB can't find it automatically.

**License errors:**
Headless JEB requires a valid license. Launch the JEB GUI once to activate it, then re-run.

**AttributeError when calling methods on a unit:**
JEB has multiple unit types (ICodeUnit, IJavaSourceUnit, IDexUnit, etc.) with different APIs. Use `hasattr()`
or check `unit.getFormatType()` before calling methods.

## Example Usage

```
User: "How many functions are in this binary?"

Claude: I'll count the functions. Let me analyze the binary...
[Writes: <work_dir>/script.py]
[Runs: cd $SKILL_DIR && uv run python run.py <work_dir>/script.py -f binary]
[Output: Found 250 methods across 1 code unit]

The binary contains 250 functions.
```

```
User: "Find all classes in this APK that extend Activity"

Claude: I'll search for Activity subclasses...
[Writes: <work_dir>/script.py]
[Runs: cd $SKILL_DIR && uv run python run.py <work_dir>/script.py -f app.apk]
[Output: MainActivity, SettingsActivity, LoginActivity, ...]

Found 12 Activity subclasses:
- MainActivity
- SettingsActivity
...
```

```
User: "Decompile the main function and save it"

Claude: I'll decompile main's C output and save it...
[Writes: <work_dir>/script.py]
[Runs: cd $SKILL_DIR && uv run python run.py <work_dir>/script.py -f binary]
[Output: Saved to /tmp/main.c]

Done! The decompiled code is saved to /tmp/main.c
```
