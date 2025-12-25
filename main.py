# web_main.py
# Minimal pygbag-compatible runner that reuses data/field.py without editing it.

from __future__ import annotations

import os
import sys
import asyncio
from typing import Tuple, Optional

import pygame
from data import field

# ---- Minimal config (kept small on purpose) ----
WINDOW_W, WINDOW_H = 540, 820
GRID_W, GRID_H = 28, 32
TILE = 24  # pixels per tile
BOARD_W, BOARD_H = GRID_W * TILE, GRID_H * TILE
BOARD_X = (WINDOW_W - BOARD_W) // 2
BOARD_Y = 10
FPS = 60

ABS_TO_PX = TILE / 4.0  # engine uses tile*4 coordinates

KEY_TO_DIR = {
    pygame.K_LEFT: "Left",
    pygame.K_a: "Left",
    pygame.K_RIGHT: "Right",
    pygame.K_d: "Right",
    pygame.K_UP: "Up",
    pygame.K_w: "Up",
    pygame.K_DOWN: "Down",
    pygame.K_s: "Down",
}

def is_web() -> bool:
    return sys.platform == "emscripten"

def load_image(path: str) -> pygame.Surface:
    return pygame.image.load(path).convert_alpha()

def scale_to_fit(img: pygame.Surface, max_px: int) -> pygame.Surface:
    w, h = img.get_size()
    if w <= 0 or h <= 0:
        return img
    s = min(max_px / w, max_px / h)
    nw, nh = max(1, int(w * s)), max(1, int(h * s))
    return pygame.transform.smoothscale(img, (nw, nh))

def center_blit(dst: pygame.Surface, img: pygame.Surface, cx: int, cy: int) -> None:
    r = img.get_rect(center=(cx, cy))
    dst.blit(img, r)

# On-screen D-pad for mobile (minimal rectangles)
class DPad:
    def __init__(self) -> None:
        size = 54
        pad = 12
        base_y = WINDOW_H - (size * 3 + pad * 2)-30
        base_x = (WINDOW_W - (size * 3)) // 2
        self.up = pygame.Rect(base_x + size, base_y, size, size)
        self.left = pygame.Rect(base_x, base_y + size, size, size)
        self.right = pygame.Rect(base_x + size * 2, base_y + size, size, size)
        self.down = pygame.Rect(base_x + size, base_y + size * 2, size, size)

    def dir_for_pos(self, pos: Tuple[int, int]) -> Optional[str]:
        x, y = pos
        if self.up.collidepoint(x, y): return "Up"
        if self.down.collidepoint(x, y): return "Down"
        if self.left.collidepoint(x, y): return "Left"
        if self.right.collidepoint(x, y): return "Right"
        return None

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        for r, label in [(self.up,"U"), (self.down,"D"), (self.left,"L"), (self.right,"R")]:
            pygame.draw.rect(screen, (255, 255, 255), r, 2)
            txt = font.render(label, True, (255, 255, 255))
            center_blit(screen, txt, r.centerx, r.centery)

class Game:
    def draw_title(self) -> None:
        self.screen.fill((0, 0, 0))

    # Title text
        title = self.title_font.render("Fitz-Man", True, (255, 255, 255))
        center_blit(self.screen, title, WINDOW_W // 2, int(WINDOW_H * 0.14))

        # Big image (dog head)
        if self.img_title is not None:
            # Scale to a consistent visual height, like your screenshot
            target_h = int(WINDOW_H * 0.38)
            w, h = self.img_title.get_size()
            scale = target_h / max(1, h)
            new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
            big = pygame.transform.smoothscale(self.img_title, new_size)
            center_blit(self.screen, big, WINDOW_W // 2, int(WINDOW_H * 0.40))
        else:
            # Fallback: use Fitz-Man sprite if no title image exists
            big = pygame.transform.smoothscale(self.img_pac, (self.img_pac.get_width() * 5, self.img_pac.get_height() * 5))
            center_blit(self.screen, big, WINDOW_W // 2, int(WINDOW_H * 0.40))

        # Start button: white fill, dark text (like screenshot)
        pygame.draw.rect(self.screen, (255, 255, 255), self.start_btn, border_radius=2)
        pygame.draw.rect(self.screen, (220, 220, 220), self.start_btn, width=2, border_radius=2)

        start_txt = pygame.font.Font(None, 28).render("Start", True, (0, 0, 0))
        center_blit(self.screen, start_txt, self.start_btn.centerx, self.start_btn.centery)

        # Hint text
        hint = self.hint_font.render("Arrow keys to move. Esc quits.", True, (140, 140, 140))
        center_blit(self.screen, hint, WINDOW_W // 2, int(WINDOW_H * 0.88))

    def __init__(self) -> None:
        pygame.init()
        try:
            pygame.mixer.init()
        except Exception:
            pass

        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("Fitz-Man (Web)")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 28)
        self.small = pygame.font.Font(None, 22)
        self.dpad = DPad()

        self.score = 0
        self.lives = 2
        self.level = 1
        self.game_over = False

        # Engine
        self.engine = field.GameEngine()
        self.engine.levelGenerate(self.level)
        self.engine.movingObjectPacman.isActive = True
        self.engine_hz = 10        
        self.engine_dt = 1.0 / self.engine_hz
        self.engine_accum = 0.0

        # Sprites (reuse your existing resource folder)
        res = "resource"
        self.img_wall = scale_to_fit(load_image(os.path.join(res, "sprite_wall.png")), TILE)
        self.img_cage = scale_to_fit(load_image(os.path.join(res, "sprite_cage.png")), TILE)
        self.img_pellet = scale_to_fit(load_image(os.path.join(res, "sprite_pellet.png")), TILE // 2)
        self.img_pac = scale_to_fit(load_image(os.path.join(res, "sprite_fitzman.png")), TILE - 2)

                # Title image (transparent PNG cutout like desktop)
        title_path = os.path.join(res, "sprite_fitzman.png")
        self.img_title = None
        if os.path.exists(title_path):
            self.img_title = load_image(title_path)

        # Title screen UI
        self.state = "TITLE"
        bw, bh = 180, 56
        self.start_btn = pygame.Rect((WINDOW_W - bw)//2, int(WINDOW_H * 0.64), bw, bh)

        # Fonts (match the “simple bold” vibe)
        self.title_font = pygame.font.Font(None, 64)
        self.hint_font = pygame.font.Font(None, 22)


        # Ghost frames optional: use what exists; if missing, ghosts just won't draw
        self.ghost = {}
        for i in range(1, 5):
            for d, name in [("Left","left"), ("Right","right"), ("Up","up"), ("Down","down")]:
                for f in (1, 2):
                    p = os.path.join(res, f"sprite_ghost_{i}_{name}{f}.png")
                    if os.path.exists(p):
                        self.ghost[(i, d, f)] = scale_to_fit(load_image(p), TILE - 2)

        self._anim_t = 0.0

    def px_from_abs(self, ax: float, ay: float) -> Tuple[int, int]:
        px = int(BOARD_X + ax * ABS_TO_PX + TILE / 2)
        py = int(BOARD_Y + ay * ABS_TO_PX + TILE / 2)
        return px, py

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            raise SystemExit
        
                # GAME OVER: restart on Enter/Space or tap
        if self.game_over:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.reset_game()
                self.state = "TITLE"  # or "PLAY" if you want instant restart
                return

            if e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                if hasattr(e, "pos"):
                    self.reset_game()
                    self.state = "TITLE"
                    return

            if e.type == pygame.FINGERDOWN:
                self.reset_game()
                self.state = "TITLE"
                return

            return  # swallow other inputs while game over


        if self.state == "TITLE":
            # Keyboard start
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.state = "PLAY"
                return

            # Mouse/touch start (desktop + many mobile browsers)
            if e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                if hasattr(e, "pos") and self.start_btn.collidepoint(e.pos):
                    self.state = "PLAY"
                    return

            # Finger start (pygbag/mobile often uses this)
            if e.type == pygame.FINGERDOWN:
                # e.x, e.y are normalized 0..1
                mx = int(e.x * WINDOW_W)
                my = int(e.y * WINDOW_H)
                if self.start_btn.collidepoint((mx, my)):
                    self.state = "PLAY"
                    return

            return  # swallow inputs on title screen


        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                raise SystemExit
            if e.key in KEY_TO_DIR:
                self.engine.movingObjectPacman.dirNext = KEY_TO_DIR[e.key]

        # Mobile touch often appears as mouse in pygbag
        if e.type == pygame.MOUSEBUTTONDOWN:
            d = self.dpad.dir_for_pos(e.pos)
            if d:
                self.engine.movingObjectPacman.dirNext = d

    def _wrap_dist_x(self, a: int, b: int, period: int) -> int:
        a %= period
        b %= period
        d = abs(a - b)
        return min(d, period - d)
    
    def _dist_y(self, a: int, b: int) -> int:
        return abs(a - b)

    def _check_ghost_collision(
        self,
        pac_prev_abs: tuple[int, int],
        ghosts_prev_abs: list[tuple[int, int]],
    ) -> bool:
        """
        Robust collision detection using engine absolute coordinates.
        This fixes 'head-on pass-through' that tile checks miss.
        """
        # Engine abs grid periods (28 tiles * 4, 32 tiles * 4)
        W_ABS = GRID_W * 4
        H_ABS = GRID_H * 4

        px, py = self.engine.movingObjectPacman.coordinateAbs
        px_prev, py_prev = pac_prev_abs

        for i, g in enumerate(self.engine.movingObjectGhosts):
            if not g.isActive or g.isCaged:
                continue

            gx, gy = g.coordinateAbs
            gx_prev, gy_prev = ghosts_prev_abs[i]

            # 1) Overlap check (match field.py "benign determine" but more reliable)
            # field.py uses (m-3 < x < m+3) so distance < 3 (strict).
            # We'll make it a hair more forgiving to prevent edge-case misses.
            dx = self._wrap_dist_x(px, gx, W_ABS)
            dy = self._dist_y(py, gy)

            if dx <= 3 and dy <= 3:
                return self._lose_life()

            # 2) Head-on cross check (both moved toward each other in the same tick)
            # This catches rare cases where they leapfrog near the boundary of the threshold.
            dx_prev = self._wrap_dist(px_prev, gx_prev, W_ABS)
            dy_prev = self._wrap_dist(py_prev, gy_prev, H_ABS)
            dx_now = dx
            dy_now = dy

            # If they were separated and then separated again but "passed through" in between,
            # this helps catch it. Keep it simple: check if relative ordering flipped on x or y
            # while staying roughly aligned on the other axis.
            if dy <= 3 and dy_prev <= 3:
                # x-order flip (with wrap-safe deltas approximated by mod space)
                # We compare signed deltas in mod space:
                def signed_delta(a: int, b: int, period: int) -> int:
                    a %= period; b %= period
                    d = (a - b) % period
                    if d > period // 2:
                        d -= period
                    return d

                s_prev = signed_delta(px_prev, gx_prev, W_ABS)
                s_now = signed_delta(px, gx, W_ABS)
                if s_prev == 0 or s_now == 0 or (s_prev > 0) != (s_now > 0):
                    return self._lose_life()

            if dx <= 3 and dx_prev <= 3:
                def signed_delta(a: int, b: int, period: int) -> int:
                    a %= period; b %= period
                    d = (a - b) % period
                    if d > period // 2:
                        d -= period
                    return d

                s_prev = signed_delta(py_prev, gy_prev, H_ABS)
                s_now = signed_delta(py, gy, H_ABS)
                if s_prev == 0 or s_now == 0 or (s_prev > 0) != (s_now > 0):
                    return self._lose_life()

        return False


    def _lose_life(self) -> bool:
        self.lives -= 1
        if self.lives < 0:
            self.game_over = True
        else:
            self.engine = field.GameEngine()
            self.engine.levelGenerate(self.level)
            self.engine.movingObjectPacman.isActive = True
            self.engine_accum = 0.0
        return True


    def update(self, dt: float) -> None:
        if self.game_over or self.state != "PLAY":
            return
    
        self._anim_t += dt
    
        # Accumulate real time, step the engine at a fixed rate
        self.engine_accum += dt
        steps = 0
        max_steps = 5  # 3 is a bit tight on slow frames
    
        while self.engine_accum >= self.engine_dt and steps < max_steps:
            pac_prev = tuple(self.engine.movingObjectPacman.coordinateAbs)
            ghosts_prev = [tuple(g.coordinateAbs) for g in self.engine.movingObjectGhosts]
    
            self.engine.loopFunction()
    
            # collisions every tick (not every frame)
            if self._check_ghost_collision(pac_prev, ghosts_prev):
                return
    
            # eat pellets only on-grid to avoid weird early eats
            ax, ay = self.engine.movingObjectPacman.coordinateAbs
            if ax % 4 == 0 and ay % 4 == 0:
                rx, ry = self.engine.movingObjectPacman.coordinateRel
                if 0 <= rx < GRID_W and 0 <= ry < GRID_H:
                    obj = self.engine.levelObjects[rx][ry]
                    if obj.name == "pellet" and not obj.isDestroyed:
                        obj.isDestroyed = True
                        obj.name = "empty"
                        self.engine.levelPelletRemaining -= 1
                        self.score += 10
    
            # level clear
            if self.engine.levelPelletRemaining <= 0:

    def _advance_level(self) -> None:
        self.level += 1
        next_path = os.path.join("resource", f"level{self.level}.txt")
        if not os.path.exists(next_path):
            self.level = 1
        self.engine = field.GameEngine()
        self.engine.levelPelletRemaining = 0
        self.engine.levelGenerate(self.level)
        self.engine.movingObjectPacman.isActive = True
        self.engine_accum = 0.0


    def reset_game(self) -> None:
        self.score = 0
        self.lives = 2
        self.level = 1
        self.game_over = False

        self.engine = field.GameEngine()
        self.engine.levelGenerate(self.level)
        self.engine.movingObjectPacman.isActive = True

        # reset tick accumulator if you're using fixed-step speed control
        if hasattr(self, "engine_accum"):
            self.engine_accum = 0.0


    def draw(self) -> None:
        if self.state == "TITLE":
            self.draw_title()
            pygame.display.flip()
            return

        self.screen.fill((0, 0, 0))

        hud = self.font.render(f"Score: {self.score}   Lives: {max(self.lives,0)}   Level: {self.level}", True, (255,255,255))
        self.screen.blit(hud, (16, 18))

        # board tiles
        for x in range(GRID_W):
            for y in range(GRID_H):
                obj = self.engine.levelObjects[x][y]
                cx = BOARD_X + x * TILE + TILE // 2
                cy = BOARD_Y + y * TILE + TILE // 2
                if obj.name == "wall":
                    center_blit(self.screen, self.img_wall, cx, cy)
                elif obj.name == "cage":
                    center_blit(self.screen, self.img_cage, cx, cy)
                elif obj.name == "pellet" and not obj.isDestroyed:
                    center_blit(self.screen, self.img_pellet, cx, cy)

       # pygame.draw.rect(self.screen, (120,120,120), (BOARD_X, BOARD_Y, BOARD_W, BOARD_H), 1)

        # pacman
        pax, pay = self.px_from_abs(*self.engine.movingObjectPacman.coordinateAbs)
        center_blit(self.screen, self.img_pac, pax, pay)

        # ghosts
        frame = 1 if int(self._anim_t * 6) % 2 == 0 else 2
        for i, g in enumerate(self.engine.movingObjectGhosts, start=1):
            if not g.isActive:
                continue
            img = self.ghost.get((i, g.dirCurrent, frame))
            if not img:
                continue
            gx, gy = self.px_from_abs(*g.coordinateAbs)
            center_blit(self.screen, img, gx, gy)

        self.dpad.draw(self.screen, self.small)

        if self.game_over:
            over = self.font.render("GAME OVER", True, (255, 80, 80))
            center_blit(self.screen, over, WINDOW_W // 2, WINDOW_H // 2)

            msg = self.small.render("Press Enter or tap to restart", True, (200, 200, 200))
            center_blit(self.screen, msg, WINDOW_W // 2, WINDOW_H // 2 + 34)

        pygame.display.flip()

async def main() -> None:
    g = Game()
    running = True
    while running:
        dt = g.clock.tick(FPS) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
                break
            try:
                g.handle_event(e)
            except SystemExit:
                running = False
                break

        g.update(dt)
        g.draw()

        if is_web():
            await asyncio.sleep(0)

    pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())




