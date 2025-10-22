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
        # Last checkpoint respawn position
        self.respawn_pos = (x, y)

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

    def respawn(self):
        # Restore position and clear transient states
        self.rect.topleft = self.respawn_pos
        self.x_vel = 0
        self.y_vel = 0
        self.hit = False
        self.hit_count = 0
        self.fall_count = 0
        self.jump_count = 0
        self.animation_count = 0


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

    def reset(self):
        # Back to initial: visible and solid
        self.triggered = False
        self.trigger_time_ms = None
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

    def reset(self):
        # Back to initial: invisible and non-solid
        self.triggered = False
        self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.mask = pygame.mask.from_surface(self.image)
        self.is_solid = False

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

    def reset(self):
        # Back to hidden, non-solid, non-hazard
        self.triggered = False
        self.active_hazard = False
        self.start_ms = 0
        self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.mask = pygame.mask.from_surface(self.image)
        self.is_solid = False
        

class Checkpoint(Object):
    ANIMATION_DELAY = 4

    def __init__(self, x, y, width=64, height=64):
        super().__init__(x, y, width, height, name="checkpoint")
        self.is_solid = False
        # Load images
        base_dir = join("assets", "Items", "Checkpoints", "Checkpoint")
        # No flag static
        no_flag_img = pygame.image.load(join(base_dir, "Checkpoint (No Flag).png")).convert_alpha()
        self.no_flag = pygame.transform.smoothscale(no_flag_img, (width, height))
        # Flag out sheet (animation)
        flag_out_sheet = pygame.image.load(join(base_dir, "Checkpoint (Flag Out) (64x64).png")).convert_alpha()
        self.flag_out_frames = self._slice_and_scale(flag_out_sheet, 64, 64, width, height)
        # Flag idle sheet (loop animation)
        flag_idle_sheet = pygame.image.load(join(base_dir, "Checkpoint (Flag Idle)(64x64).png")).convert_alpha()
        self.flag_idle_frames = self._slice_and_scale(flag_idle_sheet, 64, 64, width, height)

        self.state = "no_flag"  # no_flag -> flag_out -> idle
        self.animation_count = 0
        self.image = self.no_flag
        self.mask = pygame.mask.from_surface(self.image)
        self.activated = False

    def _slice_and_scale(self, sheet, frame_w, frame_h, out_w, out_h):
        frames = []
        num = max(1, sheet.get_width() // frame_w)
        for i in range(num):
            surface = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            rect = pygame.Rect(i * frame_w, 0, frame_w, frame_h)
            surface.blit(sheet, (0, 0), rect)
            frames.append(pygame.transform.smoothscale(surface, (out_w, out_h)))
        return frames

    def trigger(self):
        if self.activated:
            return
        self.activated = True
        self.state = "flag_out"
        self.animation_count = 0

    def loop(self):
        if self.state == "no_flag":
            # idle without flag
            self.image = self.no_flag
        elif self.state == "flag_out":
            sprites = self.flag_out_frames
            sprite_index = (self.animation_count // self.ANIMATION_DELAY)
            if sprite_index >= len(sprites):
                # transition to idle flag loop
                self.state = "idle"
                self.animation_count = 0
                self.image = self.flag_idle_frames[0]
            else:
                self.image = sprites[sprite_index]
                self.animation_count += 1
        elif self.state == "idle":
            sprites = self.flag_idle_frames
            sprite_index = (self.animation_count // self.ANIMATION_DELAY) % len(sprites)
            self.image = sprites[sprite_index]
            self.animation_count += 1

        # Update collision mask each frame in case of change
        self.mask = pygame.mask.from_surface(self.image)

    def reset(self):
        # Back to initial: no flag and not activated
        self.state = "no_flag"
        self.animation_count = 0
        self.image = self.no_flag
        self.mask = pygame.mask.from_surface(self.image)
        self.activated = False


class End(Object):
    def __init__(self, x, y, width=64, height=64):
        super().__init__(x, y, width, height, name="end")
        self.is_solid = False
        base_dir = join("assets", "Items", "Checkpoints", "End")
        idle_img = pygame.image.load(join(base_dir, "End (Idle).png")).convert_alpha()
        pressed_img = pygame.image.load(join(base_dir, "End (Pressed) (64x64).png")).convert_alpha()
        self.idle = pygame.transform.smoothscale(idle_img, (width, height))
        self.pressed = pygame.transform.smoothscale(pressed_img, (width, height))
        self.activated = False
        self.activated_at_ms = 0
        self.image = self.idle
        self.mask = pygame.mask.from_surface(self.image)

    def trigger(self):
        if self.activated:
            return
        self.activated = True
        self.activated_at_ms = pygame.time.get_ticks()
        self.image = self.pressed
        self.mask = pygame.mask.from_surface(self.image)

    def reset(self):
        self.activated = False
        self.activated_at_ms = 0
        self.image = self.idle
        self.mask = pygame.mask.from_surface(self.image)

    def loop(self):
        # Simple visual feedback during the first 1.5s after activation: blink idle/pressed
        if not self.activated:
            return
        elapsed = pygame.time.get_ticks() - (self.activated_at_ms or 0)
        if elapsed < 1500:
            phase = (elapsed // 200) % 2
            self.image = self.pressed if phase == 0 else self.idle
            self.mask = pygame.mask.from_surface(self.image)

class Box(Object):
    BROKEN_HIDE_DELAY_MS = 250

    def __init__(self, x, y, width, height, variant="Box2"):
        # Solid, decorative box (crate) that acts as a collidable block
        super().__init__(x, y, width, height, name="box")
        # Load the Box2 idle image and scale to requested size
        box_path = join("assets", "Items", "Boxes", str(variant), "Idle.png")
        base_img = pygame.image.load(box_path).convert_alpha()
        scaled_img = pygame.transform.smoothscale(base_img, (width, height))
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.image.blit(scaled_img, (0, 0))
        self.mask = pygame.mask.from_surface(self.image)
        self.is_solid = True
        self.variant = variant
        self.broken = False
        self.broken_at_ms = 0

    def break_box(self):
        if self.broken:
            return
        self.broken = True
        self.is_solid = False
        # Show break sprite briefly, then hide
        break_path = join("assets", "Items", "Boxes", str(self.variant), "Break.png")
        try:
            break_img = pygame.image.load(break_path).convert_alpha()
            break_scaled = pygame.transform.smoothscale(break_img, (self.width, self.height))
            self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.image.blit(break_scaled, (0, 0))
        except Exception:
            # Fallback to instantly invisible if asset missing
            self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.mask = pygame.mask.from_surface(self.image)
        self.broken_at_ms = pygame.time.get_ticks()

    def loop(self):
        if self.broken:
            if pygame.time.get_ticks() - self.broken_at_ms >= self.BROKEN_HIDE_DELAY_MS:
                # Hide after delay
                self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                self.mask = pygame.mask.from_surface(self.image)

    def reset(self):
        # Restore unbroken box
        box_path = join("assets", "Items", "Boxes", str(self.variant), "Idle.png")
        base_img = pygame.image.load(box_path).convert_alpha()
        scaled_img = pygame.transform.smoothscale(base_img, (self.width, self.height))
        self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.image.blit(scaled_img, (0, 0))
        self.mask = pygame.mask.from_surface(self.image)
        self.is_solid = True
        self.broken = False
        self.broken_at_ms = 0
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

    try:
        tmx = load_tmx(tmx_path)
    except Exception as e:
        print("TMX load failed:", e)
        return None, None

    # Diagnostics to help verify map type and loading behavior
    try:
        is_infinite = bool(getattr(tmx, "infinite", False))
        map_w = getattr(tmx, "width", None)
        map_h = getattr(tmx, "height", None)
        tile_w_dbg = getattr(tmx, "tilewidth", None)
        tile_h_dbg = getattr(tmx, "tileheight", None)
        print(f"Loaded TMX: {tmx_path} | infinite={is_infinite} | size={map_w}x{map_h} | tile={tile_w_dbg}x{tile_h_dbg}")
    except Exception:
        pass

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
        elif (obj_type == "checkpoint") or (obj_name == "checkpoint"):
            cx = int(obj.x)
            ch = int(getattr(obj, "height", 64) or 64)
            cw = int(getattr(obj, "width", 64) or 64)
            has_gid_c = bool(getattr(obj, "gid", None))
            cy = int(obj.y - ch) if has_gid_c else int(obj.y)
            checkpoint = Checkpoint(cx, cy, cw, ch)
            objects.append(checkpoint)
        elif (obj_type == "box2") or (obj_name == "box2"):
            bx = int(obj.x)
            bh = int(getattr(obj, "height", tile_h) or tile_h)
            bw = int(getattr(obj, "width", tile_w) or tile_w)
            has_gid_b = bool(getattr(obj, "gid", None))
            by = int(obj.y - bh) if has_gid_b else int(obj.y)
            # Always use Box2 asset regardless of gid
            box = Box(bx, by, bw, bh, variant="Box2")
            objects.append(box)
        elif (obj_type == "end") or (obj_name == "end"):
            ex = int(obj.x)
            eh = int(getattr(obj, "height", 64) or 64)
            ew = int(getattr(obj, "width", 64) or 64)
            has_gid_e = bool(getattr(obj, "gid", None))
            ey = int(obj.y - eh) if has_gid_e else int(obj.y)
            end_obj = End(ex, ey, ew, eh)
            objects.append(end_obj)

    return objects, player_spawn


def draw(window, background, bg_image, player, objects, offset_x, update_display=True, death_count=None):
    for tile in background:
        window.blit(bg_image, tile)

    for obj in objects:
        obj.draw(window, offset_x)

    player.draw(window, offset_x)

    # HUD: Death counter (top-left)
    if death_count is not None:
        hud_font = pygame.font.SysFont(None, 28)
        hud_text = hud_font.render(f"Deaths: {death_count}", True, (255, 255, 255))
        window.blit(hud_text, (12, 10))

    if update_display:
        pygame.display.update()


def draw_restart_overlay(win, message="You Died - Press R to Restart"):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    win.blit(overlay, (0, 0))
    font = pygame.font.SysFont(None, 48)
    text = font.render(message, True, (255, 255, 255))
    rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    win.blit(text, rect)
def draw_level_complete_overlay(win, elapsed_ms, death_count):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    win.blit(overlay, (0, 0))
    title_font = pygame.font.SysFont(None, 56)
    info_font = pygame.font.SysFont(None, 36)
    title = title_font.render("Level Complete!", True, (255, 255, 0))
    sec = max(0.0, elapsed_ms / 1000.0)
    info1 = info_font.render(f"Time: {sec:.2f}s", True, (255, 255, 255))
    info2 = info_font.render(f"Deaths: {death_count}", True, (255, 255, 255))
    info3 = info_font.render("N: Next Level   R: Restart", True, (200, 200, 200))
    cx, cy = WIDTH // 2, HEIGHT // 2
    win.blit(title, title.get_rect(center=(cx, cy - 60)))
    win.blit(info1, info1.get_rect(center=(cx, cy - 10)))
    win.blit(info2, info2.get_rect(center=(cx, cy + 30)))
    win.blit(info3, info3.get_rect(center=(cx, cy + 80)))
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
                # If we landed on a Box, break it and let player fall on next frame
                if isinstance(obj, Box):
                    obj.break_box()
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
        if obj and getattr(obj, "name", None) == "checkpoint":
            if isinstance(obj, Checkpoint):
                obj.trigger()
                # Update player respawn to the center-top of checkpoint
                player.respawn_pos = (obj.rect.x, obj.rect.y)
        if obj and getattr(obj, "name", None) == "trap":
            # Trigger disappearing traps when landed on
            if isinstance(obj, DisappearingBlock):
                obj.trigger()
        if obj and getattr(obj, "name", None) == "appear":
            if isinstance(obj, AppearingBlock):
                obj.trigger()
        if obj and getattr(obj, "name", None) == "end":
            if isinstance(obj, End):
                obj.trigger()

    # Hazards that are non-solid (e.g., spikes) won't be in to_check; check them directly
    for obj in objects:
        if getattr(obj, "name", None) == "spike":
            if pygame.sprite.collide_mask(player, obj) or pygame.sprite.collide_rect(player, obj):
                if isinstance(obj, HiddenSpike):
                    obj.trigger()
                player.make_hit()
        if getattr(obj, "name", None) == "checkpoint":
            # Checkpoints are non-solid, so they won't be in vertical/side collision lists
            if pygame.sprite.collide_mask(player, obj) or pygame.sprite.collide_rect(player, obj):
                try:
                    obj.trigger()
                    player.respawn_pos = (obj.rect.x, obj.rect.y)
                except Exception:
                    pass
        if getattr(obj, "name", None) == "end":
            if pygame.sprite.collide_mask(player, obj) or pygame.sprite.collide_rect(player, obj):
                try:
                    obj.trigger()
                except Exception:
                    pass


def _find_next_level(current_map):
    # Try LevelN.tmx in the same directory, increment N
    try:
        base = os.path.basename(current_map)
        dirn = os.path.dirname(current_map) or "."
        name, ext = os.path.splitext(base)
        # Accept names like Level1, Level01, level2, etc.
        import re
        m = re.search(r"(\d+)$", name)
        if not m:
            return None
        n = int(m.group(1))
        prefix = name[:m.start(1)]
        width = len(m.group(1))
        next_name = f"{prefix}{n+1:0{width}d}{ext}"
        candidate = os.path.join(dirn, next_name)
        return candidate if os.path.exists(candidate) else None
    except Exception:
        return None


def main(window, map_path_override=None, death_count_seed=0):
    clock = pygame.time.Clock()
    background, bg_image = get_background("Blue.png")

    block_size = 96

    # Try loading a TMX map if available. Prefer map/Level1.tmx unless override is given.
    if map_path_override and os.path.exists(map_path_override):
        map_path = map_path_override
    else:
        preferred_map = os.path.join("map", "Level1.tmx")
        if os.path.exists(preferred_map):
            map_path = preferred_map
        else:
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
    death_count = int(death_count_seed or 0)
    level_started_ms = pygame.time.get_ticks()
    level_complete = False
    level_completed_at_ms = 0
    elapsed_at_complete_ms = 0
    complete_overlay_delay_ms = 1500
    run = True
    while run:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
                break

            if event.type == pygame.KEYDOWN:
                if dead and event.key == pygame.K_r:
                    # Respawn at last checkpoint rather than reload level
                    dead = False
                    player.respawn()
                    # Reset dynamic objects to initial state
                    for obj in objects:
                        reset_fn = getattr(obj, "reset", None)
                        if callable(reset_fn):
                            reset_fn()
                    # Recenter camera on player after respawn
                    offset_x = max(0, player.rect.centerx - WIDTH // 2)
                    # Clear any death timers
                    dead_at_ms = 0
                    death_delay_ms = 0
                    death_cause = None
                    continue
                if level_complete:
                    if event.key == pygame.K_r:
                        # Restart same level with same death_count
                        return main(window, map_path_override=map_path, death_count_seed=death_count)
                    if event.key == pygame.K_n:
                        next_map = _find_next_level(map_path)
                        if next_map and os.path.exists(next_map):
                            return main(window, map_path_override=next_map, death_count_seed=death_count)
                        else:
                            # If no next level, restart current
                            return main(window, map_path_override=map_path, death_count_seed=death_count)
                if (not dead) and event.key == pygame.K_SPACE and player.jump_count < 2:
                    player.jump()

        if not dead and (not level_complete or (pygame.time.get_ticks() - level_completed_at_ms < complete_overlay_delay_ms)):
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
                death_count += 1
                death_cause = "spike" if spike_contact else ("fire" if fire_contact else ("fall" if fell_off else "hazard"))
                dead_at_ms = pygame.time.get_ticks()
                death_delay_ms = 1001 if death_cause == "spike" else 0
            # Check end condition
            if not level_complete:
                for obj in objects:
                    if getattr(obj, "name", None) == "end" and isinstance(obj, End) and obj.activated:
                        level_complete = True
                        level_completed_at_ms = pygame.time.get_ticks()
                        elapsed_at_complete_ms = level_completed_at_ms - level_started_ms
                        break

            draw(window, background, bg_image, player, objects, offset_x, death_count=death_count)
        else:
            if dead:
                # Dead state - handle spike death delay
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
                    draw(window, background, bg_image, player, objects, offset_x, death_count=death_count)
                else:
                    # Show restart overlay and wait for R
                    draw(window, background, bg_image, player, objects, offset_x, update_display=False, death_count=death_count)
                    draw_restart_overlay(window)
                    pygame.display.update()
            elif level_complete:
                # Before overlay: allow normal update including player movement
                if pygame.time.get_ticks() - level_completed_at_ms < complete_overlay_delay_ms:
                    # Already updated above in the main branch; just draw
                    pass
                else:
                    # After delay: lock player and show overlay
                    player.x_vel = 0
                    player.y_vel = 0
                draw(window, background, bg_image, player, objects, offset_x, update_display=False, death_count=death_count)
                now = pygame.time.get_ticks()
                if now - level_completed_at_ms >= complete_overlay_delay_ms:
                    draw_level_complete_overlay(window, elapsed_at_complete_ms, death_count)
                else:
                    pygame.display.update()

        if ((player.rect.right - offset_x >= WIDTH - scroll_area_width) and player.x_vel > 0) or (
                (player.rect.left - offset_x <= scroll_area_width) and player.x_vel < 0):
            offset_x += player.x_vel

    pygame.quit()
    quit()


if __name__ == "__main__":
    main(window)
