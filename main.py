import os
import random
import math
import pygame
from os import listdir
from os.path import isfile, join
try:
    from pytmx.util_pygame import load_pygame as load_tmx
    _PYTMX_AVAILABLE = True
except Exception:
    _PYTMX_AVAILABLE = False
pygame.init()

pygame.display.set_caption("Platformer")

WIDTH, HEIGHT = 1000, 800
FPS = 60
PLAYER_VEL = 5

window = pygame.display.set_mode((WIDTH, HEIGHT))


def flip(sprites):
    return [pygame.transform.flip(sprite, True, False) for sprite in sprites]


def load_sprite_sheets(dir1, dir2, width, height, direction=False):
    path = join("assets", dir1, dir2)
    images = [f for f in listdir(path) if isfile(join(path, f))]

    all_sprites = {}

    for image in images:
        sprite_sheet = pygame.image.load(join(path, image)).convert_alpha()

        sprites = []
        for i in range(sprite_sheet.get_width() // width):
            surface = pygame.Surface((width, height), pygame.SRCALPHA, 32)
            rect = pygame.Rect(i * width, 0, width, height)
            surface.blit(sprite_sheet, (0, 0), rect)
            sprites.append(pygame.transform.scale2x(surface))

        if direction:
            all_sprites[image.replace(".png", "") + "_right"] = sprites
            all_sprites[image.replace(".png", "") + "_left"] = flip(sprites)
        else:
            all_sprites[image.replace(".png", "")] = sprites

    return all_sprites


def get_block(size):
    path = join("assets", "Terrain", "Terrain.png")
    image = pygame.image.load(path).convert_alpha()
    surface = pygame.Surface((size, size), pygame.SRCALPHA, 32)
    rect = pygame.Rect(96, 0, size, size)
    surface.blit(image, (0, 0), rect)
    return surface


class Player(pygame.sprite.Sprite):
    COLOR = (255, 0, 0)
    GRAVITY = 1
    SPRITES = load_sprite_sheets("MainCharacters", "MaskDude", 32, 32, True)
    ANIMATION_DELAY = 3

    def __init__(self, x, y, width, height):
        super().__init__()
        self.rect = pygame.Rect(x, y, width, height)
        self.x_vel = 0
        self.y_vel = 0
        self.mask = None
        self.direction = "left"
        self.animation_count = 0
        self.fall_count = 0
        self.jump_count = 0
        self.hit = False
        self.hit_count = 0

    def jump(self):
        self.y_vel = -self.GRAVITY * 8
        self.animation_count = 0
        self.jump_count += 1
        if self.jump_count == 1:
            self.fall_count = 0

    def move(self, dx, dy):
        self.rect.x += dx
        self.rect.y += dy

    def make_hit(self):
        self.hit = True

    def move_left(self, vel):
        self.x_vel = -vel
        if self.direction != "left":
            self.direction = "left"
            self.animation_count = 0

    def move_right(self, vel):
        self.x_vel = vel
        if self.direction != "right":
            self.direction = "right"
            self.animation_count = 0

    def loop(self, fps):
        self.y_vel += min(1, (self.fall_count / fps) * self.GRAVITY)
        self.move(self.x_vel, self.y_vel)

        if self.hit:
            self.hit_count += 1
        if self.hit_count > fps * 2:
            self.hit = False
            self.hit_count = 0

        self.fall_count += 1
        self.update_sprite()

    def landed(self):
        self.fall_count = 0
        self.y_vel = 0
        self.jump_count = 0

    def hit_head(self):
        self.count = 0
        self.y_vel *= -1

    def update_sprite(self):
        sprite_sheet = "idle"
        if self.hit:
            sprite_sheet = "hit"
        elif self.y_vel < 0:
            if self.jump_count == 1:
                sprite_sheet = "jump"
            elif self.jump_count == 2:
                sprite_sheet = "double_jump"
        elif self.y_vel > self.GRAVITY * 2:
            sprite_sheet = "fall"
        elif self.x_vel != 0:
            sprite_sheet = "run"

        sprite_sheet_name = sprite_sheet + "_" + self.direction
        sprites = self.SPRITES[sprite_sheet_name]
        sprite_index = (self.animation_count //
                        self.ANIMATION_DELAY) % len(sprites)
        self.sprite = sprites[sprite_index]
        self.animation_count += 1
        self.update()

    def update(self):
        self.rect = self.sprite.get_rect(topleft=(self.rect.x, self.rect.y))
        self.mask = pygame.mask.from_surface(self.sprite)

    def draw(self, win, offset_x):
        win.blit(self.sprite, (self.rect.x - offset_x, self.rect.y))

    def kill_player(self):
        self.make_hit()


class Object(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, name=None):
        super().__init__()
        self.rect = pygame.Rect(x, y, width, height)
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.width = width
        self.height = height
        self.name = name

    def draw(self, win, offset_x):
        win.blit(self.image, (self.rect.x - offset_x, self.rect.y))


class Block(Object):
    def __init__(self, x, y, size):
        super().__init__(x, y, size, size)
        block = get_block(size)
        self.image.blit(block, (0, 0))
        self.mask = pygame.mask.from_surface(self.image)
        self.is_solid = True


class TileBlock(Object):
    def __init__(self, x, y, tile_surface, tile_w, tile_h):
        super().__init__(x, y, tile_w, tile_h)
        # Use tile image coming from TMX tileset directly
        self.image = pygame.Surface((tile_w, tile_h), pygame.SRCALPHA)
        self.image.blit(tile_surface, (0, 0))
        self.mask = pygame.mask.from_surface(self.image)
        self.is_solid = True


class DisappearingBlock(Object):
    ANIMATION_DURATION_MS = 50
    RESPAWN_MS_DEFAULT = 0  # 0 = do not respawn

    def __init__(self, x, y, width, height, tile_surface=None, respawn_ms=None):
        super().__init__(x, y, width, height, name="trap")
        # Base image
        self.base_image = pygame.Surface((width, height), pygame.SRCALPHA)
        if tile_surface is not None:
            self.base_image.blit(tile_surface, (0, 0))
        else:
            block = get_block(width)
            self.base_image.blit(block, (0, 0))

        self.image = self.base_image.copy()
        self.mask = pygame.mask.from_surface(self.image)

        self.is_solid = True
        self.triggered = False
        self.trigger_time_ms = None
        self.respawn_ms = respawn_ms if respawn_ms is not None else self.RESPAWN_MS_DEFAULT

    def trigger(self):
        if self.triggered:
            return
        self.triggered = True
        self.trigger_time_ms = pygame.time.get_ticks()
        # Disappear instantly: non-solid and invisible right away
        self.is_solid = False
        self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.mask = pygame.mask.from_surface(self.image)

    def loop(self):
        if not self.triggered:
            return
        now = pygame.time.get_ticks()
        elapsed = now - (self.trigger_time_ms or now)
        # Handle optional respawn
        if self.respawn_ms and elapsed >= self.respawn_ms:
            self.triggered = False
            self.image = self.base_image.copy()
            self.image.set_alpha(255)
            self.is_solid = True
            self.mask = pygame.mask.from_surface(self.image)


class AppearingBlock(Object):
    def __init__(self, x, y, width, height, tile_surface=None):
        super().__init__(x, y, width, height, name="appear")
        self.base_image = pygame.Surface((width, height), pygame.SRCALPHA)
        if tile_surface is not None:
            self.base_image.blit(tile_surface, (0, 0))
        else:
            block = get_block(width)
            self.base_image.blit(block, (0, 0))

        # Start invisible and non-solid
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.mask = pygame.mask.from_surface(self.image)
        self.is_solid = False
        self.triggered = False

    def trigger(self):
        if self.triggered:
            return
        self.triggered = True
        # Instantly become visible and solid
        self.image = self.base_image.copy()
        self.image.set_alpha(255)
        self.is_solid = True
        self.mask = pygame.mask.from_surface(self.image)

class Fire(Object):
    ANIMATION_DELAY = 3

    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height, "fire")
        self.fire = load_sprite_sheets("Traps", "Fire", width, height)
        self.image = self.fire["off"][0]
        self.mask = pygame.mask.from_surface(self.image)
        self.animation_count = 0
        self.animation_name = "off"

    def on(self):
        self.animation_name = "on"

    def off(self):
        self.animation_name = "off"

    def loop(self):
        sprites = self.fire[self.animation_name]
        sprite_index = (self.animation_count //
                        self.ANIMATION_DELAY) % len(sprites)
        self.image = sprites[sprite_index]
        self.animation_count += 1

        self.rect = self.image.get_rect(topleft=(self.rect.x, self.rect.y))
        self.mask = pygame.mask.from_surface(self.image)

        if self.animation_count // self.ANIMATION_DELAY > len(sprites):
            self.animation_count = 0


class Spike(Object):
    def __init__(self, x, y, width, height, tile_surface=None, orientation="up"):
        super().__init__(x, y, width, height, name="spike")
        if tile_surface is not None:
            self.image = pygame.Surface((width, height), pygame.SRCALPHA)
            self.image.blit(tile_surface, (0, 0))
        else:
            # Fallback to Spikes sprite from assets
            path = join("assets", "Traps", "Spikes", "Idle.png")
            img = pygame.image.load(path).convert_alpha()
            self.image = pygame.transform.smoothscale(img, (width, height))
        if str(orientation).lower() in ("down", "top"):
            self.image = pygame.transform.flip(self.image, False, True)
        self.mask = pygame.mask.from_surface(self.image)
        # Spikes are non-solid hazard by default (you can toggle if needed)
        self.is_solid = False


class HiddenSpike(Object):
    RISE_DURATION_MS = 250

    def __init__(self, x, y, width, height, tile_surface=None, orientation="up"):
        super().__init__(x, y, width, height, name="spike")
        # Base spike appearance
        if tile_surface is not None:
            self.base_image = pygame.Surface((width, height), pygame.SRCALPHA)
            self.base_image.blit(tile_surface, (0, 0))
        else:
            path = join("assets", "Traps", "Spikes", "Idle.png")
            img = pygame.image.load(path).convert_alpha()
            self.base_image = pygame.transform.smoothscale(img, (width, height))
        self.orientation = str(orientation).lower()
        if self.orientation in ("down", "top"):
            self.base_image = pygame.transform.flip(self.base_image, False, True)

        # Start hidden
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.mask = pygame.mask.from_surface(self.image)
        self.is_solid = False
        self.active_hazard = False
        self.triggered = False
        self.start_ms = 0

    def trigger(self):
        if self.triggered:
            return
        self.triggered = True
        self.start_ms = pygame.time.get_ticks()

    def loop(self):
        if not self.triggered:
            return
        now = pygame.time.get_ticks()
        t = max(0, min(1, (now - self.start_ms) / self.RISE_DURATION_MS))
        # Rebuild image as reveal from bottom or top depending on orientation
        self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        reveal_h = max(1, int(self.height * t))
        if self.orientation in ("down", "top"):
            # reveal from top to bottom
            src_rect = pygame.Rect(0, 0, self.width, reveal_h)
            self.image.blit(self.base_image, (0, 0), src_rect)
        else:
            # reveal from bottom to top
            src_rect = pygame.Rect(0, self.height - reveal_h, self.width, reveal_h)
            self.image.blit(self.base_image, (0, self.height - reveal_h), src_rect)
        self.mask = pygame.mask.from_surface(self.image)
        # Become solid and hazardous once fully up
        if t >= 1:
            self.is_solid = False  # spikes remain non-solid but hazardous
            self.active_hazard = True
def get_background(name):
    image = pygame.image.load(join("assets", "Background", name))
    _, _, width, height = image.get_rect()
    tiles = []

    for i in range(WIDTH // width + 1):
        for j in range(HEIGHT // height + 1):
            pos = (i * width, j * height)
            tiles.append(pos)

    return tiles, image


def load_tmx_level(tmx_path, block_size):
    """Load a Tiled TMX map and build game objects.

    Expectations for the map:
    - Use a tile layer named "solid" (or with property solid=true) for collidable ground.
    - Optionally place an object of type "player" (or name "player") for spawn.
    - Optionally place objects of type "fire" for hazards.
    Tile size in Tiled should match block_size for best visuals.
    """
    if not _PYTMX_AVAILABLE:
        return None, None

    if not os.path.exists(tmx_path):
        return None, None

    tmx = load_tmx(tmx_path)

    objects = []
    player_spawn = None

    # Use TMX tile size if available
    tile_w = getattr(tmx, "tilewidth", block_size)
    tile_h = getattr(tmx, "tileheight", block_size)
    effective_block = int(tile_w)

    # Collect tile layers and detect which are solid
    tile_layers = []
    solid_layers = []
    for layer in tmx.visible_layers:
        tiles_iter = getattr(layer, "tiles", None)
        if callable(tiles_iter):
            tile_layers.append(layer)
            is_solid = False
            layer_name = (getattr(layer, "name", "") or "").lower()
            if layer_name in ("solid", "ground", "platform"):
                is_solid = True
            if getattr(layer, "properties", None):
                is_solid = is_solid or bool(layer.properties.get("solid"))
            if is_solid:
                solid_layers.append(layer)

    # If no explicit solid layer was found, treat all tile layers as solid
    layers_to_use = solid_layers if len(solid_layers) > 0 else tile_layers

    for layer in layers_to_use:
        for x, y, gid_or_surface in layer.tiles():
            if not gid_or_surface:
                continue
            world_x = int(x * tile_w)
            world_y = int(y * tile_h)
            tile_img = None
            # pytmx with load_pygame may return a Surface instead of gid
            if isinstance(gid_or_surface, pygame.Surface):
                tile_img = gid_or_surface
            else:
                tile_img = tmx.get_tile_image_by_gid(gid_or_surface)

            if tile_img is not None:
                objects.append(TileBlock(world_x, world_y, tile_img, int(tile_w), int(tile_h)))
            else:
                # Fallback to generic block if no image is found
                objects.append(Block(world_x, world_y, effective_block))

    # Objects layer for spawn/hazards/traps
    for obj in getattr(tmx, "objects", []):
        obj_type = (getattr(obj, "type", "") or "").lower()
        obj_name = (getattr(obj, "name", "") or "").lower()

        if obj_type == "player" or obj_name == "player":
            # Place spawn at object's bottom-left
            px = int(obj.x)
            py = int(obj.y - obj.height)
            player_spawn = (px, py)
        elif obj_type == "fire" or obj_name == "fire":
            fx = int(obj.x)
            # Align using object height if provided, else reasonable default
            assumed_h = int(getattr(obj, "height", 32) or 32)
            fy = int(obj.y - assumed_h)
            hazard = Fire(fx, fy, 16, assumed_h)
            hazard.on()
            objects.append(hazard)
        elif ("trap" in obj_type) or ("trap" in obj_name):
            tx = int(obj.x)
            th = int(getattr(obj, "height", tile_h) or tile_h)
            tw = int(getattr(obj, "width", tile_w) or tile_w)
            # For rectangle objects (no gid), Tiled uses top-left origin → use y as-is.
            # For tile objects (with gid), origin is bottom-left → y - height.
            has_gid = bool(getattr(obj, "gid", None))
            ty = int(obj.y - th) if has_gid else int(obj.y)
            # Try to find tile image via gid if present in object
            tile_img = None
            try:
                gid = getattr(obj, "gid", None)
                if gid:
                    tile_img = tmx.get_tile_image_by_gid(gid)
            except Exception:
                tile_img = None

            # Optional respawn_ms property from Tiled
            respawn_ms = None
            props = getattr(obj, "properties", None)
            if props and "respawn_ms" in props:
                try:
                    respawn_ms = int(props.get("respawn_ms"))
                except Exception:
                    respawn_ms = None

            trap = DisappearingBlock(tx, ty, tw, th, tile_img, respawn_ms=respawn_ms)
            objects.append(trap)
        elif ("spike" in obj_type) or ("spike" in obj_name):
            sx = int(obj.x)
            sh = int(getattr(obj, "height", tile_h) or tile_h)
            sw = int(getattr(obj, "width", tile_w) or tile_w)
            has_gid_s = bool(getattr(obj, "gid", None))
            sy = int(obj.y - sh) if has_gid_s else int(obj.y)
            spike_img = None
            try:
                gid = getattr(obj, "gid", None)
                if gid:
                    spike_img = tmx.get_tile_image_by_gid(gid)
            except Exception:
                spike_img = None
            # Hidden spike if property hidden=true
            hidden = False
            props = getattr(obj, "properties", None)
            if props and str(props.get("hidden", "")).lower() in ("1", "true", "yes"):
                hidden = True
            orientation = str(props.get("orientation", "up")).lower() if props else "up"
            spike = HiddenSpike(sx, sy, sw, sh, spike_img, orientation=orientation) if hidden else Spike(sx, sy, sw, sh, spike_img, orientation=orientation)
            objects.append(spike)
        elif ("appear" in obj_type) or ("appear" in obj_name):
            ax = int(obj.x)
            ah = int(getattr(obj, "height", tile_h) or tile_h)
            aw = int(getattr(obj, "width", tile_w) or tile_w)
            has_gid_a = bool(getattr(obj, "gid", None))
            ay = int(obj.y - ah) if has_gid_a else int(obj.y)
            appear_img = None
            try:
                gid = getattr(obj, "gid", None)
                if gid:
                    appear_img = tmx.get_tile_image_by_gid(gid)
            except Exception:
                appear_img = None

            ap = AppearingBlock(ax, ay, aw, ah, appear_img)
            objects.append(ap)

    return objects, player_spawn


def draw(window, background, bg_image, player, objects, offset_x):
    for tile in background:
        window.blit(bg_image, tile)

    for obj in objects:
        obj.draw(window, offset_x)

    player.draw(window, offset_x)

    pygame.display.update()


def draw_restart_overlay(win, message="You Died - Press R to Restart"):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    win.blit(overlay, (0, 0))
    font = pygame.font.SysFont(None, 48)
    text = font.render(message, True, (255, 255, 255))
    rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    win.blit(text, rect)
    pygame.display.update()


def handle_vertical_collision(player, objects, dy):
    collided_objects = []
    for obj in objects:
        # If the object is an appearing block and still invisible (non-solid),
        # collision mask returns False; but we want it to appear on touch.
        if isinstance(obj, AppearingBlock):
            if pygame.sprite.collide_rect(player, obj):
                obj.trigger()
        if getattr(obj, "is_solid", True) and pygame.sprite.collide_mask(player, obj):
            # If it's a disappearing trap, trigger instantly and skip resolving collision
            if isinstance(obj, DisappearingBlock):
                obj.trigger()
                continue
            if dy > 0:
                player.rect.bottom = obj.rect.top
                player.landed()
            elif dy < 0:
                player.rect.top = obj.rect.bottom
                player.hit_head()

            collided_objects.append(obj)

    return collided_objects


def collide(player, objects, dx):
    player.move(dx, 0)
    player.update()
    collided_object = None
    for obj in objects:
        if pygame.sprite.collide_mask(player, obj):
            collided_object = obj
            break

    player.move(-dx, 0)
    player.update()
    return collided_object


def handle_move(player, objects):
    keys = pygame.key.get_pressed()

    player.x_vel = 0
    collide_left = collide(player, [o for o in objects if getattr(o, "is_solid", True)], -PLAYER_VEL * 2)
    collide_right = collide(player, [o for o in objects if getattr(o, "is_solid", True)], PLAYER_VEL * 2)

    # If we would collide with a trap on sides, trigger and ignore the collision immediately
    if isinstance(collide_left, DisappearingBlock):
        collide_left.trigger()
        collide_left = None
    if isinstance(collide_right, DisappearingBlock):
        collide_right.trigger()
        collide_right = None

    if keys[pygame.K_LEFT] and not collide_left:
        player.move_left(PLAYER_VEL)
    if keys[pygame.K_RIGHT] and not collide_right:
        player.move_right(PLAYER_VEL)

    vertical_collide = handle_vertical_collision(player, objects, player.y_vel)
    to_check = [collide_left, collide_right, *vertical_collide]

    for obj in to_check:
        if obj and obj.name == "fire":
            player.make_hit()
        if obj and obj.name == "spike":
            # If it's a hidden spike, trigger reveal; always damage player
            if isinstance(obj, HiddenSpike):
                obj.trigger()
            player.make_hit()
        if obj and getattr(obj, "name", None) == "trap":
            # Trigger disappearing traps when landed on
            if isinstance(obj, DisappearingBlock):
                obj.trigger()
        if obj and getattr(obj, "name", None) == "appear":
            if isinstance(obj, AppearingBlock):
                obj.trigger()

    # Hazards that are non-solid (e.g., spikes) won't be in to_check; check them directly
    for obj in objects:
        if getattr(obj, "name", None) == "spike":
            if pygame.sprite.collide_mask(player, obj) or pygame.sprite.collide_rect(player, obj):
                if isinstance(obj, HiddenSpike):
                    obj.trigger()
                player.make_hit()


def main(window):
    clock = pygame.time.Clock()
    background, bg_image = get_background("Blue.png")

    block_size = 96

    # Try loading a TMX map if available (prefer test.tmx, then level1.tmx)
    test_map = os.path.join("levels", "test.tmx")
    level1_map = os.path.join("levels", "level1.tmx")
    map_path = test_map if os.path.exists(test_map) else level1_map
    loaded_objects, player_spawn = load_tmx_level(map_path, block_size)

    if loaded_objects is not None:
        objects = loaded_objects
        spawn_x, spawn_y = player_spawn if player_spawn else (100, 100)
        player = Player(spawn_x, spawn_y, 50, 50)
    else:
        # Fallback to current hardcoded layout
        player = Player(100, 100, 50, 50)
        fire = Fire(100, HEIGHT - block_size - 64, 16, 32)
        fire.on()
        floor = [Block(i * block_size, HEIGHT - block_size, block_size)
                 for i in range(-WIDTH // block_size, (WIDTH * 2) // block_size)]
        objects = [*floor, Block(0, HEIGHT - block_size * 2, block_size),
                   Block(block_size * 3, HEIGHT - block_size * 4, block_size), fire]

    offset_x = 0
    scroll_area_width = 200

    dead = False
    dead_at_ms = 0
    death_delay_ms = 0
    death_cause = None
    run = True
    while run:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
                break

            if event.type == pygame.KEYDOWN:
                if dead and event.key == pygame.K_r:
                    # Reload level
                    return main(window)
                if (not dead) and event.key == pygame.K_SPACE and player.jump_count < 2:
                    player.jump()

        if not dead:
            player.loop(FPS)
            # Update per-object behavior (Fire, DisappearingBlock, etc.)
            for obj in objects:
                if hasattr(obj, "loop"):
                    if obj is player:
                        continue
                    obj.loop()
            handle_move(player, objects)

            # Death conditions
            fell_off = player.rect.top > HEIGHT + 50
            # Detect spike contact explicitly to set delay
            spike_contact = False
            fire_contact = False
            for obj in objects:
                if getattr(obj, "name", None) == "spike":
                    if pygame.sprite.collide_mask(player, obj) or pygame.sprite.collide_rect(player, obj):
                        spike_contact = True
                        break
            if not spike_contact:
                for obj in objects:
                    if getattr(obj, "name", None) == "fire":
                        if pygame.sprite.collide_mask(player, obj):
                            fire_contact = True
                            break

            hazard_hit = player.hit  # maintained from collision handlers
            if fell_off or hazard_hit:
                dead = True
                death_cause = "spike" if spike_contact else ("fire" if fire_contact else ("fall" if fell_off else "hazard"))
                dead_at_ms = pygame.time.get_ticks()
                death_delay_ms = 1001 if death_cause == "spike" else 0

            draw(window, background, bg_image, player, objects, offset_x)
            if dead:
                if pygame.time.get_ticks() - dead_at_ms >= death_delay_ms:
                    draw_restart_overlay(window)
        else:
            # Dead state
            elapsed_since_death = pygame.time.get_ticks() - dead_at_ms
            if death_cause == "spike" and elapsed_since_death < death_delay_ms:
                # Let hazards (e.g., hidden spikes) finish their reveal animation
                for obj in objects:
                    if hasattr(obj, "loop") and obj is not player:
                        obj.loop()
                # Keep player frozen but show hit pose
                player.x_vel = 0
                player.y_vel = 0
                player.make_hit()
                player.update_sprite()
                # Redraw scene without overlay yet
                draw(window, background, bg_image, player, objects, offset_x)
            else:
                # Show restart overlay and wait for R
                draw(window, background, bg_image, player, objects, offset_x)
                draw_restart_overlay(window)

        if ((player.rect.right - offset_x >= WIDTH - scroll_area_width) and player.x_vel > 0) or (
                (player.rect.left - offset_x <= scroll_area_width) and player.x_vel < 0):
            offset_x += player.x_vel

    pygame.quit()
    quit()


if __name__ == "__main__":
    main(window)
