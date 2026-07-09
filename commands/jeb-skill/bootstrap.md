---
description: Generate API_REFERENCE.md from the JEB Pro apidoc
allowed-tools: Bash(find:*), Bash(grep:*), Bash(wc:*), Read, Write, Glob, Grep
---

# Bootstrap: Generate API_REFERENCE.md

You are generating a **hand-written style** API quick reference for the JEB Pro skill.

**IMPORTANT - Path Resolution:**
This skill can be installed in different locations. Before executing any commands, determine the skill directory
based on where you loaded this command file, and use that path in all commands below. Replace `$SKILL_DIR` with the
actual discovered path.

Common installation paths:
- Project-specific: `<project>/.claude/skills/jeb-scripting`
- Manual global: `~/.claude/skills/jeb-scripting`
- Local plugin: `$REPO_DIR/skills/jeb-scripting`

## Context

JEB Pro ships with API documentation at `$JEB_DIR/doc/apidoc/` (or online at https://www.pnfsoftware.com/jeb/apidoc/).
The JEB installation location is recorded in `$SKILL_DIR/_jeb_config.json` (field `install_dir`) after `setup.py` has
run. Read that file to find the apidoc location.

If `_jeb_config.json` is missing, ask the user to run `cd $SKILL_DIR && uv run python setup.py` first.

## Your Task

1. **Locate the JEB apidoc** via `_jeb_config.json` → `install_dir` → `doc/apidoc/`
2. **Identify the main API classes and their key methods** by reading the apidoc HTML/package-list
3. **Extract key classes**: IClientContext, IProject, ICodeUnit, IJavaSourceUnit, IDexUnit, INativeCodeUnit, etc.
4. **Generate `API_REFERENCE.md`** in the skill root directory

## Output Format (API_REFERENCE.md)

Follow this structure — practical, pattern-focused, ~500-800 lines max:

```markdown
# JEB Pro API Quick Reference

Quick reference for the JEB Pro Python API. For basic usage, see [SKILL.md](SKILL.md).

In auto-wrapped scripts, the `ctx` (IClientContext) and `prj` (IProject) variables are always available.

## Table of Contents
[Generate dynamically based on discovered entities]

## Client Context (IClientContext)

### Properties
[table of key properties]

### Methods
[code examples for the most important methods]

## Project (IProject)

...

## Code Units

### Native Code Units (ICodeUnit)
- Methods, basic blocks, cross-references
- Decompilation to pseudo-C

### DEX/Dalvik Units (IDexUnit)
- Classes, methods, fields
- Decompilation to Java

### Java Source Units (IJavaSourceUnit)
- Classes, methods, fields
- Source-level analysis

## Strings, Bytes, Patterns

...

## Cross-References

...

## Common Enums

### Unit Format Types
[table with descriptions]

### Xref Types
[table with descriptions]
```

## Guidelines

1. **Be practical** - Show how to DO things, not just what exists
2. **Use code examples** - Every section should have runnable code (assume `ctx` and `prj` are available)
3. **Document the gotchas** - Different unit types have different API surfaces, use `hasattr()` to check
4. **Keep it concise** - 500-800 lines max
5. **Focus on wrapped scripts** - Assume `ctx`/`prj` are available (auto-wrapped mode)
6. **Include return types** - What does each method return?
7. **Group by use-case** - Not alphabetically by class

## Process

1. **Discover the apidoc structure:**
   - Read `_jeb_config.json` to find `install_dir`
   - Look for `doc/apidoc/` in the JEB installation
   - Check for `allclasses-noframe.html`, `index.html`, or `package-list`

2. **For each key API class discovered:**
   - Identify the class hierarchy
   - Extract key methods and their signatures
   - Note descriptions from the apidoc
   - Identify common usage patterns

3. **Extract all relevant enums and types:**
   - Unit format types
   - Xref types
   - Other commonly referenced types

4. **Generate API_REFERENCE.md:**
   - Start with IClientContext and IProject
   - Add sections for each code unit type
   - Include practical code examples
   - Document non-obvious method names and return shapes

Start by reading `_jeb_config.json`, then explore the apidoc directory structure.
