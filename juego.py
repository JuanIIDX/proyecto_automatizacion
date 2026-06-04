import pygame
import sys
import threading
import serial
import serial.tools.list_ports
import math

# ─────────────────────────────────────────────
# CONFIGURACION
# ─────────────────────────────────────────────
SCREEN_W  = 1920
SCREEN_H  = 1080
PANEL_W   = 300        # ancho del panel lateral
GAME_W    = SCREEN_W - PANEL_W
GAME_H    = SCREEN_H
TILE      = 48
FPS       = 60
BAUDRATE  = 115200

GRAV      = 0.6
JUMP_V    = -13
SPD       = 4

# Proyeccion isometrica simple (angulo de perspectiva)
ISO_ANG   = math.radians(25)   # inclinacion vertical de la profundidad
ISO_SCALE = 0.45               # cuanto se "achata" la dimension de profundidad

# Colores
C_BG        = (13,  13,  26)
C_TILE      = (58,  111, 216)
C_TILE_OUT  = (34,  85,  170)
C_RAMP      = (42,  157, 143)
C_RAMP_OUT  = (26,  122, 111)
C_PLAYER    = (87,  204, 128)
C_TEXT      = (224, 224, 224)
C_TITULO    = (0,   212, 255)
C_PANEL     = (22,  33,  62)
C_NAVBAR    = (15,  52,  96)
C_OK        = (0,   255, 153)
C_ERROR     = (255, 68,  68)
C_DARK      = (8,   8,   18)

DOOR_COLORS = {
    0: (70,  130, 255),   # Azul
    1: (70,  220, 100),   # Verde
    2: (255, 70,  70),    # Rojo
    3: (255, 220, 50),    # Amarillo
}

STAT_COLORS = {
    "A": (0,   212, 255),
    "B": (255, 153, 0),
    "R": (200, 68,  255),
    "X": (255, 68,  102),
}
STAT_INDICES = {"A": 1, "B": 2, "R": 4, "X": 0}
STAT_LIMITES = {"A": (10,160), "B": (10,100), "R": (0,180), "X": (30,110)}

# ─────────────────────────────────────────────
# TILEMAP
# Leyenda:
#   ' ' = vacio        '1' = bloque
#   '2' = rampa-der    '3' = rampa-izq
#   'A','B','C','D'    = puertas (azul,verde,rojo,amarillo)
# ─────────────────────────────────────────────
MAPA_RAW = [
    "                                                  ",
    "                                                  ",
    "                                                  ",
    "                   1                              ",
    "              A        B                          ",
    "    111111111111   111111111111    111111111111    ",
    "                                                  ",
    "                                                  ",
    "         111                          111         ",
    "    C              D                              ",
    "  11111111111  11111111111      111111111111111   ",
    "                                                  ",
    "                                                  ",
    "  1111   2                   3   1111             ",
    "                                                  ",
    "111111111111111111111111111111111111111111111111111",
    "111111111111111111111111111111111111111111111111111",
]

MAP_COLS = max(len(r) for r in MAPA_RAW)
MAP_ROWS = len(MAPA_RAW)
MAP_W    = MAP_COLS * TILE
MAP_H    = MAP_ROWS * TILE

def parse_mapa(raw):
    tiles, ramps, doors = [], [], []
    door_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    for row, line in enumerate(raw):
        for col, ch in enumerate(line):
            x, y = col * TILE, row * TILE
            if ch == "1":
                tiles.append(pygame.Rect(x, y, TILE, TILE))
            elif ch == "2":
                ramps.append(("R", x, y))
            elif ch == "3":
                ramps.append(("L", x, y))
            elif ch in door_map:
                doors.append({"idx": door_map[ch], "x": x, "y": y,
                               "w": TILE, "h": TILE*3,
                               "open_h": 0.0})
    return tiles, ramps, doors

TILES, RAMPS, DOORS = parse_mapa(MAPA_RAW)

# ─────────────────────────────────────────────
# JUGADOR
# ─────────────────────────────────────────────
class Jugador:
    W, H = 28, 36

    def __init__(self):
        self.x     = float(TILE * 2)
        self.y     = float(MAP_H - TILE * 3 - self.H)
        self.vx    = 0.0
        self.vy    = 0.0
        self.suelo = False
        self.cara  = 1
        self.anim  = 0.0   # frame de animacion

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.W, self.H)

    def update(self, izq, der, salto, doors, plataformas_extra=None):
        self.vx = 0
        if izq: self.vx = -SPD; self.cara = -1
        if der: self.vx =  SPD; self.cara =  1
        if salto and self.suelo:
            self.vy = JUMP_V
            self.suelo = False

        if izq or der:
            self.anim += 0.25
        else:
            self.anim = 0

        self.vy = min(self.vy + GRAV, 18)

        extra = plataformas_extra or []
        self.x += self.vx
        self._col_x(doors, extra)
        self.y += self.vy
        self.suelo = False
        self._col_y(doors, extra)
        self._col_rampas()

        self.x = max(0, min(self.x, MAP_W - self.W))
        if self.y > MAP_H + 200:
            self.y = 0
            self.vy = 0

    def _bloques_activos(self, doors, extra=None):
        bloques = list(TILES)
        for d in doors:
            h = int(d["h"] - d["open_h"])
            if h > 2:
                bloques.append(pygame.Rect(d["x"], d["y"], d["w"], h))
        # Plataformas del brazo robot (en coordenadas mundo, el rect ya viene en pantalla
        # pero necesitamos coordenadas mundo — se pasan directamente como Rect mundo)
        if extra:
            bloques.extend(extra)
        return bloques

    def _col_x(self, doors, extra=None):
        r = self.rect()
        for b in self._bloques_activos(doors, extra):
            if r.colliderect(b):
                if self.vx > 0: self.x = b.left - self.W
                elif self.vx < 0: self.x = b.right
                self.vx = 0
                r = self.rect()

    def _col_y(self, doors, extra=None):
        r = self.rect()
        for b in self._bloques_activos(doors, extra):
            if r.colliderect(b):
                if self.vy > 0:
                    self.y = b.top - self.H
                    self.vy = 0
                    self.suelo = True
                elif self.vy < 0:
                    self.y = b.bottom
                    self.vy = 0
                r = self.rect()

    def _col_rampas(self):
        cx  = self.x + self.W / 2
        pie = self.y + self.H
        for (tipo, rx, ry) in RAMPS:
            if rx <= cx <= rx + TILE and ry <= pie <= ry + TILE + 6:
                t = (cx - rx) / TILE
                sy = ry + TILE - t * TILE if tipo == "R" else ry + t * TILE
                if pie >= sy - 2:
                    self.y = sy - self.H
                    self.vy = 0
                    self.suelo = True

    def draw(self, surf, cx, cy, font_small):
        x = int(self.x) - cx
        y = int(self.y) - cy

        # Sombra
        pygame.draw.ellipse(surf, (0, 0, 0, 80),
                            (x + 2, y + self.H - 4, self.W - 4, 8))

        # Cuerpo
        pygame.draw.rect(surf, C_PLAYER, (x, y, self.W, self.H), border_radius=5)
        pygame.draw.rect(surf, (50, 160, 80), (x, y, self.W, self.H), 2, border_radius=5)

        # Ojos
        ox = 8 if self.cara == 1 else 4
        pygame.draw.ellipse(surf, (255, 255, 255), (x+ox, y+8, 8, 8))
        pygame.draw.ellipse(surf, (0, 0, 0),       (x+ox+2+(self.cara), y+10, 4, 4))


# ─────────────────────────────────────────────
# SERIAL (hilo de fondo)
# ─────────────────────────────────────────────
class Serial:
    def __init__(self):
        self.angulos   = [0] * 6
        self.ir        = [0] * 4
        self.ser       = None
        self.corriendo = False
        self.estado    = "Sin conectar"
        self.lock      = threading.Lock()

    def listar(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def autodetectar(self):
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").lower()
            if any(k in desc for k in ("cp210", "ch340", "esp32", "uart")):
                return p.device
        puertos = self.listar()
        return puertos[0] if puertos else None

    def conectar(self, puerto):
        self.desconectar()
        try:
            self.ser = serial.Serial(puerto, BAUDRATE, timeout=1)
            self.corriendo = True
            self.estado = f"Conectado: {puerto}"
            threading.Thread(target=self._leer, daemon=True).start()
        except Exception as e:
            self.estado = f"Error: {e}"

    def desconectar(self):
        self.corriendo = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.estado = "Desconectado"

    def _leer(self):
        while self.corriendo:
            try:
                linea = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if linea.startswith("ANGULOS:"):
                    p = linea[8:].split(",")
                    if len(p) == 6:
                        with self.lock:
                            self.angulos = [int(x) for x in p]
                elif linea.startswith("IR:"):
                    p = linea[3:].split(",")
                    if len(p) == 4:
                        with self.lock:
                            self.ir = [int(x) for x in p]
            except Exception:
                if self.corriendo:
                    self.estado = "Conexion perdida"
                break


# ─────────────────────────────────────────────
# JUEGO PRINCIPAL
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# BOTON PYGAME
# ─────────────────────────────────────────────
class Boton:
    def __init__(self, x, y, w, h, texto, color, color_hover=None):
        self.rect        = pygame.Rect(x, y, w, h)
        self.texto       = texto
        self.color       = color
        self.color_hover = color_hover or tuple(min(c+30, 255) for c in color)
        self.hovered     = False

    def draw(self, surf, font):
        c = self.color_hover if self.hovered else self.color
        pygame.draw.rect(surf, c, self.rect, border_radius=5)
        pygame.draw.rect(surf, (200, 200, 220), self.rect, 1, border_radius=5)
        txt = font.render(self.texto, True, (230, 230, 230))
        surf.blit(txt, (self.rect.x + self.rect.w//2 - txt.get_width()//2,
                        self.rect.y + self.rect.h//2 - txt.get_height()//2))

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)

    def clicked(self, mouse_pos):
        return self.rect.collidepoint(mouse_pos)


# ─────────────────────────────────────────────
# BRAZO ROBOT (proyeccion isometrica falsa)
# ─────────────────────────────────────────────
def iso_offset(profundidad):
    """Convierte una distancia de 'profundidad' en desplazamiento (dx,dy) en pantalla."""
    dx = profundidad * math.cos(ISO_ANG) * ISO_SCALE
    dy = -profundidad * math.sin(ISO_ANG) * ISO_SCALE
    return dx, dy

def dibujar_cubo_iso(surf, cx, cy, w, h, d, color, cx_off=0, cy_off=0):
    """
    Dibuja un cubo con proyeccion isometrica simple.
    cx,cy  = esquina frontal-izquierda inferior del cubo (en pixeles pantalla)
    w      = ancho del cubo (eje X pantalla)
    h      = alto del cubo (eje Y pantalla, positivo hacia arriba)
    d      = profundidad del cubo (eje Z / perspectiva)
    color  = color base
    cx_off,cy_off = offset camara
    """
    x = cx - cx_off
    y = cy - cy_off
    ox, oy = iso_offset(d)

    # Cara frontal (rectangulo normal)
    front = [(x,     y),
             (x+w,   y),
             (x+w,   y-h),
             (x,     y-h)]

    # Cara superior
    top   = [(x,     y-h),
             (x+w,   y-h),
             (x+w+ox, y-h+oy),
             (x+ox,  y-h+oy)]

    # Cara lateral derecha
    right = [(x+w,   y),
             (x+w+ox, y+oy),
             (x+w+ox, y-h+oy),
             (x+w,   y-h)]

    bright  = tuple(min(c+40, 255) for c in color)
    dark    = tuple(max(c-50, 0)   for c in color)
    outline = tuple(max(c-80, 0)   for c in color)

    pygame.draw.polygon(surf, color,  front)
    pygame.draw.polygon(surf, bright, top)
    pygame.draw.polygon(surf, dark,   right)
    pygame.draw.polygon(surf, outline, front, 1)
    pygame.draw.polygon(surf, outline, top,   1)
    pygame.draw.polygon(surf, outline, right, 1)

    # Devuelve el bounding rect de la cara frontal para colisiones
    return pygame.Rect(x, y-h, w, h)


class BrazoRobot:
    PIVOT_COL = 26
    PIVOT_ROW = 15

    LEN_B    = 130
    LEN_A    = 110
    LEN_GARRA = 160  # longitud del rectangulo de la garra
    GROSOR   = 14
    GROSOR_G = 18    # grosor garra
    CUBO_D   = 32

    C_B      = (80,  160, 255)
    C_A      = (120, 200, 255)
    C_PIVOT  = (50,  100, 200)
    C_PUNTO  = (0,   180, 255)
    C_GARRA  = (255, 210, 30)
    C_GARRA2 = (255, 240, 80)

    def __init__(self):
        self.pivot_x = float(self.PIVOT_COL * TILE + TILE // 2)
        self.pivot_y = float(self.PIVOT_ROW * TILE)

        self.ang_b_s  = 100.0
        self.ang_a_s  = 160.0
        self.rot_s    = 0.0
        self.garra_s  = 30.0   # angulo garra suavizado (angulos[0])

        # Fisica del pendulo de la garra
        # ang_pend = angulo actual del pendulo (rad, 0 = recto hacia abajo)
        self.ang_pend  = 0.0
        self.vel_pend  = 0.0

        self.plataformas = []

    # ── helpers ──────────────────────────────────────────────

    def _ang_b_rad(self, deg):
        # 100 -> 0rad (horizontal der), 10 -> -pi/2 (vertical abajo)
        return (deg - 100.0) / 90.0 * (-math.pi / 2.0)

    def _ang_a_rad(self, deg):
        # 160 -> -pi/2 (arriba), 10 -> +pi/2 (abajo)
        return (deg - 85.0) / 75.0 * (-math.pi / 2.0)

    def _calcular(self, scale_x, depth_frac):
        ab = self._ang_b_rad(self.ang_b_s)
        aa = self._ang_a_rad(self.ang_a_s)

        dx1 = math.cos(ab) * self.LEN_B * scale_x
        dy1 = math.sin(ab) * self.LEN_B
        jx1 = self.pivot_x + dx1
        jy1 = self.pivot_y + dy1
        jz1 = math.sin(ab) * self.LEN_B * depth_frac * 0.5

        dx2 = math.cos(aa) * self.LEN_A * scale_x
        dy2 = math.sin(aa) * self.LEN_A
        jx2 = jx1 + dx2
        jy2 = jy1 + dy2
        jz2 = jz1 + math.sin(aa) * self.LEN_A * depth_frac * 0.5

        return (jx1, jy1, jz1), (jx2, jy2, jz2)

    # ── update ───────────────────────────────────────────────

    def get_plataformas(self):
        return self.plataformas

    def update(self, angulos):
        k = 0.15
        self.ang_b_s  += (float(angulos[2]) - self.ang_b_s)  * k
        self.ang_a_s  += (float(angulos[1]) - self.ang_a_s)  * k
        self.rot_s    += (float(angulos[4]) - self.rot_s)    * k
        self.garra_s  += (float(angulos[0]) - self.garra_s)  * k

        # Rotacion invertida: 0=derecha, 90=frente, 180=izquierda
        # scale_x negado para que 180=derecha real -> scale_x positivo a 180
        rot_rad    = math.radians(self.rot_s)
        scale_x    = -math.cos(rot_rad)
        depth_frac = abs(math.sin(rot_rad))

        (jx1, jy1, _), (jx2, jy2, _) = self._calcular(scale_x, depth_frac)

        # ── Fisica pendulo garra ──────────────────────────────
        # tension: 0.0 a 1.0 segun garra_s (30=flojo, 110=rigido)
        tension = max(0.0, min(1.0, (self.garra_s - 30.0) / 80.0))

        # angulo "rigido": alineado con Brazo B
        ab = self._ang_b_rad(self.ang_b_s)
        # En modo rigido la garra apunta en la misma direccion que B
        # En modo flojo cae recto hacia abajo (pendulo con gravedad)
        ang_rigido = ab  # mismo angulo que B (alineado)

        if tension >= 0.85:
            # Rigido: interpola directo al angulo de B, sin fisicas
            target = ang_rigido
            self.ang_pend += (target - self.ang_pend) * 0.25
            self.vel_pend *= 0.5
        else:
            # Pendulo con gravedad simulada
            # La gravedad tira hacia pi/2 (abajo en pantalla)
            # La tension actua como resorte hacia ang_rigido
            gravity_torque = math.cos(self.ang_pend) * 0.018   # gravedad
            spring_torque  = (ang_rigido - self.ang_pend) * tension * 0.12

            # A baja tension (flojo) la garra oscila libremente
            # A tension media empieza a amortiguar
            damping = 0.92 - tension * 0.10   # 0.92 flojo -> 0.82 tension media

            self.vel_pend += gravity_torque + spring_torque
            self.vel_pend *= damping
            self.ang_pend += self.vel_pend

        # Plataformas AABB para colision (solo brazos, no garra)
        self.plataformas = []
        g = self.GROSOR
        for (ax, ay), (bx, by) in [
            ((self.pivot_x, self.pivot_y), (jx1, jy1)),
            ((jx1, jy1),                  (jx2, jy2)),
        ]:
            x0, x1_ = min(ax, bx), max(ax, bx)
            y0, y1_ = min(ay, by), max(ay, by)
            w = max(int(x1_ - x0), g)
            h = max(int(y1_ - y0), g)
            self.plataformas.append(pygame.Rect(int(x0), int(y0), w, h))

        # Plataforma garra (solo si tension alta >= 0.7, la garra es solida)
        if tension >= 0.7:
            gx = jx2 + math.cos(self.ang_pend) * self.LEN_GARRA
            gy = jy2 + math.sin(self.ang_pend) * self.LEN_GARRA
            x0, x1_ = min(jx2, gx), max(jx2, gx)
            y0, y1_ = min(jy2, gy), max(jy2, gy)
            w = max(int(x1_ - x0), self.GROSOR_G)
            h = max(int(y1_ - y0), self.GROSOR_G)
            self.plataformas.append(pygame.Rect(int(x0), int(y0), w, h))

    # ── draw ─────────────────────────────────────────────────

    def _segmento_cubo(self, surf, ax, ay, bx, by, profundidad, color, grosor, cam_x, cam_y):
        g = grosor
        ox, oy = iso_offset(profundidad)

        dx = bx - ax
        dy = by - ay
        length = math.hypot(dx, dy)
        if length < 2:
            return

        nx = -dy / length * g
        ny =  dx / length * g

        def tp(wx, wy):
            return (wx - cam_x, wy - cam_y)

        f0 = tp(ax + nx/2, ay + ny/2)
        f1 = tp(bx + nx/2, by + ny/2)
        f2 = tp(bx - nx/2, by - ny/2)
        f3 = tp(ax - nx/2, ay - ny/2)
        front = [f0, f1, f2, f3]

        t0 = (f0[0] + ox, f0[1] + oy)
        t1 = (f1[0] + ox, f1[1] + oy)
        top = [t0, t1, f1, f0]

        bright  = tuple(min(c + 50, 255) for c in color)
        outline = tuple(max(c - 90, 0)   for c in color)

        pygame.draw.polygon(surf, color,  front)
        pygame.draw.polygon(surf, bright, top)
        pygame.draw.polygon(surf, outline, front, 1)
        pygame.draw.polygon(surf, outline, top,   1)

    def draw(self, surf, cam_x, cam_y):
        rot_rad    = math.radians(self.rot_s)
        scale_x    = -math.cos(rot_rad)
        depth_frac = abs(math.sin(rot_rad))

        (jx1, jy1, jz1), (jx2, jy2, jz2) = self._calcular(scale_x, depth_frac)

        prof = self.CUBO_D * depth_frac

        # Segmento B
        self._segmento_cubo(surf,
                            self.pivot_x, self.pivot_y,
                            jx1, jy1,
                            prof, self.C_B, self.GROSOR, cam_x, cam_y)
        # Segmento A
        self._segmento_cubo(surf,
                            jx1, jy1,
                            jx2, jy2,
                            prof, self.C_A, self.GROSOR, cam_x, cam_y)

        # ── Garra (pendulo) ───────────────────────────────────
        tension = max(0.0, min(1.0, (self.garra_s - 30.0) / 80.0))

        gx = jx2 + math.cos(self.ang_pend) * self.LEN_GARRA
        gy = jy2 + math.sin(self.ang_pend) * self.LEN_GARRA

        # Amarillo, se vuelve mas brillante a mas tension
        r     = 255
        g_col = int(210 + tension * 30)
        color_g = (r, min(g_col, 255), 20)

        self._segmento_cubo(surf,
                            jx2, jy2,
                            gx, gy,
                            prof * 0.5, color_g, self.GROSOR_G, cam_x, cam_y)

        # Cable fino entre efector y garra (cuando esta floja)
        if tension < 0.7:
            sx = int(jx2 - cam_x)
            sy = int(jy2 - cam_y)
            ex = int(gx  - cam_x)
            ey = int(gy  - cam_y)
            alpha = int(180 * (1.0 - tension))
            pygame.draw.line(surf, (180, 160, 30), (sx, sy), (ex, ey), 1)

        def sp(wx, wy):
            return (int(wx - cam_x), int(wy - cam_y))

        px, py   = sp(self.pivot_x, self.pivot_y)
        p1x, p1y = sp(jx1, jy1)
        p2x, p2y = sp(jx2, jy2)
        pgx, pgy = sp(gx, gy)

        # Pivot base
        pygame.draw.circle(surf, self.C_PIVOT, (px, py), 9)
        pygame.draw.circle(surf, (200, 220, 255), (px, py), 9, 2)

        # Articulacion B-A
        pygame.draw.circle(surf, self.C_PUNTO, (p1x, p1y), 7)
        pygame.draw.circle(surf, (255, 255, 255), (p1x, p1y), 7, 1)

        # Efector final (union con garra)
        pygame.draw.circle(surf, self.C_PUNTO, (p2x, p2y), 9)
        pygame.draw.circle(surf, (255, 255, 255), (p2x, p2y), 9, 2)

        # Punta de la garra
        pygame.draw.circle(surf, (255, 210, 30), (pgx, pgy), 6)
        pygame.draw.circle(surf, (255, 255, 150), (pgx, pgy), 6, 1)


# ─────────────────────────────────────────────
class Juego:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Robot Game")
        self.clock  = pygame.time.Clock()

        self.font_big   = pygame.font.SysFont("Consolas", 28, bold=True)
        self.font_med   = pygame.font.SysFont("Consolas", 18, bold=True)
        self.font_small = pygame.font.SysFont("Consolas", 13)
        self.font_tiny  = pygame.font.SysFont("Consolas", 11)

        self.serial   = Serial()
        self.jugador  = Jugador()
        self.doors    = [dict(d) for d in DOORS]
        self.brazo    = BrazoRobot()
        self.cam_x    = 0.0
        self.cam_y    = 0.0

        self.puertos    = []
        self.puerto_sel = 0
        self.navbar_h   = 48
        self.anim_texto = ">> Sin animacion <<  |  Conecta el robot para activar"

        # Botones navbar
        NB = self.navbar_h
        self.btn_prev    = Boton(170, 8, 28, 32, "<",  (30, 60, 100))
        self.btn_next    = Boton(320, 8, 28, 32, ">",  (30, 60, 100))
        self.btn_refr    = Boton(354, 8, 36, 32, "↺",  (30, 60, 100))
        self.btn_con     = Boton(396, 8, 110, 32, "Conectar",    (20, 100, 55))
        self.btn_discon  = Boton(512, 8, 130, 32, "Desconectar", (100, 25, 25))
        self.btns_navbar = [self.btn_prev, self.btn_next, self.btn_refr,
                            self.btn_con, self.btn_discon]

        self._refrescar_puertos()

    def _refrescar_puertos(self):
        self.puertos = self.serial.listar()
        if not self.puertos:
            self.puertos = ["(ninguno)"]
        self.puerto_sel = min(self.puerto_sel, len(self.puertos) - 1)
        auto = self.serial.autodetectar()
        if auto and auto in self.puertos:
            self.puerto_sel = self.puertos.index(auto)

    def _actualizar_puertas(self):
        with self.serial.lock:
            ir = list(self.serial.ir)
        for d in self.doors:
            val = ir[d["idx"]]
            # 0=desaparecida, 0-1000=crece, 1000-4095=tamanio completo
            frac = max(0.0, min(1.0, val / 1000.0))
            target = frac * d["h"]
            d["open_h"] += (target - d["open_h"]) * 0.08

    def run(self):
        keys_held = set()

        while True:
            dt = self.clock.tick(FPS)
            mouse_pos = pygame.mouse.get_pos()

            for btn in self.btns_navbar:
                btn.update(mouse_pos)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.serial.desconectar()
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.KEYDOWN:
                    keys_held.add(event.key)

                if event.type == pygame.KEYUP:
                    keys_held.discard(event.key)

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mp = event.pos
                    if self.btn_prev.clicked(mp):
                        self.puerto_sel = (self.puerto_sel - 1) % max(len(self.puertos), 1)
                    elif self.btn_next.clicked(mp):
                        self.puerto_sel = (self.puerto_sel + 1) % max(len(self.puertos), 1)
                    elif self.btn_refr.clicked(mp):
                        self._refrescar_puertos()
                    elif self.btn_con.clicked(mp):
                        p = self.puertos[self.puerto_sel] if self.puertos else ""
                        if p and p != "(ninguno)":
                            self.serial.conectar(p)
                    elif self.btn_discon.clicked(mp):
                        self.serial.desconectar()

            izq   = pygame.K_LEFT  in keys_held or pygame.K_a in keys_held
            der   = pygame.K_RIGHT in keys_held or pygame.K_d in keys_held
            salto = pygame.K_SPACE in keys_held or pygame.K_UP in keys_held or pygame.K_w in keys_held

            self._actualizar_puertas()

            with self.serial.lock:
                angulos_snap = list(self.serial.angulos)
            self.brazo.update(angulos_snap)

            self.jugador.update(izq, der, salto, self.doors, self.brazo.get_plataformas())

            # Camara suave con scroll X e Y
            tx = self.jugador.x - (GAME_W // 2) + self.jugador.W // 2
            ty = self.jugador.y - (GAME_H // 2) + self.jugador.H // 2
            self.cam_x += (tx - self.cam_x) * 0.12
            self.cam_y += (ty - self.cam_y) * 0.12
            self.cam_x = max(0, min(self.cam_x, MAP_W - GAME_W))
            self.cam_y = max(0, min(self.cam_y, MAP_H - GAME_H))
            cx = int(self.cam_x)
            cy = int(self.cam_y)

            self._draw(cx, cy)

        pygame.quit()

    def _draw(self, cx, cy):
        s = self.screen

        # ── JUEGO ──────────────────────────────────────────────
        game_surf = pygame.Surface((GAME_W, GAME_H))
        game_surf.fill(C_BG)

        # Fondo estrellas estáticas (pseudo-parallax)
        for i in range(80):
            sx = (i * 137 + 23) % GAME_W
            sy = (i * 97  + 11) % GAME_H
            pygame.draw.circle(game_surf, (30, 30, 60), (sx, sy), 1)

        # Tiles
        for t in TILES:
            rx = t.x - cx
            ry = t.y - cy
            if -TILE < rx < GAME_W and -TILE < ry < GAME_H:
                pygame.draw.rect(game_surf, C_TILE, (rx, ry, TILE, TILE))
                pygame.draw.rect(game_surf, C_TILE_OUT, (rx, ry, TILE, TILE), 2)

        # Rampas
        for (tipo, rx2, ry2) in RAMPS:
            rx = rx2 - cx
            ry = ry2 - cy
            if -TILE < rx < GAME_W and -TILE < ry < GAME_H:
                if tipo == "R":
                    pts = [(rx, ry+TILE), (rx+TILE, ry), (rx+TILE, ry+TILE)]
                else:
                    pts = [(rx, ry), (rx+TILE, ry+TILE), (rx, ry+TILE)]
                pygame.draw.polygon(game_surf, C_RAMP, pts)
                pygame.draw.polygon(game_surf, C_RAMP_OUT, pts, 2)

        # Puertas
        for d in self.doors:
            rx = d["x"] - cx
            ry = d["y"] - cy
            color = DOOR_COLORS[d["idx"]]
            h_vis = int(d["h"] - d["open_h"])
            if h_vis > 0 and -TILE < rx < GAME_W and -TILE*4 < ry < GAME_H:
                pygame.draw.rect(game_surf, color, (rx, ry, d["w"], h_vis))
                pygame.draw.rect(game_surf, (255,255,255), (rx, ry, d["w"], h_vis), 2)
                # Etiqueta
                nombres_puerta = ["IR1", "IR2", "IR3", "IR4"]
                txt = self.font_tiny.render(nombres_puerta[d["idx"]], True, (0,0,0))
                game_surf.blit(txt, (rx + 4, ry + 4))

        # Brazo robot
        self.brazo.draw(game_surf, cx, cy)

        # Jugador
        self.jugador.draw(game_surf, cx, cy, self.font_small)

        # Navbar del juego — dibujada sobre la pantalla principal, no game_surf
        # (se dibuja al final en _draw sobre self.screen directamente)
        # Estado serial debajo de navbar
        color_estado = C_OK if "Conectado" in self.serial.estado else C_ERROR
        e_surf = self.font_small.render(self.serial.estado, True, color_estado)
        game_surf.blit(e_surf, (12, self.navbar_h + 6))

        # HUD controles
        ctrl = "← → A D : moverse    SPACE W ↑ : saltar"
        c_surf = self.font_tiny.render(ctrl, True, (80, 80, 120))
        game_surf.blit(c_surf, (12, GAME_H - 20))

        s.blit(game_surf, (0, 0))

        # ── NAVBAR con botones ─────────────────────────────────
        pygame.draw.rect(s, C_NAVBAR, (0, 0, GAME_W, self.navbar_h))
        pygame.draw.line(s, C_TITULO, (0, self.navbar_h), (GAME_W, self.navbar_h), 1)

        # Titulo
        t_surf = self.font_med.render("Robot Game", True, C_TITULO)
        s.blit(t_surf, (10, 13))

        # Label puerto
        lbl = self.font_small.render("Puerto:", True, C_TEXT)
        s.blit(lbl, (138, 17))

        # Puerto seleccionado entre los botones < >
        p_txt = self.puertos[self.puerto_sel] if self.puertos else "-"
        p_surf = self.font_med.render(p_txt, True, C_OK)
        s.blit(p_surf, (202, 13))

        # Botones
        for btn in self.btns_navbar:
            btn.draw(s, self.font_small)

        # Estado conexion a la derecha
        color_estado = C_OK if "Conectado" in self.serial.estado else C_ERROR
        e_surf = self.font_small.render(self.serial.estado, True, color_estado)
        s.blit(e_surf, (660, 17))

        # ── PANEL LATERAL ──────────────────────────────────────
        panel = pygame.Surface((PANEL_W, SCREEN_H))
        panel.fill(C_PANEL)
        pygame.draw.line(panel, C_TITULO, (0, 0), (0, SCREEN_H), 2)

        py = 14
        titulo = self.font_big.render("ROBOT", True, C_TITULO)
        panel.blit(titulo, (PANEL_W//2 - titulo.get_width()//2, py))
        py += 38

        pygame.draw.line(panel, (50, 70, 120), (10, py), (PANEL_W-10, py), 1)
        py += 10

        # Barras de motores (columnas verticales)
        t = self.font_med.render("MOTORES", True, (150, 150, 200))
        panel.blit(t, (PANEL_W//2 - t.get_width()//2, py))
        py += 28

        bar_h    = 160
        bar_w    = 44
        nombres  = list(STAT_INDICES.keys())
        total_w  = len(nombres) * (bar_w + 14)
        start_x  = (PANEL_W - total_w) // 2

        with self.serial.lock:
            angulos = list(self.serial.angulos)

        for i, nombre in enumerate(nombres):
            bx = start_x + i * (bar_w + 14)
            idx = STAT_INDICES[nombre]
            val = angulos[idx]
            lo, hi = STAT_LIMITES[nombre]
            frac = max(0.0, min(1.0, (val - lo) / max(hi - lo, 1)))
            color = STAT_COLORS[nombre]

            # Fondo barra
            pygame.draw.rect(panel, C_DARK, (bx, py, bar_w, bar_h), border_radius=4)
            # Relleno
            fill_h = int(bar_h * frac)
            if fill_h > 0:
                pygame.draw.rect(panel, color,
                                 (bx, py + bar_h - fill_h, bar_w, fill_h),
                                 border_radius=4)
            # Borde
            pygame.draw.rect(panel, color, (bx, py, bar_w, bar_h), 2, border_radius=4)

            # Letra
            lt = self.font_big.render(nombre, True, color)
            panel.blit(lt, (bx + bar_w//2 - lt.get_width()//2, py + bar_h + 4))

            # Valor
            vt = self.font_med.render(str(val), True, C_TEXT)
            panel.blit(vt, (bx + bar_w//2 - vt.get_width()//2, py + bar_h + 30))

            # Limite
            lmt = self.font_tiny.render(f"{lo}-{hi}", True, (100, 100, 140))
            panel.blit(lmt, (bx + bar_w//2 - lmt.get_width()//2, py + bar_h + 50))

        py += bar_h + 70

        pygame.draw.line(panel, (50, 70, 120), (10, py), (PANEL_W-10, py), 1)
        py += 10

        # Barras IR
        t2 = self.font_med.render("SENSORES IR", True, (255, 200, 50))
        panel.blit(t2, (PANEL_W//2 - t2.get_width()//2, py))
        py += 28

        bar_h_ir = 100
        total_w2 = 4 * (bar_w + 14)
        start_x2 = (PANEL_W - total_w2) // 2

        with self.serial.lock:
            ir = list(self.serial.ir)

        for i in range(4):
            bx = start_x2 + i * (bar_w + 14)
            val = ir[i]
            frac = max(0.0, min(1.0, val / 4095.0))
            color_ir = DOOR_COLORS[i]

            pygame.draw.rect(panel, C_DARK, (bx, py, bar_w, bar_h_ir), border_radius=4)
            fill_h = int(bar_h_ir * frac)
            if fill_h > 0:
                pygame.draw.rect(panel, color_ir,
                                 (bx, py + bar_h_ir - fill_h, bar_w, fill_h),
                                 border_radius=4)
            pygame.draw.rect(panel, color_ir, (bx, py, bar_w, bar_h_ir), 2, border_radius=4)

            # Umbral 1000 marcado
            umbral_y = py + bar_h_ir - int(bar_h_ir * 1000/4095)
            pygame.draw.line(panel, (255,255,255), (bx, umbral_y), (bx+bar_w, umbral_y), 1)

            lt = self.font_big.render(str(i+1), True, color_ir)
            panel.blit(lt, (bx + bar_w//2 - lt.get_width()//2, py + bar_h_ir + 4))

            vt = self.font_med.render(str(val), True, C_TEXT)
            panel.blit(vt, (bx + bar_w//2 - vt.get_width()//2, py + bar_h_ir + 30))

        py += bar_h_ir + 56

        # Leyenda puertas
        pygame.draw.line(panel, (50, 70, 120), (10, py), (PANEL_W-10, py), 1)
        py += 8
        leg = self.font_small.render("0=cerrada  1000+=abierta", True, (150,150,150))
        panel.blit(leg, (PANEL_W//2 - leg.get_width()//2, py))
        py += 18
        nombres_door = ["Azul", "Verde", "Rojo", "Amarillo"]
        for i, nd in enumerate(nombres_door):
            pygame.draw.rect(panel, DOOR_COLORS[i], (12, py + i*18, 14, 12), border_radius=2)
            nt = self.font_tiny.render(f"IR{i+1} - {nd}", True, C_TEXT)
            panel.blit(nt, (32, py + i*18))

        s.blit(panel, (GAME_W, 0))

        # Separador
        pygame.draw.line(s, C_TITULO, (GAME_W, 0), (GAME_W, SCREEN_H), 2)

        pygame.display.flip()


# ─────────────────────────────────────────────
if __name__ == "__main__":
    Juego().run()
