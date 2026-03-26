# /compile - MQL5 Compilation

Command for compiling MQL5 files via Pepperstone MetaTrader 5.

## Usage

```
/compile [file]
```

If no file is specified, `Stage2.mq5` is compiled.

## How It Works

MetaTrader 5 runs via Parallels (Windows VM). Compilation is performed through `metaeditor64.exe`.

### Compilation Command

```bash
# Via Parallels prlctl
prlctl exec "Windows 11" "C:\Program Files\Pepperstone MetaTrader 5\metaeditor64.exe" /compile:"<file_path>" /log:"compile.log"
```

### Alternative: Via Shared Folder

If files are synced through Parallels Shared Folders:

```bash
# Windows path to the project
C:\Users\User\MQL5_Dev\Experts\Michael Spiropoulos\Stage2.mq5

# Or via Parallels mount
\\Mac\Home\MQL5_Dev\Experts\Michael Spiropoulos\Stage2.mq5
```

## Steps

1. **Check the MT5 path** -- make sure Pepperstone MT5 is installed
2. **Run compilation** -- use the command above
3. **Check logs** -- `compile.log` contains errors and warnings

## Parsing Results

After compilation, check:

- **0 error(s)** -- successful compilation
- **X error(s)** -- there are errors that need to be fixed
- **X warning(s)** -- warnings (can be ignored, but better to fix)

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `'identifier' - undeclared identifier` | Variable/function not declared | Check include files |
| `'=' - l-value required` | Attempting to assign a value to a constant | Check const modifiers |
| `cannot open file` | File not found | Check include path |
| `struct has no members` | Empty struct | Add at least one field |

## Notes

- Compilation requires a running Windows VM in Parallels
- MetaEditor must be closed during CLI compilation
- The result is saved as an `.ex5` file next to the source file
