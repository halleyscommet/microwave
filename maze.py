import math
import sys
import random
import pygame

# ---------- Config ----------
SCREEN_W, SCREEN_H = 800, 600
FOV = math.pi / 3  # 60°
HALF_FOV = FOV * 0.5

MOVE_SPEED = 3.0       # units / sec
TURN_SPEED = 2.2       # rad / sec
DEADZONE = 0.12
TEX_SIZE = 64 

# Maze config (use odd dimensions for pretty mazes)
# These are runtime-adjustable now; use the controls to change them.
MAZE_W = 32  # columns
MAZE_H = 32  # rows
DOOR_FRACTION = 0.0015  # ~1.5% of cells become "doors" (2); set 0 to disable
RNG_SEED = random.randint(0, 27000000000)        # set to an int for reproducible mazes

# Minimap config
MINIMAP_MARGIN = 10
MINIMAP_BG_ALPHA = 120   # 0..255
MINIMAP_WALL = (70, 70, 80)
MINIMAP_FLOOR = (150, 150, 160)
MINIMAP_DOOR = (230, 200, 60)
MINIMAP_PLAYER = (255, 70, 90)
MINIMAP_FOV = (255, 255, 255)

# --- Height model (feet) ---
PLAYER_HEIGHT_FT = 6.0
WALL_MIN_HEIGHT_FT = 6.0
WALL_MAX_HEIGHT_FT = 13.0
DOOR_HEIGHT_FT = 7.0  # tweak as desired

# --- Distant Morphing (new) ---
SHUFFLE_SAFE_RADIUS = 6        # cells around player that never morph
PHASE_PERIOD = 3.5             # seconds per morph phase
FLIP_PROB = 0.18               # chance to flip far tiles per phase (wall<->floor)
# Note: doors can also morph (rare) to feel spicier; reduce inside perturb() if you want doors stable.

# ---------- Feature Toggles (runtime) ----------
SHOW_MINIMAP = True          # toggle: M
ENABLE_MORPH = True          # toggle: R  (R for "randomization")
ENABLE_RAND_HEIGHTS = False  # toggle: H  (random wall height scaling)

# ---------- Maze Generation ----------
# 1=wall, 0=floor, 2=door
def generate_maze_grid(w, h, seed=None):
    if seed is not None:
        random.seed(seed)
    w = max(5, w | 1)
    h = max(5, h | 1)
    grid = [[1 for _ in range(w)] for _ in range(h)]
    start_x, start_y = 1, 1
    grid[start_y][start_x] = 0
    stack = [(start_x, start_y)]

    def neighbors(x, y):
        dirs = [(2, 0), (-2, 0), (0, 2), (0, -2)]
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 1 <= nx < w - 1 and 1 <= ny < h - 1 and grid[ny][nx] == 1:
                yield (nx, ny, dx, dy)

    while stack:
        x, y = stack[-1]
        for nx, ny, dx, dy in neighbors(x, y):
            grid[y + dy // 2][x + dx // 2] = 0
            grid[ny][nx] = 0
            stack.append((nx, ny))
            break
        else:
            stack.pop()
    return grid

def sprinkle_doors(world, fraction=0.01):
    h = len(world); w = len(world[0])
    candidates = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if world[y][x] != 1: continue
            ns = (world[y - 1][x] == 0 and world[y + 1][x] == 0)
            ew = (world[y][x - 1] == 0 and world[y][x + 1] == 0)
            if ns or ew:
                candidates.append((x, y))
    random.shuffle(candidates)
    count = int(w * h * fraction)
    for i in range(min(count, len(candidates))):
        x, y = candidates[i]
        world[y][x] = 2

def pick_spawn(world):
    h = len(world); w = len(world[0])
    open_cells = [(x, y) for y in range(1, h - 1) for x in range(1, w - 1) if world[y][x] == 0]
    if not open_cells:
        cx, cy = w // 2, h // 2
        world[cy][cx] = 0
        return (cx + 0.5, cy + 0.5)
    x, y = random.choice(open_cells)
    return (x + 0.5, y + 0.5)

def regenerate_map(w, h, seed=None):
    """Generate WORLD_MAP, BASE_MAP, MAP_W, MAP_H and WALL_HEIGHTS_FT for new dimensions.
    Returns tuple (WORLD_MAP, BASE_MAP, MAP_W, MAP_H, WALL_HEIGHTS_FT).
    """
    world = generate_maze_grid(w, h, seed=seed)
    if DOOR_FRACTION > 0:
        sprinkle_doors(world, DOOR_FRACTION)
    map_w, map_h = len(world[0]), len(world)
    base = [row[:] for row in world]
    heights = [[0.0 for _ in range(map_w)] for _ in range(map_h)]
    for yy in range(map_h):
        for xx in range(map_w):
            t = base[yy][xx]
            if t == 1:
                heights[yy][xx] = random.uniform(WALL_MIN_HEIGHT_FT, WALL_MAX_HEIGHT_FT)
            elif t == 2:
                heights[yy][xx] = DOOR_HEIGHT_FT
            else:
                heights[yy][xx] = 0.0
    return world, base, map_w, map_h, heights


WORLD_MAP, BASE_MAP, MAP_W, MAP_H, WALL_HEIGHTS_FT = regenerate_map(MAZE_W, MAZE_H, seed=RNG_SEED)

# Per-tile wall/door heights (in feet) for base walls/doors
WALL_HEIGHTS_FT = [[0.0 for _ in range(MAP_W)] for _ in range(MAP_H)]
for y in range(MAP_H):
    for x in range(MAP_W):
        t = BASE_MAP[y][x]
        if t == 1:  # wall
            WALL_HEIGHTS_FT[y][x] = random.uniform(WALL_MIN_HEIGHT_FT, WALL_MAX_HEIGHT_FT)
        elif t == 2:  # door
            WALL_HEIGHTS_FT[y][x] = DOOR_HEIGHT_FT
        else:
            WALL_HEIGHTS_FT[y][x] = 0.0  # floor

# ---------- Init ----------
pygame.init()
pygame.joystick.init()

screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("First Person 3D Renderer (No-Strafe) + Minimap + Distant Morphing")
clock = pygame.time.Clock()

# HUD font
HUD_FONT = pygame.font.SysFont(None, 18)

# Secret/debug mode state (disabled by default). Use a hidden key sequence to toggle.
DEBUG_MODE = False
DEBUG_NOCLIP = False
# Konami-like secret sequence to enable debug mode: Up,Up,Down,Down,Left,Right,Left,Right,B,A
_SECRET_SEQ = [pygame.K_UP, pygame.K_UP, pygame.K_DOWN, pygame.K_DOWN,
               pygame.K_LEFT, pygame.K_RIGHT, pygame.K_LEFT, pygame.K_RIGHT,
               pygame.K_b, pygame.K_a]
_secret_idx = 0


# Textures
def load_scaled(path):
    surf = pygame.image.load(path).convert()
    return pygame.transform.scale(surf, (TEX_SIZE, TEX_SIZE))

stone = load_scaled("cobblestone.png")
brick = load_scaled("brick.jpg")
wood = load_scaled("wood.jpeg")
door_red = load_scaled("red.png")
door_blue = load_scaled("blue.png")

def pick_wall_texture(mx, my):
    s = (mx + my) % 3
    if s == 0: return stone
    elif s == 1: return brick
    else: return wood

def pick_door_texture(mx, my):
    return door_red if ((mx ^ my) & 1) == 0 else door_blue

# Player (spawn on a floor tile, centered)
spawn_x, spawn_y = pick_spawn(BASE_MAP)
player_pos = pygame.Vector2(spawn_x, spawn_y)
player_ang = 0.0

# Joystick (optional)
joy = None
if pygame.joystick.get_count() > 0:
    joy = pygame.joystick.Joystick(0)
    joy.init()
    print("Joystick detected:", joy.get_name())
else:
    print("No joystick detected. Using keyboard controls.")

# ---------- Helpers ----------
def in_map(mx, my):
    return 0 <= mx < MAP_W and 0 <= my < MAP_H

# --- Distant Morphing helpers (new) ---
phase_timer = 0.0  # accumulates time

def _hash01(mx, my, phase_idx):
    # fast deterministic 0..1 hash based on coords+phase
    h = (mx * 73856093) ^ (my * 19349663) ^ (phase_idx * 83492791)
    h &= 0xFFFFFFFF
    # xorshift-ish
    h ^= (h << 13) & 0xFFFFFFFF
    h ^= (h >> 17)
    h ^= (h << 5) & 0xFFFFFFFF
    return ((h & 0xFFFFFFFF) / 0xFFFFFFFF)

def _perturb_tile(base_t, mx, my, phase_idx):
    r = _hash01(mx, my, phase_idx)
    if base_t == 2:
        # doors never morph
        return 2
    if r < FLIP_PROB:
        # flip logic: wall<->floor
        if base_t == 0:   # floor -> wall
            return 1
        elif base_t == 1: # wall -> floor
            return 0
    return base_t

def tile_at(mx, my, px, py, phase_idx):
    """Return the current (possibly morphed) tile value at map coords."""
    if not in_map(mx, my): return 1  # treat out of bounds as solid
    base_t = BASE_MAP[my][mx]

    # If morphing is disabled, lock to base reality.
    if not ENABLE_MORPH:
        return base_t

    # keep a safe bubble stable
    dx = (mx + 0.5) - px
    dy = (my + 0.5) - py
    if math.hypot(dx, dy) < SHUFFLE_SAFE_RADIUS:
        return base_t

    return _perturb_tile(base_t, mx, my, phase_idx)


def dynamic_wall_height_ft(mx, my, t, phase_idx):
    """Height for current tile t; generate deterministic height for morphed walls."""
    if t == 2:
        return DOOR_HEIGHT_FT
    if t == 1:
        base_t = BASE_MAP[my][mx]
        if base_t == 1:
            return WALL_HEIGHTS_FT[my][mx]
        # floor morphed into wall: synthesize height deterministically
        r = _hash01(mx, my, phase_idx)
        return WALL_MIN_HEIGHT_FT + (WALL_MAX_HEIGHT_FT - WALL_MIN_HEIGHT_FT) * r
    return 0.0

def is_blocking(mx, my, px, py, phase_idx):
    t = tile_at(mx, my, px, py, phase_idx)
    return t in (1, 2)

def try_move(nx, ny, phase_idx):
    # If debug noclip is enabled, allow movement through walls
    if DEBUG_NOCLIP:
        return True

    pad = 0.15
    mx0, my0 = int(nx - pad), int(ny - pad)
    mx1, my1 = int(nx + pad), int(ny + pad)
    for my in (my0, my1):
        for mx in (mx0, mx1):
            if is_blocking(mx, my, nx, ny, phase_idx):
                return False
    return True

# ---------- Raycasting (DDA) ----------
def cast_and_draw(phase_idx):
    # sky/floor
    screen.fill((20, 20, 28), rect=pygame.Rect(0, 0, SCREEN_W, SCREEN_H // 2))       # ceiling
    screen.fill((38, 38, 46), rect=pygame.Rect(0, SCREEN_H // 2, SCREEN_W, SCREEN_H // 2))  # floor

    for x in range(SCREEN_W):
        ray_angle = player_ang - HALF_FOV + (x + 0.5) * (FOV / SCREEN_W)
        ray_dir_x = math.cos(ray_angle)
        ray_dir_y = math.sin(ray_angle)

        map_x = int(player_pos.x)
        map_y = int(player_pos.y)

        inv_dx = 1.0 / ray_dir_x if ray_dir_x != 0 else 1e30
        inv_dy = 1.0 / ray_dir_y if ray_dir_y != 0 else 1e30
        delta_dist_x = abs(inv_dx)
        delta_dist_y = abs(inv_dy)

        if ray_dir_x < 0:
            step_x = -1
            side_dist_x = (player_pos.x - map_x) * delta_dist_x
        else:
            step_x = 1
            side_dist_x = (map_x + 1.0 - player_pos.x) * delta_dist_x

        if ray_dir_y < 0:
            step_y = -1
            side_dist_y = (player_pos.y - map_y) * delta_dist_y
        else:
            step_y = 1
            side_dist_y = (map_y + 1.0 - player_pos.y) * delta_dist_y

        hit = False
        side = 0
        tile = 0

        while True:
            # advance DDA
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1

            if not in_map(map_x, map_y):
                break

            tile = tile_at(map_x, map_y, player_pos.x, player_pos.y, phase_idx)
            if tile != 0:
                hit = True
                break

        if not hit:
            continue

        if side == 0:
            perp_dist = (map_x - player_pos.x + (1 - step_x) * 0.5) * inv_dx
        else:
            perp_dist = (map_y - player_pos.y + (1 - step_y) * 0.5) * inv_dy
        if perp_dist <= 0.0001:
            perp_dist = 0.0001

        base_line_h = SCREEN_H / perp_dist

        # dynamic height based on current (possibly morphed) tile
        if ENABLE_RAND_HEIGHTS:
            height_ft = dynamic_wall_height_ft(map_x, map_y, tile, phase_idx)
            scale = (height_ft / PLAYER_HEIGHT_FT) if height_ft > 0 else 1.0
            line_h = int(base_line_h * (scale if scale > 0 else 1.0))
        else:
            line_h = int(base_line_h)

        # textures
        if tile == 1:
            tex = pick_wall_texture(map_x, map_y)
        else:
            # For doors (tile == 2) choose a single canonical face that opens
            # onto a floor cell so the door texture won't be covered by another wall.
            # We look at neighboring BASE_MAP tiles to find the two floor sides
            # (doors are only sprinkled where there's a floor pair), prefer the
            # side that continues into floor (corridor), and fall back
            # deterministically if needed.
            show_door_texture = False
            # gather candidate directions where adjacent cell is floor
            floor_dirs = []
            # north
            if in_map(map_x, map_y - 1) and BASE_MAP[map_y - 1][map_x] == 0:
                floor_dirs.append((0, -1))
            # south
            if in_map(map_x, map_y + 1) and BASE_MAP[map_y + 1][map_x] == 0:
                floor_dirs.append((0, 1))
            # west
            if in_map(map_x - 1, map_y) and BASE_MAP[map_y][map_x - 1] == 0:
                floor_dirs.append((-1, 0))
            # east
            if in_map(map_x + 1, map_y) and BASE_MAP[map_y][map_x + 1] == 0:
                floor_dirs.append((1, 0))

            desired_face_dir = None
            # Prefer a direction where the neighbor continues into floor (corridor)
            for dx, dy in floor_dirs:
                nx, ny = map_x + dx, map_y + dy
                bx, by = nx + dx, ny + dy
                if in_map(bx, by) and BASE_MAP[by][bx] == 0:
                    desired_face_dir = (dx, dy)
                    break

            # If none continue, pick a deterministic choice from floor_dirs
            if desired_face_dir is None and floor_dirs:
                # pick based on tile parity for determinism
                idx = ((map_x + map_y) & 1) % len(floor_dirs)
                desired_face_dir = floor_dirs[idx]

            # Now determine which face was hit by the ray
            if desired_face_dir is not None:
                if side == 0:
                    # hit a vertical grid line -> face is east/west
                    face_dir = (1, 0) if ray_dir_x > 0 else (-1, 0)
                else:
                    # hit a horizontal grid line -> face is north/south
                    face_dir = (0, 1) if ray_dir_y > 0 else (0, -1)

                if face_dir == desired_face_dir:
                    show_door_texture = True

            if show_door_texture:
                tex = pick_door_texture(map_x, map_y)
            else:
                tex = pick_wall_texture(map_x, map_y)

        if side == 0:
            wall_x = player_pos.y + perp_dist * ray_dir_y
        else:
            wall_x = player_pos.x + perp_dist * ray_dir_x
        wall_x -= math.floor(wall_x)

        tex_x = int(wall_x * TEX_SIZE)
        if side == 0 and ray_dir_x > 0:
            tex_x = TEX_SIZE - tex_x - 1
        if side == 1 and ray_dir_y < 0:
            tex_x = TEX_SIZE - tex_x - 1

        column = tex.subsurface(pygame.Rect(tex_x, 0, 1, TEX_SIZE))
        column = pygame.transform.scale(column, (1, line_h))

        draw_y = (SCREEN_H // 2) - (line_h // 2)

        if side == 1:
            screen.blit(column, (x, draw_y))
            shade = pygame.Surface((1, line_h), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 60))
            screen.blit(shade, (x, draw_y))
        else:
            screen.blit(column, (x, draw_y))

# ---------- Minimap ----------
def draw_minimap(phase_idx):
    # Choose cell size to keep the map compact
    max_dim = max(MAP_W, MAP_H)
    cell = max(3, min(12, 220 // max_dim))  # auto-scale nicely
    mm_w = MAP_W * cell
    mm_h = MAP_H * cell

    mm = pygame.Surface((mm_w, mm_h), pygame.SRCALPHA)
    # background
    bg = pygame.Surface((mm_w, mm_h), pygame.SRCALPHA)
    bg.fill((0, 0, 0, MINIMAP_BG_ALPHA))
    mm.blit(bg, (0, 0))

    # tiles (dynamic)
    for y in range(MAP_H):
        for x in range(MAP_W):
            r = pygame.Rect(x * cell, y * cell, cell, cell)
            t = tile_at(x, y, player_pos.x, player_pos.y, phase_idx)
            if t == 1:
                pygame.draw.rect(mm, MINIMAP_WALL, r)
            elif t == 0:
                pygame.draw.rect(mm, MINIMAP_FLOOR, r)
            else:  # door
                pygame.draw.rect(mm, MINIMAP_DOOR, r)

    # player
    px = player_pos.x * cell
    py = player_pos.y * cell
    pygame.draw.circle(mm, MINIMAP_PLAYER, (int(px), int(py)), max(2, cell // 3))

    # facing direction line
    dir_len = max(10, 3 * cell)
    dx = math.cos(player_ang) * dir_len
    dy = math.sin(player_ang) * dir_len
    pygame.draw.line(mm, MINIMAP_PLAYER, (px, py), (px + dx, py + dy), 2)

    # FOV cone
    fov_len = max(16, 4 * cell)
    left_ang = player_ang - HALF_FOV
    right_ang = player_ang + HALF_FOV
    lx, ly = px + math.cos(left_ang) * fov_len, py + math.sin(left_ang) * fov_len
    rx, ry = px + math.cos(right_ang) * fov_len, py + math.sin(right_ang) * fov_len
    pygame.draw.line(mm, MINIMAP_FOV, (px, py), (lx, ly), 1)
    pygame.draw.line(mm, MINIMAP_FOV, (px, py), (rx, ry), 1)

    # blit to screen
    screen.blit(mm, (MINIMAP_MARGIN, MINIMAP_MARGIN))

# ---------- Input (no strafe) ----------
def get_inputs(dt, phase_idx):
    global player_ang, player_pos

    keys = pygame.key.get_pressed()
    forward = 0.0
    turn = 0.0

    if keys[pygame.K_w]: forward += 1
    if keys[pygame.K_s]: forward -= 1
    if keys[pygame.K_a]: turn -= 1
    if keys[pygame.K_d]: turn += 1
    if keys[pygame.K_ESCAPE]:
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    if joy:
        y = -joy.get_axis(1)
        rx = joy.get_axis(0)
        if abs(y) < DEADZONE: y = 0.0
        if abs(rx) < DEADZONE: rx = 0.0
        forward += y
        turn += rx

    player_ang = (player_ang + turn * TURN_SPEED * dt) % (2 * math.pi)

    dx = math.cos(player_ang) * forward * MOVE_SPEED * dt
    dy = math.sin(player_ang) * forward * MOVE_SPEED * dt

    nx = player_pos.x + dx
    ny = player_pos.y + dy

    if try_move(nx, player_pos.y, phase_idx):
        player_pos.x = nx
    if try_move(player_pos.x, ny, phase_idx):
        player_pos.y = ny

def draw_hud():
    info = f"[M] Minimap: {'ON' if SHOW_MINIMAP else 'OFF'}   " \
        f"[R] Distant Morphing: {'ON' if ENABLE_MORPH else 'OFF'}   " \
        f"[H] Random Heights: {'ON' if ENABLE_RAND_HEIGHTS else 'OFF'}"
    # extra info: map size and FOV
    info2 = f"Map: {MAP_W}x{MAP_H}  (use '['/']' to -/+ size)   FOV: {int(math.degrees(FOV))}°  ('-'/'=' to -/+)"
    surf = HUD_FONT.render(info, True, (230, 230, 235))
    screen.blit(surf, (10, SCREEN_H - 38))
    surf2 = HUD_FONT.render(info2, True, (200, 200, 205))
    screen.blit(surf2, (10, SCREEN_H - 20))
    # debug indicators
    if DEBUG_MODE:
        dbg = f"DEBUG ON  (N: noclip={'ON' if DEBUG_NOCLIP else 'OFF'} | T: teleport | P: print)"
        surf3 = HUD_FONT.render(dbg, True, (255, 160, 80))
        screen.blit(surf3, (10, SCREEN_H - 56))

def main():
    global phase_timer, SHOW_MINIMAP, ENABLE_MORPH, ENABLE_RAND_HEIGHTS, FOV, HALF_FOV
    global WORLD_MAP, BASE_MAP, MAP_W, MAP_H, WALL_HEIGHTS_FT, MAZE_W, MAZE_H, player_pos
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        phase_timer += dt
        phase_idx = int(phase_timer // PHASE_PERIOD)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                # advance secret sequence state machine
                global _secret_idx, DEBUG_MODE, DEBUG_NOCLIP
                if _secret_idx < len(_SECRET_SEQ) and e.key == _SECRET_SEQ[_secret_idx]:
                    _secret_idx += 1
                    if _secret_idx == len(_SECRET_SEQ):
                        DEBUG_MODE = not DEBUG_MODE
                        _secret_idx = 0
                        print("DEBUG_MODE toggled:", "ON" if DEBUG_MODE else "OFF")
                else:
                    # reset on mismatch unless the key could be the start of the sequence
                    if e.key == _SECRET_SEQ[0]:
                        _secret_idx = 1
                    else:
                        _secret_idx = 0

                # Debug-only keybindings (active when DEBUG_MODE True)
                if DEBUG_MODE:
                    if e.key == pygame.K_n:
                        DEBUG_NOCLIP = not DEBUG_NOCLIP
                        print("DEBUG_NOCLIP:", "ON" if DEBUG_NOCLIP else "OFF")
                    elif e.key == pygame.K_t:
                        # teleport to center of map for quick testing
                        cx, cy = MAP_W // 2, MAP_H // 2
                        player_pos = pygame.Vector2(cx + 0.5, cy + 0.5)
                        print(f"Teleported to {cx},{cy}")
                    elif e.key == pygame.K_p:
                        # print some debug info
                        print(f"Player: ({player_pos.x:.2f}, {player_pos.y:.2f}) ang={player_ang:.2f}")
                    # fall through to regular key handlers below
                if e.key == pygame.K_m:
                    SHOW_MINIMAP = not SHOW_MINIMAP
                    print("Minimap:", "ON" if SHOW_MINIMAP else "OFF")
                elif e.key == pygame.K_r:
                    ENABLE_MORPH = not ENABLE_MORPH
                    print("Distant Morphing:", "ON" if ENABLE_MORPH else "OFF")
                elif e.key == pygame.K_h:
                    ENABLE_RAND_HEIGHTS = not ENABLE_RAND_HEIGHTS
                    print("Random Heights:", "ON" if ENABLE_RAND_HEIGHTS else "OFF")
                elif e.key == pygame.K_LEFTBRACKET:  # '[' decrease map size
                    # decrease both dims by 2 (keep odd)
                    new_w = max(5, MAZE_W - 2)
                    new_h = max(5, MAZE_H - 2)
                    if new_w != MAZE_W or new_h != MAZE_H:
                        MAZE_W, MAZE_H = new_w, new_h
                        WORLD_MAP, BASE_MAP, MAP_W, MAP_H, WALL_HEIGHTS_FT = regenerate_map(MAZE_W, MAZE_H, seed=RNG_SEED)
                        spawn_x, spawn_y = pick_spawn(BASE_MAP)
                        player_pos = pygame.Vector2(spawn_x, spawn_y)
                        print(f"Map resized to {MAP_W}x{MAP_H}")
                elif e.key == pygame.K_RIGHTBRACKET:  # ']' increase map size
                    new_w = MAZE_W + 2
                    new_h = MAZE_H + 2
                    MAZE_W, MAZE_H = new_w, new_h
                    WORLD_MAP, BASE_MAP, MAP_W, MAP_H, WALL_HEIGHTS_FT = regenerate_map(MAZE_W, MAZE_H, seed=RNG_SEED)
                    spawn_x, spawn_y = pick_spawn(BASE_MAP)
                    player_pos = pygame.Vector2(spawn_x, spawn_y)
                    print(f"Map resized to {MAP_W}x{MAP_H}")
                elif e.key == pygame.K_MINUS or e.key == pygame.K_KP_MINUS:
                    # decrease FOV by 5 degrees, clamp to 20 deg
                    new_deg = max(20, int(math.degrees(FOV)) - 5)
                    FOV = math.radians(new_deg)
                    HALF_FOV = FOV * 0.5
                    print(f"FOV set to {new_deg}°")
                elif e.key == pygame.K_EQUALS or e.key == pygame.K_KP_PLUS:
                    # increase FOV by 5 degrees, clamp to 120 deg
                    new_deg = min(120, int(math.degrees(FOV)) + 5)
                    FOV = math.radians(new_deg)
                    HALF_FOV = FOV * 0.5
                    print(f"FOV set to {new_deg}°")

        get_inputs(dt, phase_idx)
        cast_and_draw(phase_idx)
        if SHOW_MINIMAP:
            draw_minimap(phase_idx)
        draw_hud()
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
