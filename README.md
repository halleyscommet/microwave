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
