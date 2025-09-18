import math
import sys
import random
import pygame
import os

# =========================
# Config
# =========================
SCREEN_W, SCREEN_H = 960, 600
FOV = math.radians(66)
HALF_FOV = FOV * 0.5
MAX_VIEW_DIST = 32.0

MOVE_SPEED = 3.4
SPRINT_MULT = 1.6
TURN_SPEED = 2.2
DEADZONE = 0.12
TEX_SIZE = 64

# Map defaults (no generator)
MAP_W, MAP_H = 33, 25
MAP_SAVE_PATH = "map2.txt"
ENT_SAVE_PATH = "map_ents2.txt"

# Minimap
MINIMAP_MARGIN = 10
MINIMAP_BG_ALPHA = 120
MINIMAP_WALL = (70, 70, 80)
MINIMAP_FLOOR = (150, 150, 160)
MINIMAP_DOOR = (230, 200, 60)
MINIMAP_PLAYER = (255, 70, 90)
MINIMAP_FOV = (255, 255, 255)

# Heights
PLAYER_HEIGHT_FT = 6.0
WALL_MIN_HEIGHT_FT = 7.0
WALL_MAX_HEIGHT_FT = 12.0
DOOR_HEIGHT_FT = 7.0

# Game bits
START_HEALTH = 100
START_AMMO = 40
WEAPON_FIRE_RATE = 0.28
WEAPON_RANGE = 18.0
WEAPON_DAMAGE = (14, 26)
ENEMY_TOUCH_DAMAGE = 6
ENEMY_HP = 40
ENEMY_SPEED = 1.6
ENEMY_DETECT_RANGE = 20.0
# Additional enemy type base stats (multipliers / overrides)
ENEMY_TYPES = {
    # id: (display_name, hp, speed, detect_range, color_on_minimap, behavior)
    # behavior: 'chaser' (current), 'wander', 'patrol'
    "grunt": ("Grunt", ENEMY_HP, ENEMY_SPEED, ENEMY_DETECT_RANGE, (255,120,220), "chaser"),
    "scout": ("Scout", int(ENEMY_HP*0.6), ENEMY_SPEED*1.9, ENEMY_DETECT_RANGE*1.1, (255,200,120), "wander"),
    "brute": ("Brute", int(ENEMY_HP*2.0), ENEMY_SPEED*0.9, ENEMY_DETECT_RANGE*0.8, (255,60,120), "patrol"),
}
DEFAULT_ENEMY_TYPE = "grunt"
CURRENT_ENEMY_TYPE = DEFAULT_ENEMY_TYPE  # editor selection

# If you don't place any enemies/pickups, these fallbacks kick in:
FALLBACK_ENEMIES_COUNT = 10
FALLBACK_PICKUP_COUNT = 8
AMMO_PICKUP_AMOUNT = 16
MEDKIT_HEAL = 35

# Editor
EDITOR_BG = (18, 20, 24)
GRID_COLOR = (60, 64, 72)
GRID_BOLD = (95, 100, 110)
CURSOR_COLOR = (255, 255, 255)
CELL_PX_DEFAULT = 24
EDITOR_MIN_CELL = 8
EDITOR_MAX_CELL = 48

# =========================
# Init
# =========================
pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Microwave Raycaster (Play / Edit)")
clock = pygame.time.Clock()
HUD_FONT = pygame.font.SysFont(None, 20)
SMALL_FONT = pygame.font.SysFont(None, 16)
TITLE_FONT = pygame.font.SysFont(None, 48)
MENU_FONT = pygame.font.SysFont(None, 26)

# =========================
# Assets / placeholders
# =========================
def solid(size, color, alpha=False):
    f = pygame.SRCALPHA if alpha else 0
    s = pygame.Surface((size, size), f)
    s.fill(color)
    return s

def checker(size, a, b):
    s = pygame.Surface((size, size))
    tile = max(1, size // 8)
    for y in range(0, size, tile):
        for x in range(0, size, tile):
            s.fill(a if ((x//tile + y//tile) & 1)==0 else b, pygame.Rect(x,y,tile,tile))
    return s

def load_tex(path, size=TEX_SIZE, alpha=False, fallback=None):
    try:
        img = pygame.image.load(path).convert_alpha() if alpha else pygame.image.load(path).convert()
        return pygame.transform.scale(img, (size, size))
    except Exception:
        return pygame.transform.scale(fallback or checker(size, (90,90,100), (60,60,70)), (size, size))

def load_sprite(path, base_color):
    size = 64
    try:
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.scale(img, (size, size))
    except:
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(s, base_color, (size//2, size//2), size//2)
        pygame.draw.circle(s, (0,0,0,180), (size//2, size//2), size//2, 2)
        return s

stone = load_tex("cobblestone.png", TEX_SIZE, False, checker(TEX_SIZE,(120,120,130),(90,90,100)))
brick = load_tex("brick.jpg", TEX_SIZE, False, checker(TEX_SIZE,(150,70,70),(110,40,40)))
wood  = load_tex("wood.jpeg", TEX_SIZE, False, checker(TEX_SIZE,(120,90,60),(90,60,40)))
door_red = load_tex("red.png", TEX_SIZE, False, solid(TEX_SIZE,(200,40,40)))
door_blue= load_tex("blue.png", TEX_SIZE, False, solid(TEX_SIZE,(40,40,200)))

SPRITE_ENEMY  = load_sprite("enemy.png", (240, 80, 200))  # fallback / generic
SPRITE_AMMO   = load_sprite("pickup_ammo.png", (250, 230, 80))
SPRITE_MEDKIT = load_sprite("pickup_medkit.png", (120, 220, 120))
HUD_PISTOL    = load_sprite("pistol.png", (180, 180, 180))
MUZZLE_FLASH  = load_sprite("muzzle.png", (255, 240, 200))

# Per-type enemy sprites (attempt to load individual files, fallback to colored circles)
ENEMY_SPRITES = {
    "grunt": load_sprite("enemy_grunt.png", (240, 80, 200)),
    "scout": load_sprite("enemy_scout.png", (255, 200, 120)),
    "brute": load_sprite("enemy_brute.png", (255, 60, 120)),
}

def pick_wall_texture(mx, my):
    s = (mx + my) % 3
    return stone if s==0 else (brick if s==1 else wood)

def pick_door_texture(mx, my):
    return door_red if ((mx ^ my) & 1) == 0 else door_blue

# =========================
# Map storage (no generator)
# Tiles: 0=floor, 1=wall, 2=door
# =========================
def make_blank_map(w, h):
    grid = [[0 for _ in range(w)] for _ in range(h)]
    # perimeter walls
    for x in range(w):
        grid[0][x] = 1
        grid[h-1][x] = 1
    for y in range(h):
        grid[y][0] = 1
        grid[y][w-1] = 1
    # one door at the middle of the top wall
    if w >= 3:
        door_x = w // 2
        grid[0][door_x] = 2
    return grid

def clamp(v, lo, hi): return max(lo, min(hi, v))

def resize_map(grid, new_w, new_h):
    old_h = len(grid); old_w = len(grid[0])
    new_grid = make_blank_map(new_w, new_h)
    for y in range(min(old_h, new_h)):
        for x in range(min(old_w, new_w)):
            # keep old interior where possible
            if 0 < y < new_h-1 and 0 < x < new_w-1:
                new_grid[y][x] = grid[y][x]
    return new_grid

def save_map(grid, path=MAP_SAVE_PATH):
    with open(path, "w") as f:
        for row in grid:
            f.write("".join(str(clamp(v,0,2)) for v in row) + "\n")
    print(f"Saved map to {path}")

def load_map(path=MAP_SAVE_PATH):
    if not os.path.exists(path):
        print(f"No {path}, making a fresh blank map.")
        return make_blank_map(MAP_W, MAP_H)
    grid = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            row = [clamp(int(ch),0,2) if ch.isdigit() else 1 for ch in line]
            grid.append(row)
    # normalize rectangle
    w = max(len(r) for r in grid)
    for r in grid:
        if len(r) < w:
            r.extend([1]*(w-len(r)))
    return grid

BASE_MAP = make_blank_map(MAP_W, MAP_H)  # Edited here
MAP_H = len(BASE_MAP); MAP_W = len(BASE_MAP[0])

# wall heights (static)
WALL_HEIGHTS_FT = [[(random.uniform(WALL_MIN_HEIGHT_FT, WALL_MAX_HEIGHT_FT) if t==1 else (DOOR_HEIGHT_FT if t==2 else 0.0))
                    for t in row] for row in BASE_MAP]

def in_map(mx, my): return 0 <= mx < MAP_W and 0 <= my < MAP_H
def is_blocking_tile(t): return t in (1,2)
def is_blocking(mx, my):
    if not in_map(mx, my): return True
    return is_blocking_tile(BASE_MAP[my][mx])

# =========================
# Entity placement (cells)
# =========================
ENEMY_CELLS  = {}        # {(x,y): enemy_type, ...}
AMMO_CELLS   = set()
MEDKIT_CELLS = set()
SPAWN_CELL   = None      # (x,y) or None

def clear_entities():
    global ENEMY_CELLS, AMMO_CELLS, MEDKIT_CELLS, SPAWN_CELL
    ENEMY_CELLS.clear()
    AMMO_CELLS.clear()
    MEDKIT_CELLS.clear()
    SPAWN_CELL = None

def cell_has_entity(x, y):
    if (x,y) in ENEMY_CELLS: return "enemy"
    if (x,y) in AMMO_CELLS: return "ammo"
    if (x,y) in MEDKIT_CELLS: return "medkit"
    if SPAWN_CELL == (x,y): return "spawn"
    return None

def remove_entity_at(x, y):
    global SPAWN_CELL
    ENEMY_CELLS.pop((x,y), None)
    AMMO_CELLS.discard((x,y))
    MEDKIT_CELLS.discard((x,y))
    if SPAWN_CELL == (x,y): SPAWN_CELL = None

def place_entity_at(x, y, kind):
    """kind: 'enemy'|'ammo'|'medkit'|'spawn'"""
    if not in_map(x,y): return
    if BASE_MAP[y][x] != 0:  # only place on floor
        return
    remove_entity_at(x, y)
    global SPAWN_CELL, CURRENT_ENEMY_TYPE
    if kind == "enemy":
        ENEMY_CELLS[(x,y)] = CURRENT_ENEMY_TYPE if CURRENT_ENEMY_TYPE in ENEMY_TYPES else DEFAULT_ENEMY_TYPE
    elif kind == "ammo":
        AMMO_CELLS.add((x,y))
    elif kind == "medkit":
        MEDKIT_CELLS.add((x,y))
    elif kind == "spawn":
        SPAWN_CELL = (x,y)

def save_entities(path=ENT_SAVE_PATH):
    with open(path, "w") as f:
        if SPAWN_CELL:
            f.write(f"spawn {SPAWN_CELL[0]} {SPAWN_CELL[1]}\n")
        for (x,y), etype in sorted(ENEMY_CELLS.items()):
            f.write(f"enemy {etype} {x} {y}\n")
        for x,y in sorted(AMMO_CELLS):   f.write(f"ammo {x} {y}\n")
        for x,y in sorted(MEDKIT_CELLS): f.write(f"medkit {x} {y}\n")
    print(f"Saved entities to {path}")

def load_entities(path=ENT_SAVE_PATH):
    clear_entities()
    if not os.path.exists(path):
        print(f"No {path}; starting with no entities.")
        return
    with open(path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if not parts: continue
            if parts[0] == "spawn" and len(parts) == 3:
                _, sx, sy = parts
                if sx.isdigit() and sy.isdigit():
                    x, y = int(sx), int(sy)
                    if in_map(x,y) and BASE_MAP[y][x]==0:
                        global SPAWN_CELL
                        SPAWN_CELL = (x,y)
            elif parts[0] == "enemy":
                # new format: enemy type x y
                # old format: enemy x y
                if len(parts) == 4:
                    _, etype, sx, sy = parts
                elif len(parts) == 3:
                    _, sx, sy = parts; etype = "grunt"
                else:
                    continue
                if sx.isdigit() and sy.isdigit():
                    x, y = int(sx), int(sy)
                    if in_map(x,y) and BASE_MAP[y][x]==0:
                        if etype not in ENEMY_TYPES: etype = "grunt"
                        ENEMY_CELLS[(x,y)] = etype
            elif parts[0] == "ammo" and len(parts) == 3:
                _, sx, sy = parts
                if sx.isdigit() and sy.isdigit():
                    x, y = int(sx), int(sy)
                    if in_map(x,y) and BASE_MAP[y][x]==0:
                        AMMO_CELLS.add((x,y))
            elif parts[0] == "medkit" and len(parts) == 3:
                _, sx, sy = parts
                if sx.isdigit() and sy.isdigit():
                    x, y = int(sx), int(sy)
                    if in_map(x,y) and BASE_MAP[y][x]==0:
                        MEDKIT_CELLS.add((x,y))

def filter_entities_within_bounds():
    """Drop any entities that moved out of bounds after a resize."""
    global SPAWN_CELL
    # filter enemy dict
    for pos in list(ENEMY_CELLS.keys()):
        if not in_map(pos[0], pos[1]):
            ENEMY_CELLS.pop(pos, None)
    AMMO_CELLS.intersection_update({(x,y) for y in range(MAP_H) for x in range(MAP_W)})
    MEDKIT_CELLS.intersection_update({(x,y) for y in range(MAP_H) for x in range(MAP_W)})
    if SPAWN_CELL and not in_map(*SPAWN_CELL):
        SPAWN_CELL = None

# =========================
# Player / game state
# =========================
def first_floor_spawn():
    for y in range(1, MAP_H-1):
        for x in range(1, MAP_W-1):
            if BASE_MAP[y][x] == 0:
                return (x+0.5, y+0.5)
    return (1.5, 1.5)

def spawn_from_entities():
    if SPAWN_CELL: return (SPAWN_CELL[0]+0.5, SPAWN_CELL[1]+0.5)
    return first_floor_spawn()

player_pos = pygame.Vector2(*spawn_from_entities())
player_ang = 0.0
player_health = START_HEALTH
player_ammo = START_AMMO
time_since_shot = 999.0
died = False
win = False
START_MENU = True   # start at main menu
PAUSED = False      # pause overlay flag
EDITOR_MODE = False # start outside editor; menu chooses
SHOW_MINIMAP_PLAY = True

# Mouse look (will be enabled on play start)
pygame.event.set_grab(False)
pygame.mouse.set_visible(True)
MOUSE_SENS = 0.0026

# Enemies / pickups at runtime
class SpriteEnt:
    def __init__(self, x, y, surf, kind, enemy_type=None):
        self.pos = pygame.Vector2(x, y)
        self.surf = surf
        self.kind = kind  # 'enemy' or 'pickup'
        self.enemy_type = enemy_type if (kind == "enemy" and enemy_type in ENEMY_TYPES) else (DEFAULT_ENEMY_TYPE if kind=="enemy" else None)
        if self.enemy_type:
            data = ENEMY_TYPES[self.enemy_type]
            self.hp = data[1]
            self.base_speed = data[2]
            self.detect_range = data[3]
            self.minimap_color = data[4]
            self.behavior = data[5]
        else:
            self.hp = ENEMY_HP if kind=="enemy" else 1
            self.base_speed = ENEMY_SPEED
            self.detect_range = ENEMY_DETECT_RANGE
            self.minimap_color = (255,120,220)
            self.behavior = "chaser"
        self.alive = True
        self.pickup_type = None
        self.cooldown = 0.0
        # Behavior state
        self.wander_dir = pygame.Vector2(random.uniform(-1,1), random.uniform(-1,1)) if self.behavior=="wander" else pygame.Vector2()
        if self.wander_dir.length_squared() > 0:
            self.wander_dir = self.wander_dir.normalize()
        self.wander_timer = 0.0
        self.patrol_points = []
        self.patrol_index = 0
        self._init_patrol()

    def _init_patrol(self):
        if self.behavior != "patrol":
            return
        # Create a simple square/loop of points near the spawn cell (within open floor)
        cx, cy = int(self.pos.x), int(self.pos.y)
        candidates = []
        # sample a 5x5 ring for walkable cells
        for dy in range(-3,4):
            for dx in range(-3,4):
                mx, my = cx+dx, cy+dy
                if in_map(mx,my) and BASE_MAP[my][mx]==0:
                    candidates.append((mx+0.5,my+0.5))
        random.shuffle(candidates)
        # pick up to 4 distinct points
        self.patrol_points = candidates[:4] if len(candidates)>=2 else [self.pos.xy]
        self.patrol_index = 0

    def patrol_target(self):
        if not self.patrol_points:
            return self.pos
        return pygame.Vector2(*self.patrol_points[self.patrol_index])

    def advance_patrol(self):
        if not self.patrol_points:
            return
        self.patrol_index = (self.patrol_index + 1) % len(self.patrol_points)

def to_center(x, y): return (x+0.5, y+0.5)

def spawn_enemies_from_cells():
    spawned = []
    for (x,y), etype in ENEMY_CELLS.items():
        sprite = ENEMY_SPRITES.get(etype, SPRITE_ENEMY)
        spawned.append(SpriteEnt(*to_center(x,y), sprite, "enemy", enemy_type=etype))
    return spawned

def spawn_pickups_from_cells():
    arr = []
    for (x,y) in AMMO_CELLS:
        s = SpriteEnt(*to_center(x,y), SPRITE_AMMO, "pickup"); s.pickup_type="ammo"; arr.append(s)
    for (x,y) in MEDKIT_CELLS:
        s = SpriteEnt(*to_center(x,y), SPRITE_MEDKIT, "pickup"); s.pickup_type="medkit"; arr.append(s)
    return arr

def place_free_cell():
    for _ in range(500):
        x = random.randint(1, MAP_W-2)
        y = random.randint(1, MAP_H-2)
        if BASE_MAP[y][x]==0 and cell_has_entity(x,y) is None:
            return (x+0.5, y+0.5)
    return (1.5, 1.5)

def spawn_enemies_fallback(n):
    arr = []
    for _ in range(n):
        x,y = place_free_cell()
        arr.append(SpriteEnt(x,y,SPRITE_ENEMY,"enemy"))
    return arr

def spawn_pickups_fallback(n):
    arr = []
    for _ in range(n):
        x,y = place_free_cell()
        if random.random()<0.5:
            s = SpriteEnt(x,y,SPRITE_AMMO,"pickup"); s.pickup_type="ammo"
        else:
            s = SpriteEnt(x,y,SPRITE_MEDKIT,"pickup"); s.pickup_type="medkit"
        arr.append(s)
    return arr

def reset_run_from_map():
    global player_pos, player_ang, player_health, player_ammo, time_since_shot, died, win, enemies, pickups
    player_pos = pygame.Vector2(*spawn_from_entities())
    player_ang = 0.0
    player_health = START_HEALTH
    player_ammo = START_AMMO
    time_since_shot = 999.0
    died = False; win = False
    enemies = spawn_enemies_from_cells()
    pickups = spawn_pickups_from_cells()

enemies = []
pickups = []
reset_run_from_map()

# =========================
# Movement / raycasting
# =========================
def try_move(nx, ny):
    pad = 0.18
    mx0, my0 = int(nx - pad), int(ny - pad)
    mx1, my1 = int(nx + pad), int(ny + pad)
    for my in (my0, my1):
        for mx in (mx0, mx1):
            if is_blocking(mx, my):
                return False
    return True

def cast_and_draw(zbuf):
    screen.fill((18, 18, 26), rect=pygame.Rect(0, 0, SCREEN_W, SCREEN_H // 2))
    screen.fill((38, 38, 46), rect=pygame.Rect(0, SCREEN_H // 2, SCREEN_W, SCREEN_H // 2))
    for x in range(SCREEN_W):
        ray_angle = player_ang - HALF_FOV + (x + 0.5) * (FOV / SCREEN_W)
        ray_dir_x = math.cos(ray_angle); ray_dir_y = math.sin(ray_angle)
        map_x = int(player_pos.x); map_y = int(player_pos.y)
        inv_dx = 1.0 / ray_dir_x if ray_dir_x != 0 else 1e30
        inv_dy = 1.0 / ray_dir_y if ray_dir_y != 0 else 1e30
        delta_x = abs(inv_dx); delta_y = abs(inv_dy)

        if ray_dir_x < 0:
            step_x = -1; side_x = (player_pos.x - map_x) * delta_x
        else:
            step_x = 1; side_x = (map_x + 1.0 - player_pos.x) * delta_x
        if ray_dir_y < 0:
            step_y = -1; side_y = (player_pos.y - map_y) * delta_y
        else:
            step_y = 1; side_y = (map_y + 1.0 - player_pos.y) * delta_y

        hit = False; side = 0; tile = 0
        while True:
            if side_x < side_y:
                side_x += delta_x; map_x += step_x; side = 0
            else:
                side_y += delta_y; map_y += step_y; side = 1
            if not in_map(map_x, map_y): break
            tile = BASE_MAP[map_y][map_x]
            if tile != 0: hit = True; break

        if not hit:
            zbuf[x] = MAX_VIEW_DIST
            continue

        perp_dist = ((map_x - player_pos.x + (1 - step_x) * 0.5) * inv_dx) if side==0 else ((map_y - player_pos.y + (1 - step_y) * 0.5) * inv_dy)
        perp_dist = max(perp_dist, 1e-4)
        zbuf[x] = perp_dist
        line_h = int(SCREEN_H / perp_dist)

        tex = pick_wall_texture(map_x, map_y) if tile==1 else pick_door_texture(map_x, map_y)
        wall_x = (player_pos.y + perp_dist * ray_dir_y) if side==0 else (player_pos.x + perp_dist * ray_dir_x)
        wall_x -= math.floor(wall_x)
        tex_x = int(wall_x * TEX_SIZE)
        if side == 0 and ray_dir_x > 0: tex_x = TEX_SIZE - tex_x - 1
        if side == 1 and ray_dir_y < 0: tex_x = TEX_SIZE - tex_x - 1
        column = tex.subsurface(pygame.Rect(tex_x, 0, 1, TEX_SIZE))
        column = pygame.transform.scale(column, (1, line_h))
        draw_y = (SCREEN_H // 2) - (line_h // 2)
        if side == 1:
            screen.blit(column, (x, draw_y))
            shade = pygame.Surface((1, line_h), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 60)); screen.blit(shade, (x, draw_y))
        else:
            screen.blit(column, (x, draw_y))

def render_sprites(zbuf):
    # gather
    things = []
    for e in enemies:
        if e.alive: things.append(("enemy", e.pos, e.surf, e))
    for p in pickups:
        if p.alive: things.append(("pickup", p.pos, p.surf, p))
    # sort far -> near
    things.sort(key=lambda t: (player_pos - t[1]).length(), reverse=True)

    for kind, pos, surf, obj in things:
        dx = pos.x - player_pos.x; dy = pos.y - player_pos.y
        dist = math.hypot(dx, dy)
        if dist < 1e-3: continue
        angle = math.atan2(dy, dx) - player_ang
        while angle < -math.pi: angle += 2*math.pi
        while angle >  math.pi: angle -= 2*math.pi
        if abs(angle) > HALF_FOV + 0.6:
            continue
        screen_x = int((0.5 + angle / FOV) * SCREEN_W)
        size = max(12, int((SCREEN_H / dist) * 0.9))
        sprite = pygame.transform.scale(surf, (size, size))
        top = (SCREEN_H // 2) - size // 2
        left = screen_x - size // 2

        for sx in range(size):
            x = left + sx
            if x < 0 or x >= SCREEN_W: continue
            if dist >= zbuf[x] + 0.01: continue
            column = sprite.subsurface(pygame.Rect(sx, 0, 1, size))
            # simple alpha pass; sprite surfaces are RGBA
            screen.blit(column, (x, top))

def line_of_sight(a, b):
    dx = b.x - a.x; dy = b.y - a.y
    dist = math.hypot(dx, dy)
    steps = int(dist * 8) + 1
    for i in range(steps+1):
        t = i/steps
        x = a.x + dx*t; y = a.y + dy*t
        mx, my = int(x), int(y)
        if not in_map(mx, my) or is_blocking(mx, my):
            return False
    return True

def update_enemies(dt):
    global player_health
    for e in enemies:
        if not e.alive: continue
        e.cooldown = max(0.0, e.cooldown - dt)
        to_p = player_pos - e.pos
        dist = to_p.length()
        if dist < 0.001:
            continue
        # Determine if player detected based on enemy-specific range
        detected = (dist < e.detect_range and line_of_sight(e.pos, player_pos))
        speed = e.base_speed
        moved = False
        if e.behavior == "chaser":
            if detected:
                dir = to_p.normalize()
                nx = e.pos.x + dir.x * speed * dt
                ny = e.pos.y + dir.y * speed * dt
                if not is_blocking(int(nx), int(e.pos.y)): e.pos.x = nx; moved=True
                if not is_blocking(int(e.pos.x), int(ny)): e.pos.y = ny; moved=True
        elif e.behavior == "wander":
            if detected:
                dir = to_p.normalize()
            else:
                e.wander_timer -= dt
                if e.wander_timer <= 0:
                    e.wander_dir = pygame.Vector2(random.uniform(-1,1), random.uniform(-1,1))
                    if e.wander_dir.length_squared()>0:
                        e.wander_dir = e.wander_dir.normalize()
                    e.wander_timer = random.uniform(1.0, 2.4)
                dir = e.wander_dir
            nx = e.pos.x + dir.x * speed * dt
            ny = e.pos.y + dir.y * speed * dt
            if not is_blocking(int(nx), int(e.pos.y)): e.pos.x = nx; moved=True
            if not is_blocking(int(e.pos.x), int(ny)): e.pos.y = ny; moved=True
        elif e.behavior == "patrol":
            tgt = e.patrol_target()
            dvec = tgt - e.pos
            dlen = dvec.length()
            if detected:
                dir = to_p.normalize()
            else:
                if dlen < 0.2:
                    e.advance_patrol()
                    tgt = e.patrol_target(); dvec = tgt - e.pos; dlen = dvec.length()
                dir = dvec.normalize() if dlen>0.001 else pygame.Vector2()
            nx = e.pos.x + dir.x * speed * dt
            ny = e.pos.y + dir.y * speed * dt
            if not is_blocking(int(nx), int(e.pos.y)): e.pos.x = nx; moved=True
            if not is_blocking(int(e.pos.x), int(ny)): e.pos.y = ny; moved=True
        # Touch damage
        if dist < 0.6 and e.cooldown <= 0.0:
            player_hurt(ENEMY_TOUCH_DAMAGE)
            e.cooldown = 0.8

def try_pickups():
    global player_ammo, player_health
    for p in pickups:
        if not p.alive: continue
        if (p.pos - player_pos).length() < 0.7:
            if p.pickup_type == "ammo":
                player_ammo += AMMO_PICKUP_AMOUNT
            else:
                player_health = min(100, player_health + MEDKIT_HEAL)
            p.alive = False

muzzle_alpha = 0.0
def player_hurt(dmg):
    global player_health, died
    player_health = max(0, player_health - dmg)
    if player_health <= 0: died = True

def hitscan_shot():
    global player_ammo, time_since_shot, muzzle_alpha
    if time_since_shot < WEAPON_FIRE_RATE or player_ammo <= 0: return
    player_ammo -= 1
    time_since_shot = 0.0
    muzzle_alpha = 1.0
    best = None; bestDist = 1e9
    for e in enemies:
        if not e.alive: continue
        to = e.pos - player_pos
        dist = to.length()
        if dist > WEAPON_RANGE: continue
        ang = math.atan2(to.y, to.x) - player_ang
        while ang < -math.pi: ang += 2*math.pi
        while ang >  math.pi: ang -= 2*math.pi
        if abs(ang) > math.radians(4.0): continue
        if not line_of_sight(player_pos, e.pos): continue
        if dist < bestDist: bestDist = dist; best = e
    if best:
        dmg = random.randint(*WEAPON_DAMAGE)
        best.hp -= dmg
        if best.hp <= 0: best.alive = False

def draw_minimap():
    max_dim = max(MAP_W, MAP_H)
    cell = max(3, min(12, 220 // max_dim))
    mm_w = MAP_W * cell; mm_h = MAP_H * cell
    mm = pygame.Surface((mm_w, mm_h), pygame.SRCALPHA)
    bg = pygame.Surface((mm_w, mm_h), pygame.SRCALPHA); bg.fill((0,0,0,MINIMAP_BG_ALPHA))
    mm.blit(bg, (0, 0))
    for y in range(MAP_H):
        for x in range(MAP_W):
            r = pygame.Rect(x * cell, y * cell, cell, cell)
            t = BASE_MAP[y][x]
            if t == 1: pygame.draw.rect(mm, MINIMAP_WALL, r)
            elif t == 0: pygame.draw.rect(mm, MINIMAP_FLOOR, r)
            else: pygame.draw.rect(mm, MINIMAP_DOOR, r)
    # dynamic entities on minimap
    # Draw remaining (uncollected) pickups from runtime list instead of static cell sets
    for p in pickups:
        if not p.alive: continue
        x = p.pos.x; y = p.pos.y
        col = (255,240,120) if p.pickup_type=="ammo" else (140,250,160)
        pygame.draw.rect(mm, col, pygame.Rect(int(x*cell)-cell//4, int(y*cell)-cell//4, cell//2, cell//2))
    # Draw enemies by their live positions & type color
    for e in enemies:
        if not e.alive: continue
        col = getattr(e, 'minimap_color', (255,120,220))
        pygame.draw.rect(mm, col, pygame.Rect(int(e.pos.x*cell)-cell//3, int(e.pos.y*cell)-cell//3, (2*cell)//3, (2*cell)//3))
    # spawn marker remains static
    if SPAWN_CELL:
        sx, sy = SPAWN_CELL
        pygame.draw.rect(mm, (120,200,255), pygame.Rect(sx*cell+cell//4, sy*cell+cell//4, cell//2, cell//2), 2)

    px = player_pos.x * cell; py = player_pos.y * cell
    pygame.draw.circle(mm, MINIMAP_PLAYER, (int(px), int(py)), max(2, cell // 3))
    dir_len = max(10, 3 * cell)
    dx = math.cos(player_ang) * dir_len; dy = math.sin(player_ang) * dir_len
    pygame.draw.line(mm, MINIMAP_PLAYER, (px, py), (px + dx, py + dy), 2)
    left_ang = player_ang - HALF_FOV; right_ang = player_ang + HALF_FOV
    fov_len = max(16, 4 * cell)
    lx, ly = px + math.cos(left_ang)*fov_len, py + math.sin(left_ang)*fov_len
    rx, ry = px + math.cos(right_ang)*fov_len, py + math.sin(right_ang)*fov_len
    pygame.draw.line(mm, MINIMAP_FOV, (px, py), (lx, ly), 1)
    pygame.draw.line(mm, MINIMAP_FOV, (px, py), (rx, ry), 1)
    screen.blit(mm, (MINIMAP_MARGIN, MINIMAP_MARGIN))

def get_inputs(dt):
    global player_ang, player_pos
    keys = pygame.key.get_pressed()
    forward = 0.0; strafe = 0.0; turn_kb = 0.0
    if keys[pygame.K_w]: forward += 1
    if keys[pygame.K_s]: forward -= 1
    if keys[pygame.K_a]: strafe -= 1
    if keys[pygame.K_d]: strafe += 1
    if keys[pygame.K_LEFT]:  turn_kb -= 1
    if keys[pygame.K_RIGHT]: turn_kb += 1
    if keys[pygame.K_ESCAPE]: pygame.event.post(pygame.event.Event(pygame.QUIT))
    mx, my = pygame.mouse.get_rel()
    player_ang = (player_ang + mx * MOUSE_SENS) % (2*math.pi)
    if turn_kb != 0.0:
        player_ang = (player_ang + turn_kb * TURN_SPEED * dt) % (2*math.pi)
    speed = MOVE_SPEED * (SPRINT_MULT if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] else 1.0)
    sin_a = math.sin(player_ang); cos_a = math.cos(player_ang)
    dx = (cos_a * forward - sin_a * strafe) * speed * dt
    dy = (sin_a * forward + cos_a * strafe) * speed * dt
    nx = player_pos.x + dx; ny = player_pos.y + dy
    if try_move(nx, player_pos.y): player_pos.x = nx
    if try_move(player_pos.x, ny): player_pos.y = ny

def draw_crosshair():
    col = (255,255,255)
    cx, cy = SCREEN_W//2, SCREEN_H//2
    pygame.draw.line(screen, col, (cx-8, cy), (cx-2, cy), 2)
    pygame.draw.line(screen, col, (cx+2, cy), (cx+8, cy), 2)
    pygame.draw.line(screen, col, (cx, cy-8), (cx, cy-2), 2)
    pygame.draw.line(screen, col, (cx, cy+2), (cx, cy+8), 2)

def draw_panel(x, y, w, h, alpha=170):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((8, 10, 14, alpha))
    pygame.draw.rect(s, (70,75,85, min(alpha+20,255)), (0,0,w,h), 2)
    screen.blit(s, (x,y))

def draw_fps():
    fps = clock.get_fps()
    txt = SMALL_FONT.render(f"{fps:5.1f} FPS", True, (200,200,210))
    screen.blit(txt, (SCREEN_W - txt.get_width() - 8, 6))

def draw_center_message(title, subtitle, color):
    title_surf = MENU_FONT.render(title, True, color)
    sub_surf = SMALL_FONT.render(subtitle, True, (230,230,235))
    pad = 24
    w = max(title_surf.get_width(), sub_surf.get_width()) + pad
    h = title_surf.get_height() + sub_surf.get_height() + pad
    x = SCREEN_W//2 - w//2
    y = SCREEN_H//2 - h//2 - 80
    draw_panel(x, y, w, h)
    screen.blit(title_surf, (x + (w-title_surf.get_width())//2, y + 12))
    screen.blit(sub_surf, (x + (w-sub_surf.get_width())//2, y + 16 + title_surf.get_height()))

def draw_start_menu():
    title = TITLE_FONT.render("Microwave Raycaster", True, (245,245,250))
    subtitle = SMALL_FONT.render("Retro raycaster + map editor", True, (200,200,205))
    opts = ["[1] Play Game", "[2] Map Editor", "[H] Controls / Help", "[ESC] Quit"]
    help_lines = [
        "WASD move  Mouse look  Shift sprint  Space/LMB shoot",
        "M toggle minimap  E editor  P pause  R restart (if dead/win)",
        "Editor: 0/1/2 tiles 3 enemy 4 ammo 5 medkit 6 spawn",
        "Ctrl+S save  Ctrl+L load  G/S/B enemy type  Wheel zoom"
    ]
    total_h = title.get_height()+subtitle.get_height()+20+len(opts)*28+18+len(help_lines)*18
    w = 660; h = total_h+40
    x = SCREEN_W//2 - w//2; y = SCREEN_H//2 - h//2
    draw_panel(x, y, w, h, 190)
    screen.blit(title, (x + (w-title.get_width())//2, y + 14))
    screen.blit(subtitle, (x + (w-subtitle.get_width())//2, y + 14 + title.get_height()))
    oy = y + 20 + title.get_height() + subtitle.get_height()
    for line in opts:
        s = MENU_FONT.render(line, True, (235,235,240))
        screen.blit(s, (x + 28, oy))
        oy += 28
    oy += 6
    for line in help_lines:
        s = SMALL_FONT.render(line, True, (205,205,210))
        screen.blit(s, (x + 28, oy))
        oy += 18
    draw_fps()

def draw_pause_menu():
    lines = ["[R] Resume","[T] Restart Run","[E] Editor","[M] Main Menu","[ESC] Quit Game"]
    w = 380; h = 48 + len(lines)*30
    x = SCREEN_W//2 - w//2; y = SCREEN_H//2 - h//2
    draw_panel(x, y, w, h)
    title = MENU_FONT.render("Paused", True, (240,240,245))
    screen.blit(title, (x + (w-title.get_width())//2, y + 12))
    oy = y + 16 + title.get_height()
    for ln in lines:
        s = SMALL_FONT.render(ln, True, (220,220,230))
        screen.blit(s, (x + 24, oy))
        oy += 30
    draw_fps()

# We override original simple HUD with enhanced UI helpers
# (Locate old draw_hud definition later in file and consider everything after it until main() updated.)
def draw_hud(show_minimap=True):  # override
    global muzzle_alpha
    alive_enemies = sum(1 for e in enemies if e.alive)
    total_enemies = len(enemies)
    if total_enemies > 0:
        info = f"HP {player_health:3d}  AMMO {player_ammo:3d}  ENEMIES {total_enemies - alive_enemies}/{total_enemies}"
    else:
        info = f"HP {player_health:3d}  AMMO {player_ammo:3d}"
    surf = HUD_FONT.render(info, True, (240, 240, 245))
    screen.blit(surf, (10, SCREEN_H - 30))
    wp = pygame.transform.scale(HUD_PISTOL, (160, 160))
    screen.blit(wp, (SCREEN_W//2 - 80, SCREEN_H - 160))
    if muzzle_alpha > 0:
        mf = pygame.transform.scale(MUZZLE_FLASH, (120, 120)).copy()
        mf.set_alpha(int(220 * muzzle_alpha))
        screen.blit(mf, (SCREEN_W//2 - 60, SCREEN_H - 180))
    if died:
        draw_center_message("YOU DIED", "[R]estart  [E]ditor  [M]enu  [ESC] Quit", (255,90,90))
    elif win:
        draw_center_message("AREA CLEARED", "[R]estart  [E]ditor  [M]enu  [ESC] Quit", (120,255,160))
    else:
        draw_crosshair()
    draw_fps()

# Helper to restart run (idempotent)
def restart_run():
    reset_run_from_map()

# =========================
# Editor (restored)
# =========================
# Brushes: 0=floor,1=wall,2=door,3=enemy,4=ammo,5=medkit,6=spawn
BRUSH = 1
cell_px = CELL_PX_DEFAULT

def update_map_dimensions():
    global MAP_W, MAP_H
    MAP_H = len(BASE_MAP); MAP_W = len(BASE_MAP[0])

def resize_to(new_w, new_h):
    global BASE_MAP, WALL_HEIGHTS_FT
    BASE_MAP[:] = resize_map(BASE_MAP, new_w, new_h)
    update_map_dimensions()
    WALL_HEIGHTS_FT[:] = [[(random.uniform(WALL_MIN_HEIGHT_FT, WALL_MAX_HEIGHT_FT) if t==1 else (DOOR_HEIGHT_FT if t==2 else 0.0))
                           for t in row] for row in BASE_MAP]
    filter_entities_within_bounds()

def editor_draw():
    screen.fill(EDITOR_BG)
    gw, gh = MAP_W*cell_px, MAP_H*cell_px
    origin_x = (SCREEN_W - gw)//2
    origin_y = (SCREEN_H - gh)//2
    # tiles
    for y in range(MAP_H):
        for x in range(MAP_W):
            t = BASE_MAP[y][x]
            r = pygame.Rect(origin_x + x*cell_px, origin_y + y*cell_px, cell_px, cell_px)
            if t == 0: col = (32, 34, 40)
            elif t == 1: col = (80, 86, 100)
            else: col = (160, 130, 40)
            pygame.draw.rect(screen, col, r)
    # entities
    def blit_icon(surf, cx, cy):
        size = max(6, cell_px - 4)
        icon = pygame.transform.smoothscale(surf, (size, size))
        screen.blit(icon, (origin_x + cx*cell_px + (cell_px-size)//2, origin_y + cy*cell_px + (cell_px-size)//2))
    for (x,y), etype in ENEMY_CELLS.items():
        icon = ENEMY_SPRITES.get(etype, SPRITE_ENEMY)
        blit_icon(icon, x, y)
    for (x,y) in AMMO_CELLS:   blit_icon(SPRITE_AMMO, x, y)
    for (x,y) in MEDKIT_CELLS: blit_icon(SPRITE_MEDKIT, x, y)
    if SPAWN_CELL:
        blit_icon(HUD_PISTOL, SPAWN_CELL[0], SPAWN_CELL[1])
    # grid
    for y in range(MAP_H+1):
        ypix = origin_y + y*cell_px
        pygame.draw.line(screen, GRID_COLOR, (origin_x, ypix), (origin_x+gw, ypix), 1)
    for x in range(MAP_W+1):
        xpix = origin_x + x*cell_px
        pygame.draw.line(screen, GRID_COLOR, (xpix, origin_y), (xpix, origin_y+gh), 1)
    pygame.draw.rect(screen, GRID_BOLD, (origin_x, origin_y, gw, gh), 2)
    # cursor
    mx, my = pygame.mouse.get_pos()
    cx = clamp((mx - origin_x)//cell_px, 0, MAP_W-1)
    cy = clamp((my - origin_y)//cell_px, 0, MAP_H-1)
    r = pygame.Rect(origin_x + cx*cell_px, origin_y + cy*cell_px, cell_px, cell_px)
    pygame.draw.rect(screen, CURSOR_COLOR, r, 2)
    legend = f"[ESC] Menu  [P] Play  Brush 0/1/2 tiles  3=Enemy[{CURRENT_ENEMY_TYPE}] (G/S/B) 4=Ammo 5=Medkit 6=Spawn   LMB place   RMB eyedrop   Del remove   Ctrl+S/Ctrl+L save/load   N new   Ctrl +/- resize   Wheel zoom"
    txt = SMALL_FONT.render(legend, True, (230,230,235))
    screen.blit(txt, (10, SCREEN_H-24))

def editor_cell_at_mouse():
    gw, gh = MAP_W*cell_px, MAP_H*cell_px
    origin_x = (SCREEN_W - gw)//2
    origin_y = (SCREEN_H - gh)//2
    mx, my = pygame.mouse.get_pos()
    if not (origin_x <= mx < origin_x+gw and origin_y <= my < origin_y+gh):
        return None
    cx = int((mx - origin_x)//cell_px); cy = int((my - origin_y)//cell_px)
    return (cx, cy)

def editor_paint_tile(x, y):
    if (x==0 or y==0 or x==MAP_W-1 or y==MAP_H-1) and BRUSH==0:
        return
    BASE_MAP[y][x] = BRUSH
    if BASE_MAP[y][x] != 0:
        remove_entity_at(x, y)

def editor_place_entity(x, y):
    kind = {3:"enemy", 4:"ammo", 5:"medkit", 6:"spawn"}.get(BRUSH, None)
    if not kind: return
    place_entity_at(x, y, kind)

def editor_pick_under_cursor(x, y):
    ent = cell_has_entity(x, y)
    if 3 <= BRUSH <= 6:
        if ent == "enemy": return 3
        if ent == "ammo": return 4
        if ent == "medkit": return 5
        if ent == "spawn": return 6
        return BRUSH
    else:
        return BASE_MAP[y][x]

def editor_handle_event(e):
    # declare globals once at top to avoid 'used prior to global declaration' SyntaxError
    global BRUSH, BASE_MAP, MAP_W, MAP_H, cell_px, EDITOR_MODE, CURRENT_ENEMY_TYPE, WALL_HEIGHTS_FT
    if e.type == pygame.KEYDOWN:
        if e.key in (pygame.K_p, pygame.K_e):
            # enter play (from editor)
            EDITOR_MODE = False
            pygame.event.set_grab(True); pygame.mouse.set_visible(False)
            restart_run()
        elif e.key in (pygame.K_0, pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6):
            BRUSH = int(e.unicode) if e.unicode.isdigit() else BRUSH
        elif e.key == pygame.K_DELETE or e.key == pygame.K_BACKSPACE:
            c = editor_cell_at_mouse()
            if c: remove_entity_at(*c)
        elif e.key == pygame.K_s and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            save_map(BASE_MAP, MAP_SAVE_PATH); save_entities(ENT_SAVE_PATH)
        elif e.key == pygame.K_l and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            BASE_MAP[:] = load_map(MAP_SAVE_PATH); update_map_dimensions(); load_entities(ENT_SAVE_PATH)
            global WALL_HEIGHTS_FT
            WALL_HEIGHTS_FT[:] = [[(random.uniform(WALL_MIN_HEIGHT_FT, WALL_MAX_HEIGHT_FT) if t==1 else (DOOR_HEIGHT_FT if t==2 else 0.0)) for t in row] for row in BASE_MAP]
            filter_entities_within_bounds()
        elif e.key in (pygame.K_g, pygame.K_s, pygame.K_b):
            if BRUSH == 3:
                if e.key == pygame.K_g: CURRENT_ENEMY_TYPE = "grunt"
                elif e.key == pygame.K_s: CURRENT_ENEMY_TYPE = "scout"
                elif e.key == pygame.K_b: CURRENT_ENEMY_TYPE = "brute"
        elif e.key == pygame.K_n:
            BASE_MAP[:] = make_blank_map(MAP_W, MAP_H); clear_entities()
        elif (e.key in (pygame.K_EQUALS, pygame.K_KP_PLUS)) and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            new_w = clamp(MAP_W + 2, 5, 255); new_h = clamp(MAP_H + 2, 5, 255); resize_to(new_w, new_h)
        elif (e.key in (pygame.K_MINUS, pygame.K_KP_MINUS)) and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            new_w = clamp(MAP_W - 2, 5, 255); new_h = clamp(MAP_H - 2, 5, 255); resize_to(new_w, new_h)
    elif e.type == pygame.MOUSEBUTTONDOWN:
        c = editor_cell_at_mouse()
        if e.button == 1 and c:
            x,y = c
            if BRUSH in (0,1,2): editor_paint_tile(x,y)
            else: editor_place_entity(x,y)
        elif e.button == 3 and c:
            BRUSH = editor_pick_under_cursor(*c)
        elif e.button == 4:
            cell_px = clamp(cell_px + 2, EDITOR_MIN_CELL, EDITOR_MAX_CELL)
        elif e.button == 5:
            cell_px = clamp(cell_px - 2, EDITOR_MIN_CELL, EDITOR_MAX_CELL)
    elif e.type == pygame.MOUSEMOTION and pygame.mouse.get_pressed()[0]:
        c = editor_cell_at_mouse()
        if c and BRUSH in (0,1,2): editor_paint_tile(*c)

def all_enemies_down():
    return len(enemies) > 0 and all(not e.alive for e in enemies)

# Override main loop with new UI state handling
def main():
    global time_since_shot, muzzle_alpha, EDITOR_MODE, SHOW_MINIMAP_PLAY, died, win, START_MENU, PAUSED
    zbuffer = [MAX_VIEW_DIST]*SCREEN_W
    while True:
        dt = clock.tick(60)/1000.0
        time_since_shot += dt
        muzzle_alpha = max(0.0, muzzle_alpha - 6.0*dt)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            # START MENU EVENTS
            if START_MENU:
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_1:
                        START_MENU = False; EDITOR_MODE = False; PAUSED = False
                        restart_run(); pygame.event.set_grab(True); pygame.mouse.set_visible(False)
                    elif e.key == pygame.K_2:
                        START_MENU = False; EDITOR_MODE = True; PAUSED = False
                        pygame.event.set_grab(False); pygame.mouse.set_visible(True)
                    elif e.key == pygame.K_ESCAPE:
                        pygame.quit(); sys.exit()
                continue

            # EDITOR EVENTS
            if EDITOR_MODE:
                editor_handle_event(e)
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    START_MENU = True; EDITOR_MODE = False
                    pygame.event.set_grab(False); pygame.mouse.set_visible(True)
                continue

            # PLAY EVENTS
            if e.type == pygame.KEYDOWN:
                if PAUSED:
                    if e.key == pygame.K_r:  # resume
                        PAUSED = False; pygame.event.set_grab(True); pygame.mouse.set_visible(False)
                    elif e.key == pygame.K_t:  # restart
                        restart_run(); PAUSED = False
                    elif e.key == pygame.K_e:  # editor
                        EDITOR_MODE = True; PAUSED = False
                        pygame.event.set_grab(False); pygame.mouse.set_visible(True)
                    elif e.key == pygame.K_m:  # main menu
                        START_MENU = True; PAUSED = False
                        pygame.event.set_grab(False); pygame.mouse.set_visible(True)
                    elif e.key == pygame.K_ESCAPE:
                        pygame.quit(); sys.exit()
                else:
                    if e.key == pygame.K_p:
                        PAUSED = True; pygame.event.set_grab(False); pygame.mouse.set_visible(True)
                    elif e.key == pygame.K_m:
                        SHOW_MINIMAP_PLAY = not SHOW_MINIMAP_PLAY
                    elif e.key == pygame.K_e:
                        EDITOR_MODE = True; pygame.event.set_grab(False); pygame.mouse.set_visible(True)
                    elif e.key == pygame.K_r and (died or win):
                        restart_run()
                    elif e.key == pygame.K_SPACE and not died and not win:
                        hitscan_shot()
                    elif e.key == pygame.K_ESCAPE:
                        PAUSED = True; pygame.event.set_grab(False); pygame.mouse.set_visible(True)
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if not PAUSED and e.button == 1 and not died and not win:
                    hitscan_shot()

        # RENDERING
        if START_MENU:
            screen.fill((12,14,18))
            draw_start_menu()
        elif EDITOR_MODE:
            editor_draw()
            cap = f"EDITOR — Tiles: 0/1/2  Entities: 3 Enemy[{CURRENT_ENEMY_TYPE}] (G/S/B) 4 Ammo 5 Medkit 6 Spawn | LMB place  RMB eyedrop  Del remove | S/L save/load  N new  Ctrl +/- resize  Wheel zoom  P Play  ESC Menu"
            t = HUD_FONT.render(cap, True, (245, 245, 250))
            screen.blit(t, (10, 10))
        else:
            if not PAUSED:
                if not died and not win:
                    get_inputs(dt)
                    update_enemies(dt)
                    try_pickups()
                    if all_enemies_down(): win = True
                cast_and_draw(zbuffer)
                render_sprites(zbuffer)
                if SHOW_MINIMAP_PLAY: draw_minimap()
                draw_hud(SHOW_MINIMAP_PLAY)
                hint = SMALL_FONT.render("[P] Pause  [E] Editor  [M] Minimap  [LMB/Space] Shoot  [R] Restart (dead/win)", True, (220,220,230))
                screen.blit(hint, (10, 10))
            else:
                cast_and_draw(zbuffer)
                render_sprites(zbuffer)
                if SHOW_MINIMAP_PLAY: draw_minimap()
                draw_hud(SHOW_MINIMAP_PLAY)
                draw_pause_menu()

        pygame.display.flip()

if __name__ == "__main__":
    # try load existing stuff if present
    if os.path.exists(MAP_SAVE_PATH):
        BASE_MAP[:] = load_map(MAP_SAVE_PATH)
        MAP_H = len(BASE_MAP); MAP_W = len(BASE_MAP[0])
    if os.path.exists(ENT_SAVE_PATH):
        load_entities(ENT_SAVE_PATH)
    main()
