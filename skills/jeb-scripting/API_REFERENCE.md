# JEB Pro API Quick Reference

Quick reference for the JEB Pro Python API. For basic usage, see [SKILL.md](SKILL.md).

In auto-wrapped scripts, the `ctx` (IClientContext) and `prj` (IProject) variables are always available.

**IMPORTANT:** JEB uses Jython (Python 2.7 compatible). Avoid f-strings, type hints, and `pathlib`. Use `%` formatting, plain `print`, and `os.path` instead. The IScript class name **must match** the script filename stem (e.g., `class myscript(IScript):` in `myscript.py`).

## Table of Contents

- [Client Context (IClientContext)](#client-context-iclientcontext)
- [Project (IProject)](#project-iproject)
- [Artifacts and Units](#artifacts-and-units)
- [APK Unit](#apk-unit)
- [DEX Bytecode Unit](#dex-bytecode-unit)
- [Classes](#classes)
- [Methods](#methods)
- [Strings](#strings)
- [Cross-References](#cross-references)
- [Decompilation](#decompilation)
- [Common Patterns](#common-patterns)

## Client Context (IClientContext)

```python
# Available as `ctx` in wrapped scripts
prj = ctx.getMainProject()    # Get the loaded project
args = ctx.getArguments()     # Script arguments (after --)
```

## Project (IProject)

```python
prj.getName()                  # Project name (filename)
prj.getLiveArtifacts()         # List[IArtifact] — top-level artifacts
prj.getLiveArtifact(index)     # Get artifact by index
prj.findUnit(name)             # Find a specific unit by name
prj.getCreationTimestamp()     # Project creation time

# Save
prj.save()                     # Save .jdb2 (use with --save flag)
```

## Artifacts and Units

JEB organizes files in a hierarchy: **Project → Artifact → Unit → Children**.

```python
# Get the first artifact (container for processed file)
art = prj.getLiveArtifacts()[0]

# Get units within an artifact
units = art.getUnits()         # List[IUnit]
main_unit = art.getMainUnit()  # Primary unit
```

### Unit (IUnit)

```python
unit.getName()                 # e.g. "com.unitree.doggo2" or "Bytecode"
unit.getFormatType()           # e.g. "apk", "dex", "xml", "cert", "composite"
unit.isProcessed()             # Whether analysis completed
unit.getInput()                # Input file path
unit.getChildren()             # List[IUnit] — sub-units (DEX, resources, libs...)
unit.getParent()               # Parent unit
```

## APK Unit

An APK unit's children contain:

```python
apk_unit = prj.getLiveArtifacts()[0].getUnits()[0]
children = apk_unit.getChildren()
# [0] Manifest (xml)      — AndroidManifest.xml
# [1] Certificate (cert)  — signing certificate
# [2] Bytecode (dex)      — merged DEX code
# [3] Resources (composite)
# [4] Assets (composite)
# [5] Libraries (composite)

apk_unit.getPackageName()      # Package name (e.g. "com.unitree.doggo2")
```

## DEX Bytecode Unit

```python
dex = apk_unit.getChildren()[2]   # "Bytecode" unit

dex.getFormatType()               # "dex"
dex.getName()                     # "Bytecode"

# Bulk access (return Java lists)
dex.getClasses()                  # All classes
dex.getMethods()                  # All methods
dex.getStrings()                  # All strings
dex.getPackages()                 # All packages
dex.getFields()                   # All fields

# Lookup
dex.findClassByName(signature)    # e.g. "Lcom/example/Foo;"
dex.getMethod(address)            # Method at address
dex.getString(index)              # String by index
dex.getField(address)             # Field at address

# Disassembly
dex.getDisassembly(address)       # Disassembly at address
dex.getInstructionCount()         # Total instructions
```

## Classes

```python
for cls in dex.getClasses():
    s = str(cls)
    # Format: "Class:#0,name=ClassName,address=Ljava/lang/Object;"
    # Extract name: s.split("name=")[1].split(",")[0]
    # Extract address: s.split("address=")[1].split(";")[0]
```

Class properties (via `str()` parsing, not direct attributes):
| Field | Example |
|-------|---------|
| `name=...` | `MainActivity` |
| `address=...` | `Lcom/example/MainActivity;` |

## Methods

```python
for method in dex.getMethods():
    s = str(method)
    # Format: "Method:#0,name=onCreate,address=...@0x1234,type=virtual"
```

## Strings

```python
for s_obj in dex.getStrings():
    try:
        s = unicode(s_obj)        # Jython: use unicode(), not str()
    except:
        continue                  # Skip non-decodable strings
```

**Warning:** Jython's `str()` raises UnicodeEncodeError on non-ASCII strings. Always wrap with `unicode()` and try/except.

## Cross-References

```python
# Get xrefs to an address
xrefs = dex.getCrossReferences(address)
for xref in xrefs:
    print("From: 0x%x, Type: %s" % (xref.getFromAddress(), xref.getType()))
```

## Decompilation

```python
# Decompile to Java (DEX) or C (native)
decompiler = dex.getDecompiler()
if decompiler:
    result = decompiler.decompile(address)
    if result:
        print(result.getSource())
```

```python
# Get disassembly document
doc = dex.getDisassemblyDocument()
if doc:
    print(doc.getText())  # Full disassembly
```

## Common Patterns

### APK Summary

```python
art = prj.getLiveArtifacts()[0]
apk = art.getUnits()[0]
print("Package: %s" % apk.getPackageName())

for child in apk.getChildren():
    print("  %s [%s]" % (child.getName(), child.getFormatType()))
```

### DEX Stats

```python
dex = apk.getChildren()[2]  # Bytecode
print("Classes: %d" % len(dex.getClasses()))
print("Methods: %d" % len(dex.getMethods()))
print("Strings: %d" % len(dex.getStrings()))
```

### List Non-Standard Packages

```python
non_std = set()
for cls in dex.getClasses():
    s = str(cls)
    if "address=L" in s:
        addr = s.split("address=L")[1].split(";")[0]
        pkg = addr.rsplit("/", 1)[0]
        if not pkg.startswith(("android", "java", "javax", "dalvik", "kotlin")):
            non_std.add(pkg)

for pkg in sorted(non_std):
    print(pkg.replace("/", "."))
```

### Find Classes by Prefix

```python
prefix = "com/example"
for cls in dex.getClasses():
    s = str(cls)
    if prefix in s:
        name = s.split("name=")[1].split(",")[0] if "name=" in s else "?"
        addr = s.split("address=L")[1].split(";")[0] if "address=L" in s else "?"
        print("%s  ->  %s" % (addr.replace("/", "."), name))
```

### Search Strings

```python
keywords = ["http://", "api.", "token", "password"]
for s_obj in dex.getStrings():
    try:
        s = unicode(s_obj)
        for kw in keywords:
            if kw in s.lower():
                print(s)
                break
    except:
        pass  # Skip non-decoded strings
```

## Gotchas

1. **Jython is Python 2.7** — no f-strings, no type hints, no `pathlib`. Use `%` formatting and `unicode()`.
2. **Class name = filename stem** — JEB imports the script and looks for a class matching the module name.
3. **`unicode()` not `str()` for strings** — Jython's `str()` crashes on non-ASCII. Always `try/except` string reads.
4. **DEX classes are opaque** — properties extracted from `str(cls)` representation, not direct attributes.
5. **5 DEX merge for protected APKs** — JEB merges multi-DEX automatically; baidu-protected APKs may have obfuscated class names.
6. **`getUnits()` is on artifacts, not project** — use `prj.getLiveArtifacts()[0].getUnits()`.
