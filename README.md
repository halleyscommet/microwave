# Microwave Raycaster

An experimental retro raycaster + tile/ entity map editor built with Pygame. Recently upgraded with improved UI/UX:

## New UI / UX Features
- Start menu (Play / Editor / Help)
- In‑game pause overlay (Resume, Restart, Editor, Main Menu, Quit)
- Enhanced HUD: health, ammo, enemy progress, crosshair, muzzle flash
- FPS counter (top‑right)
- Context hints and consistent fonts
- Cleaner window title
- Editor legend and quick menu return (ESC)

## Controls
### Menus
- 1 – Start Game
- 2 – Open Map Editor
- H – Show help (inline)
- ESC – Quit (from menu) or open menu (from game/editor)

### Gameplay
- WASD – Move (strafe + forward/back)
- Mouse – Look
- Shift (hold) – Sprint
- Space / Left Mouse – Shoot
- M – Toggle minimap
- P – Pause / resume
- R – Restart run (when dead / win state)
- E – Enter editor (from play)
- ESC – Pause (then menu options) / quit from pause menu

### Editor
- 0 / 1 / 2 – Floor / Wall / Door tiles
- 3 / 4 / 5 / 6 – Enemy / Ammo / Medkit / Spawn
- G / S / B – Change enemy type (while brush = 3)
- LMB – Paint tile or place entity
- RMB – Eyedrop (pick tile or entity brush)
- Delete / Backspace – Remove entity in cell
- Ctrl + S – Save map + entities
- Ctrl + L – Load map + entities
- N – New blank map (same size)
- Ctrl + Plus / Minus – Grow / shrink map
- Mouse Wheel – Zoom grid cell size
- P / E – Play test run
- ESC – Return to main menu

## Running
Requires Python 3.10+ and `pygame`.

```bash
pip install pygame
python game.py
```

Optional: run `maze.py` for the procedural morphing maze variant.

## File Overview
- `game.py` – Main game + editor with entities
- `maze.py` – Procedural maze raycaster variant
- `map2.txt` / `map_ents2.txt` – Saved map + entity layout
- Texture & sprite PNG/JPG assets (fallback procedural textures if missing)

## Future Ideas
- Audio feedback & weapon sounds
- Animated doors / interaction
- Configurable key bindings
- Difficulty / wave scaling
- Better enemy AI (line patrolling, ranged attack)

PRs / suggestions welcome. Have fun fragging pixels!

## Installation

Requirements:
- Python 3.10+
- Pygame

Recommended setup on macOS (zsh):

```bash
# (optional) create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# install pygame
python -m pip install --upgrade pip
pip install pygame
```

If pip errors on macOS, ensure Xcode CLT is installed and SDL has permissions to capture input. See Troubleshooting below.

## Run

From the project folder:

```bash
python game.py
```

This opens the Start Menu with Play, Editor, and Help. Mouse look is enabled automatically in play mode; use ESC to access the pause menu.

Procedural maze variant:

```bash
python maze.py
```

## Editor Quickstart

Open the editor from the main menu (option 2) or press E in play. Basics:
- Brushes: 0=floor, 1=wall, 2=door; 3=enemy, 4=ammo, 5=medkit, 6=spawn
- Enemy type while brush=3: G=grunt, S=scout, B=brute
- LMB paints/places, RMB eyedrops the tile/entity under the cursor
- Delete/Backspace removes entity in the hovered cell
- Ctrl+S saves to `map2.txt` and `map_ents2.txt`
- Ctrl+L loads from `map2.txt` and `map_ents2.txt`
- N creates a fresh blank map (same dimensions)
- Ctrl + Plus/Minus resizes the map (content preserved where possible)
- Mouse wheel zooms the grid cell size
- P or E starts a playtest run; ESC returns to main menu

Tip: Only place entities on floor tiles (0). Doors (2) and walls (1) block placement and movement.

## Map and Entity File Formats

Default paths used by the editor/game:
- Map: `map2.txt`
- Entities: `map_ents2.txt`

### Map file (`map2.txt`)
Plain text grid where each character is one tile:
- `0` = floor (walkable)
- `1` = wall (solid)
- `2` = door (solid, textured differently)

Rows may vary in length when loading; they are normalized to a rectangle with missing cells treated as walls. Perimeter walls are recommended.

### Entities file (`map_ents2.txt`)
Each line is one entity. Coordinates are integer cell indices (x y).
- `spawn x y`
- `enemy <type> x y` where `<type>` is one of `grunt|scout|brute`
	- Legacy format `enemy x y` is still accepted and maps to `grunt`
- `ammo x y`
- `medkit x y`

Out-of-bounds or blocked positions are ignored on load. Entities are only valid on floor tiles.

## Maze Variant Controls (`maze.py`)

While running the maze renderer:
- Movement: W/S to move, A/D to turn
- Toggle minimap: M
- Toggle distant morphing: R
- Toggle random wall heights: H
- Resize maze: `[` to shrink, `]` to grow (keeps odd dimensions)
- Adjust FOV: `-` to decrease, `=` (or numpad +) to increase
- ESC quits

Notes:
- Maze tiles morph beyond a safe radius from the player when morphing is enabled.
- A hidden debug mode with noclip/teleport exists behind a secret key sequence (see code for details).

## Assets and Modding

The game tries to load texture/sprite files by name and falls back to generated placeholders when missing.

Wall/door textures (64x64 recommended):
- `cobblestone.png`, `brick.jpg`, `wood.jpeg`
- `red.png`, `blue.png` (doors)

Sprites (optional):
- `enemy.png`, `enemy_grunt.png`, `enemy_scout.png`, `enemy_brute.png`
- `pickup_ammo.png`, `pickup_medkit.png`
- `pistol.png`, `muzzle.png`

Place custom images in the project root with matching filenames to override the defaults. Different sizes are scaled to 64x64.

## Troubleshooting

- Pygame install issues on macOS
	- Ensure you use a recent Python (3.10+) and a fresh virtualenv
	- Upgrade pip: `python -m pip install --upgrade pip`
	- Try `pip install pygame==2.5.*` if latest gives issues
	- If you see “SDL...” or window/input permission prompts, allow screen recording and input monitoring for your terminal in System Settings → Privacy & Security
- Mouse not captured / too sensitive
	- Mouse is grabbed only in play mode; press 1 → Play from the main menu
	- Adjust sensitivity in code via `MOUSE_SENS` in `game.py`
- Fonts or images look generic
	- That’s expected when optional assets are missing; placeholders are generated
- Crashes when loading maps/entities
	- Check that entity coordinates are inside the map and placed on `0` tiles

## Contributing

Issues and PRs are welcome. If you plan a larger change, please open an issue first to discuss scope. Useful contributions:
- Bug fixes and performance tweaks
- New enemy behaviors or editor tools
- Sound effects and music support
- Packaging scripts (e.g., pyproject, requirements, or a simple launcher)

## License

No license file present. If you intend to reuse or distribute, consider adding a `LICENSE` (e.g., MIT) to clarify permissions.
