# rgb-keyboard-language

Monorepo for automatically changing Keychron keyboard RGB color based on current keyboard layout.

## Projects

### [keychron-via-hue](./keychron-via-hue/)

CLI utility for managing RGB hue of QMK/VIA-compatible keyboards via `qmk_hid`.

**See:** [keychron-via-hue/README.md](./keychron-via-hue/README.md)

### [rgb-keyboard-language-windows](./rgb-keyboard-language-windows/)

Windows tray application that automatically changes keyboard RGB color based on current keyboard layout.

**See:** [rgb-keyboard-language-windows/README.md](./rgb-keyboard-language-windows/README.md)

## Quick Start

### Requirements

- Windows 10/11
- Python 3.10+
- `qmk_hid` - must be available in PATH ([download](https://github.com/FrameworkComputer/qmk_hid/releases))

### Installation

```bash
# Install both projects
pip install -e ./keychron-via-hue
pip install -e ./rgb-keyboard-language-windows

# Run tray application
rgb-keyboard-language
```

### Build Executable

```bash
cd rgb-keyboard-language-windows
python build.py
```

Executable will be in `rgb-keyboard-language-windows/dist/rgb-keyboard-language.exe`

### Releasing

1. Update version in `pyproject.toml`
2. Commit: `git commit -am "release: v0.x.x"`
3. Tag: `git tag v0.x.x`
4. Push: `git push && git push --tags`

GitHub Actions will automatically build the Windows exe and create a release with it attached.

## Project Structure

```
rgb-keyboard-language/
├── keychron-via-hue/              # CLI utility
├── rgb-keyboard-language-windows/ # Windows tray app
├── .cursor/rules/                 # Cursor IDE rules
├── AGENTS.md                      # Agents knowledge base
└── CLAUDE.md                      # Claude knowledge base
```

## Documentation

- [keychron-via-hue/README.md](./keychron-via-hue/README.md) - CLI utility documentation
- [rgb-keyboard-language-windows/README.md](./rgb-keyboard-language-windows/README.md) - Tray app documentation
- [AGENTS.md](./AGENTS.md) - Architectural patterns and solutions
- [CLAUDE.md](./CLAUDE.md) - Code examples and context

## License

MIT
