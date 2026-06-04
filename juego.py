import pygame
import sys
import threading
import serial
import serial.tools.list_ports
import math
import json
import os
from collections import deque

NIVELES_FILE = os.path.join(os.path.dirname(__file__), "niveles.json")

# ─────────────────────────────────────────────
# CONFIGURACION
# ─────────────────────────────────────────────
SCREEN_W  = 1920
SCREEN_H  = 1080
PANEL_W   = 300        # ancho del panel lateral
GAME_W    = SCREEN_W - PANEL_W
GAME_H    = SCREEN_H
TILE      = 60
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
    0: (70,  220, 100),   # IR1 Verde
    1: (255, 220, 50),    # IR2 Amarillo
    2: (255, 70,  70),    # IR3 Rojo
    3: (70,  130, 255),   # IR4 Azul
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
#   'E'               = brazo robot normal
#   'F'               = brazo robot grande (doble tamaño)
# ─────────────────────────────────────────────

MAPA_DEFAULT = [
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

def _mapa_vacio():
    cols, rows = 50, 17
    mapa = [" " * cols for _ in range(rows - 2)]
    mapa += ["1" * cols, "1" * cols]
    return mapa

def _niveles_defecto():
    return {
        "1": MAPA_DEFAULT,
        "2": _mapa_vacio(),
        "3": _mapa_vacio(),
    }

def cargar_niveles():
    if os.path.exists(NIVELES_FILE):
        try:
            with open(NIVELES_FILE, "r") as f:
                data = json.load(f)
            # Asegurar que existan los 3 niveles
            defecto = _niveles_defecto()
            for k in ("1", "2", "3"):
                if k not in data:
                    data[k] = defecto[k]
            return data
        except Exception:
            pass
    return _niveles_defecto()

def guardar_niveles(niveles):
    with open(NIVELES_FILE, "w") as f:
        json.dump(niveles, f, indent=2)

def parse_mapa(raw):
    tiles, ramps, doors, brazos, tesoros = [], [], [], [], []
    spawn = None
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
                               "w": TILE, "h": TILE*3, "open_h": 0.0})
            elif ch == "E":
                brazos.append({"col": col, "row": row, "grande": False})
            elif ch == "F":
                brazos.append({"col": col, "row": row, "grande": True})
            elif ch == "S":
                spawn = (x, y)
            elif ch == "T":
                tesoros.append({"x": x + TILE//4, "y": y + TILE//4,
                                 "w": TILE//2, "h": TILE//2,
                                 "recogido": False})
    return tiles, ramps, doors, brazos, tesoros, spawn

# Estado global del mapa — se recarga al cambiar de nivel
NIVELES   = cargar_niveles()
NIVEL_ACT = "1"

def _cargar_nivel(n):
    global TILES, RAMPS, DOORS, BRAZOS_MAP, TESOROS_BASE, SPAWN_BASE
    global MAP_COLS, MAP_ROWS, MAP_W, MAP_H, NIVEL_ACT
    NIVEL_ACT = str(n)
    raw = NIVELES[NIVEL_ACT]
    MAP_COLS = max(len(r) for r in raw)
    MAP_ROWS = len(raw)
    MAP_W    = MAP_COLS * TILE
    MAP_H    = MAP_ROWS * TILE
    TILES, RAMPS, DOORS, BRAZOS_MAP, TESOROS_BASE, SPAWN_BASE = parse_mapa(raw)

_cargar_nivel(1)

# ─────────────────────────────────────────────
# JUGADOR
# ─────────────────────────────────────────────
class Jugador:
    W, H = 28, 36

    def __init__(self, sx=None, sy=None):
        self.x     = float(sx) if sx is not None else float(TILE * 2)
        self.y     = float(sy) if sy is not None else float(MAP_H - TILE * 3 - self.H)
        self.vx    = 0.0
        self.vy    = 0.0
        self.suelo = False
        self.cara  = 1
        self.anim  = 0.0   # frame de animacion

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.W, self.H)

    def update(self, izq, der, salto, doors, segmentos_brazo=None):
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

        self.x += self.vx
        self._col_x(doors)
        self.y += self.vy
        self.suelo = False
        self._col_y(doors)
        self._col_rampas()
        if segmentos_brazo:
            self._col_segmentos(segmentos_brazo)

        self.x = max(0, min(self.x, MAP_W - self.W))
        if self.y > MAP_H + 200:
            self.y = 0
            self.vy = 0

    def _bloques_activos(self, doors):
        bloques = list(TILES)
        for d in doors:
            # La puerta siempre tiene altura completa, se desplaza hacia arriba
            dy = int(d["y"] - d["open_h"])
            bloques.append(pygame.Rect(d["x"], dy, d["w"], d["h"]))
        return bloques

    def _col_x(self, doors):
        r = self.rect()
        for b in self._bloques_activos(doors):
            if r.colliderect(b):
                if self.vx > 0: self.x = b.left - self.W
                elif self.vx < 0: self.x = b.right
                self.vx = 0
                r = self.rect()

    def _col_y(self, doors):
        r = self.rect()
        for b in self._bloques_activos(doors):
            if r.colliderect(b):
                if self.vy > 0:
                    self.y = b.top - self.H
                    self.vy = 0
                    self.suelo = True
                elif self.vy < 0:
                    self.y = b.bottom
                    self.vy = 0
                r = self.rect()

    def _col_segmentos(self, segmentos):
        """
        Colision con segmentos diagonales del brazo, estilo rampa Super Mario:
        - Proyecta cx del jugador sobre el rango X del segmento
        - Interpola la Y de la superficie en ese punto
        - Si el pie esta sobre o justo debajo de esa Y, lo posa encima
        """
        cx  = self.x + self.W / 2
        pie = self.y + self.H

        for (ax, ay, bx, by, grosor) in segmentos:
            # Rango X del segmento
            x_min = min(ax, bx)
            x_max = max(ax, bx)

            # El jugador debe estar horizontalmente dentro del segmento
            if cx < x_min or cx > x_max:
                continue

            seg_dx = bx - ax
            # Evitar division por cero en segmentos verticales
            if abs(seg_dx) < 1:
                continue

            # Interpolar Y de la superficie en cx
            t  = (cx - ax) / seg_dx          # 0..1 a lo largo del eje X
            sy = ay + t * (by - ay)           # Y de la linea del segmento

            # Margen: el jugador cae sobre la superficie si su pie esta
            # justo por encima o en la superficie (no si ya esta muy abajo)
            if pie >= sy - 2 and pie <= sy + grosor + self.vy + 2:
                self.y     = sy - self.H
                self.vy    = 0
                self.suelo = True

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
        self.temp      = 0.0
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

    def enviar_cmd(self, cmd):
        try:
            if self.ser and self.ser.is_open:
                self.ser.write(f"CMD:{cmd}\n".encode("utf-8"))
        except Exception:
            pass

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
                elif linea.startswith("TEMP:"):
                    try:
                        with self.lock:
                            self.temp = float(linea[5:])
                    except ValueError:
                        pass
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
        self.garra_gx  = 0.0
        self.garra_gy  = 0.0

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

        # ── Fisica garra ─────────────────────────────────────
        # Mapeo de garra_s a angulo objetivo (en radianes, absoluto en pantalla):
        #   110 -> esquina superior (misma dir que Brazo B, apunta hacia arriba-der)
        #    70 -> horizontal (0 rad)
        #    60 -> esquina inferior (apunta hacia abajo)
        #   <60 -> flacido, fisica de pendulo libre

        gs = self.garra_s
        # Angulo de Brazo B en pantalla (para orientar la garra a 110)
        ab = self._ang_b_rad(self.ang_b_s)

        # Angulo absoluto de la garra en pantalla (independiente de los brazos):
        #   110 -> -75 grados (diagonal arriba)   = -5pi/12
        #    70 ->   0 grados (horizontal)         =  0
        #    60 -> +45 grados (diagonal abajo)     = +pi/4
        #   <60 -> flacido, pendulo libre

        if gs >= 70:
            # 110->-75deg, 70->0deg
            frac       = (gs - 70.0) / 40.0
            frac       = max(0.0, min(1.0, frac))
            ang_target = -frac * math.radians(75.0)
            self.ang_pend += (ang_target - self.ang_pend) * 0.20
            self.vel_pend *= 0.3
        elif gs >= 60:
            # 70->0deg, 60->+45deg
            frac       = (70.0 - gs) / 10.0
            frac       = max(0.0, min(1.0, frac))
            ang_target = frac * (math.pi / 4.0)
            self.ang_pend += (ang_target - self.ang_pend) * 0.20
            self.vel_pend *= 0.3
        else:
            # <60: pendulo flacido con gravedad
            flaccidez      = max(0.0, min(1.0, (60.0 - gs) / 30.0))
            gravity_torque = math.cos(self.ang_pend) * (0.015 + flaccidez * 0.02)
            damping        = 0.94 - flaccidez * 0.04
            self.vel_pend += gravity_torque
            self.vel_pend *= damping
            self.ang_pend += self.vel_pend

        # Proyeccion: dx escala con scale_x (igual que brazos)
        gx = jx2 + math.cos(self.ang_pend) * self.LEN_GARRA * scale_x
        gy = jy2 + math.sin(self.ang_pend) * self.LEN_GARRA

        # Guardar posicion de garra para draw
        self.garra_gx = gx
        self.garra_gy = gy

        # Segmentos para colision diagonal (ax,ay,bx,by,grosor)
        self.plataformas = [
            (self.pivot_x, self.pivot_y, jx1, jy1, self.GROSOR),
            (jx1, jy1, jx2, jy2, self.GROSOR),
        ]
        if gs >= 60:
            self.plataformas.append((jx2, jy2, gx, gy, self.GROSOR_G))

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

    def _segmento_cubo_adelante(self, surf, ax, ay, bx, by, profundidad, color, grosor, cam_x, cam_y):
        """Igual que _segmento_cubo pero la cara lateral aparece hacia adelante/abajo."""
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

        # Cara lateral hacia ADELANTE (offset negado = viene hacia la camara)
        b0 = (f3[0] - ox, f3[1] - oy)
        b1 = (f2[0] - ox, f2[1] - oy)
        bottom = [b0, b1, f2, f3]

        bright  = tuple(min(c + 50, 255) for c in color)
        dark    = tuple(max(c - 40,  0)  for c in color)
        outline = tuple(max(c - 90,  0)  for c in color)

        # Dibujar cara delantera primero, luego la frontal encima
        pygame.draw.polygon(surf, dark,   bottom)
        pygame.draw.polygon(surf, color,  front)
        pygame.draw.polygon(surf, outline, bottom, 1)
        pygame.draw.polygon(surf, outline, front,  1)

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

        # ── Garra ────────────────────────────────────────────
        gs  = self.garra_s
        gx  = self.garra_gx
        gy  = self.garra_gy

        # Color: mas rigido = mas brillante
        rigidez = max(0.0, min(1.0, (gs - 60.0) / 50.0))
        g_col   = int(190 + rigidez * 50)
        color_g = (255, min(g_col, 255), 20)

        self._segmento_cubo_adelante(surf,
                            jx2, jy2,
                            gx, gy,
                            prof, color_g, self.GROSOR_G, cam_x, cam_y)

        # Cable fino cuando esta flacida (<60)
        if gs < 60:
            pygame.draw.line(surf, (180, 160, 30),
                             (int(jx2 - cam_x), int(jy2 - cam_y)),
                             (int(gx  - cam_x), int(gy  - cam_y)), 1)

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
# BRAZO GRANDE (doble tamaño)
# ─────────────────────────────────────────────
class BrazoRobotGrande(BrazoRobot):
    LEN_B     = 260
    LEN_A     = 220
    LEN_GARRA = 320
    GROSOR    = 22
    GROSOR_G  = 28
    CUBO_D    = 56

    def __init__(self, pivot_col, pivot_row):
        super().__init__()
        self.pivot_x = float(pivot_col * TILE + TILE // 2)
        self.pivot_y = float(pivot_row  * TILE)


# ─────────────────────────────────────────────
# EDITOR DE MAPAS
# ─────────────────────────────────────────────
PALETA = [
    ("Bloque",      "1", C_TILE),
    ("Rampa Der",   "2", C_RAMP),
    ("Rampa Izq",   "3", C_RAMP),
    ("Puerta A",    "A", DOOR_COLORS[0]),
    ("Puerta B",    "B", DOOR_COLORS[1]),
    ("Puerta C",    "C", DOOR_COLORS[2]),
    ("Puerta D",    "D", DOOR_COLORS[3]),
    ("Brazo",       "E", (80, 160, 255)),
    ("Brazo x2",    "F", (120, 200, 255)),
    ("Spawn",       "S", (87, 204, 128)),
    ("Tesoro",      "T", (255, 160, 30)),
    ("Borrar",      " ", (60,  60,  80)),
]

C_TESORO = (255, 160, 30)

class Editor:
    ITEM_H   = 44
    PALETA_W = 200

    def __init__(self, nivel_key, font_med, font_small):
        self.nivel_key  = nivel_key
        self.font_med   = font_med
        self.font_small = font_small

        self.raw = [list(r) for r in NIVELES[nivel_key]]
        self._normalizar()

        self.cols = max(len(r) for r in self.raw)
        self.rows = len(self.raw)

        # Restaurar zoom y posicion guardados
        self.zoom  = float(NIVELES.get(f"_zoom_{nivel_key}", 1.0))
        self.off_x = float(NIVELES.get(f"_offx_{nivel_key}", 0.0))
        self.off_y = float(NIVELES.get(f"_offy_{nivel_key}", 0.0))
        self.sel     = 0           # indice en PALETA seleccionado
        self.pan_act = False
        self.pan_ox  = 0
        self.pan_oy  = 0
        self.pan_sx  = 0.0
        self.pan_sy  = 0.0

    def _normalizar(self):
        cols = max((len(r) for r in self.raw), default=50)
        for r in self.raw:
            while len(r) < cols:
                r.append(" ")

    def _tile_en(self, mx, my):
        """Convierte posicion pantalla a (col, row) del mapa."""
        area_w = GAME_W - self.PALETA_W
        tx = (mx - self.off_x) / (TILE * self.zoom)
        ty = (my - self.off_y) / (TILE * self.zoom)
        col, row = int(tx), int(ty)
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return col, row
        return None, None

    def _resize(self, accion):
        if accion == "col+":
            for r in self.raw: r.append(" ")
            self.cols += 1
        elif accion == "col-" and self.cols > 5:
            for r in self.raw:
                if len(r) > 1: r.pop()
            self.cols -= 1
        elif accion == "row+":
            self.raw.append([" "] * self.cols)
            self.rows += 1
        elif accion == "row-" and self.rows > 3:
            self.raw.pop()
            self.rows -= 1
        self._guardar()

    def _aplicar_zoom(self, factor, mx, my):
        """Zoom centrado en el punto mx,my de pantalla."""
        zoom_nuevo = max(0.2, min(4.0, self.zoom * factor))
        # Ajustar offset para que el punto bajo el cursor no se mueva
        self.off_x = mx - (mx - self.off_x) * (zoom_nuevo / self.zoom)
        self.off_y = my - (my - self.off_y) * (zoom_nuevo / self.zoom)
        self.zoom  = zoom_nuevo
        self._guardar_vista()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            mx, my = pygame.mouse.get_pos()
            if event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                self._aplicar_zoom(1.2, mx, my)
            elif event.key == pygame.K_MINUS:
                self._aplicar_zoom(1/1.2, mx, my)

        elif event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if event.y > 0:
                self._aplicar_zoom(1.15, mx, my)
            elif event.y < 0:
                self._aplicar_zoom(1/1.15, mx, my)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            area_w = GAME_W - self.PALETA_W

            # Click en botones resize
            bw, bh = 36, 26
            by_base = GAME_H - 36
            resize_acciones = ["col+", "col-", "row+", "row-"]
            for i, acc in enumerate(resize_acciones):
                bx_r = 10 + i * (bw + 6)
                if bx_r <= mx <= bx_r + bw and by_base <= my <= by_base + bh:
                    self._resize(acc)
                    return

            # Click en paleta
            if mx >= area_w:
                idx = (my - 60) // self.ITEM_H
                if 0 <= idx < len(PALETA):
                    self.sel = idx
                return

            if event.button == 1:
                # Alt+click = inicio pan
                if pygame.key.get_mods() & pygame.KMOD_ALT:
                    self.pan_act = True
                    self.pan_ox, self.pan_oy = mx, my
                    self.pan_sx, self.pan_sy = self.off_x, self.off_y
                else:
                    col, row = self._tile_en(mx, my)
                    if col is not None:
                        self._colocar(col, row)
            elif event.button == 3:
                col, row = self._tile_en(mx, my)
                if col is not None:
                    self.raw[row][col] = " "
                    self._guardar()

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.pan_act = False
                self._guardar_vista()

        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            area_w = GAME_W - self.PALETA_W
            if self.pan_act:
                self.off_x = self.pan_sx + (mx - self.pan_ox)
                self.off_y = self.pan_sy + (my - self.pan_oy)
            else:
                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_ALT:
                    pass
                else:
                    if pygame.mouse.get_pressed()[0] and mx < area_w:
                        col, row = self._tile_en(mx, my)
                        if col is not None:
                            self.raw[row][col] = PALETA[self.sel][1]
                            self._guardar()
                    elif pygame.mouse.get_pressed()[2] and mx < area_w:
                        col, row = self._tile_en(mx, my)
                        if col is not None:
                            self.raw[row][col] = " "
                            self._guardar()

    def _colocar(self, col, row):
        ch = PALETA[self.sel][1]
        # Spawn unico: borrar el anterior antes de colocar
        if ch == "S":
            for r in self.raw:
                for c2 in range(len(r)):
                    if r[c2] == "S":
                        r[c2] = " "
        self.raw[row][col] = ch
        self._guardar()

    def _guardar(self):
        NIVELES[self.nivel_key] = ["".join(r) for r in self.raw]
        NIVELES[f"_zoom_{self.nivel_key}"] = self.zoom
        guardar_niveles(NIVELES)
        _cargar_nivel(self.nivel_key)

    def _guardar_vista(self):
        NIVELES[f"_zoom_{self.nivel_key}"] = self.zoom
        NIVELES[f"_offx_{self.nivel_key}"] = self.off_x
        NIVELES[f"_offy_{self.nivel_key}"] = self.off_y
        guardar_niveles(NIVELES)

    def draw(self, surf):
        area_w = GAME_W - self.PALETA_W
        ts = int(TILE * self.zoom)

        # Fondo
        pygame.draw.rect(surf, C_BG, (0, 0, area_w, GAME_H))

        # Grid y tiles
        for row in range(self.rows):
            for col in range(self.cols):
                sx = int(self.off_x + col * ts)
                sy = int(self.off_y + row * ts)
                if sx + ts < 0 or sx > area_w or sy + ts < 0 or sy > GAME_H:
                    continue
                ch = self.raw[row][col]
                # Grid
                pygame.draw.rect(surf, (30, 35, 55), (sx, sy, ts, ts), 1)
                if ch == "1":
                    pygame.draw.rect(surf, C_TILE, (sx+1, sy+1, ts-2, ts-2))
                elif ch == "2":
                    pts = [(sx, sy+ts), (sx+ts, sy), (sx+ts, sy+ts)]
                    pygame.draw.polygon(surf, C_RAMP, pts)
                elif ch == "3":
                    pts = [(sx, sy), (sx+ts, sy+ts), (sx, sy+ts)]
                    pygame.draw.polygon(surf, C_RAMP, pts)
                elif ch in ("A","B","C","D"):
                    idx = ord(ch) - ord("A")
                    pygame.draw.rect(surf, DOOR_COLORS[idx], (sx+2, sy+2, ts-4, ts-4))
                    lbl = self.font_small.render(ch, True, (0,0,0))
                    surf.blit(lbl, (sx + ts//2 - lbl.get_width()//2,
                                    sy + ts//2 - lbl.get_height()//2))
                elif ch == "E":
                    pygame.draw.rect(surf, (80, 160, 255), (sx+2, sy+2, ts-4, ts-4))
                    lbl = self.font_small.render("E", True, (0,0,0))
                    surf.blit(lbl, (sx + ts//2 - lbl.get_width()//2,
                                    sy + ts//2 - lbl.get_height()//2))
                elif ch == "F":
                    pygame.draw.rect(surf, (120, 200, 255), (sx+2, sy+2, ts-4, ts-4))
                    lbl = self.font_small.render("F", True, (0,0,0))
                    surf.blit(lbl, (sx + ts//2 - lbl.get_width()//2,
                                    sy + ts//2 - lbl.get_height()//2))
                elif ch == "S":
                    pygame.draw.rect(surf, (87, 204, 128), (sx+2, sy+2, ts-4, ts-4), border_radius=4)
                    lbl = self.font_small.render("S", True, (0,0,0))
                    surf.blit(lbl, (sx + ts//2 - lbl.get_width()//2,
                                    sy + ts//2 - lbl.get_height()//2))
                elif ch == "T":
                    pygame.draw.rect(surf, C_TESORO, (sx+2, sy+2, ts-4, ts-4), border_radius=4)
                    lbl = self.font_small.render("T", True, (0,0,0))
                    surf.blit(lbl, (sx + ts//2 - lbl.get_width()//2,
                                    sy + ts//2 - lbl.get_height()//2))

        # Separador paleta
        pygame.draw.rect(surf, (20, 25, 45), (area_w, 0, self.PALETA_W, GAME_H))
        pygame.draw.line(surf, C_TITULO, (area_w, 0), (area_w, GAME_H), 2)

        lbl = self.font_med.render("PALETA", True, C_TITULO)
        surf.blit(lbl, (area_w + self.PALETA_W//2 - lbl.get_width()//2, 20))

        for i, (nombre, ch, color) in enumerate(PALETA):
            y = 60 + i * self.ITEM_H
            bg = (40, 55, 90) if i == self.sel else (25, 30, 50)
            pygame.draw.rect(surf, bg, (area_w + 4, y, self.PALETA_W - 8, self.ITEM_H - 4),
                             border_radius=4)
            if i == self.sel:
                pygame.draw.rect(surf, C_TITULO,
                                 (area_w + 4, y, self.PALETA_W - 8, self.ITEM_H - 4),
                                 2, border_radius=4)
            pygame.draw.rect(surf, color, (area_w + 10, y + 8, 20, 20), border_radius=3)
            t = self.font_small.render(nombre, True, C_TEXT)
            surf.blit(t, (area_w + 36, y + 12))

        # Botones redimensionar mapa
        bw, bh = 36, 26
        by_base = GAME_H - 36
        resize_btns = [
            ("+Col", "col+"), ("-Col", "col-"),
            ("+Fil", "row+"), ("-Fil", "row-"),
        ]
        for i, (lbl_r, _) in enumerate(resize_btns):
            bx_r = 10 + i * (bw + 6)
            pygame.draw.rect(surf, (40, 55, 80), (bx_r, by_base, bw, bh), border_radius=4)
            pygame.draw.rect(surf, C_TITULO,     (bx_r, by_base, bw, bh), 1, border_radius=4)
            t_r = self.font_small.render(lbl_r, True, C_TEXT)
            surf.blit(t_r, (bx_r + bw//2 - t_r.get_width()//2,
                            by_base + bh//2 - t_r.get_height()//2))

        # Tamaño actual
        sz = self.font_small.render(f"{self.cols}x{self.rows}", True, (150,150,180))
        surf.blit(sz, (10 + 4*(bw+6) + 8, by_base + 6))

        # Info zoom
        info = self.font_small.render(
            f"Zoom:{self.zoom:.1f}x  +/-zoom  Alt+drag=pan  Clic=colocar  Der=borrar  ESC=salir",
            True, (120, 120, 160))
        surf.blit(info, (10, GAME_H - 18))


# ─────────────────────────────────────────────
# GRAFICA DE SENSORES / MOTORES
# ─────────────────────────────────────────────
class Grafica:
    # 2 minutos a 10 muestras/seg = 1200 puntos
    MAX_PUNTOS  = 1200
    INTERVALO   = 100   # ms entre muestras

    # Colores y etiquetas de cada canal graficado
    CANALES_IR  = [
        ("IR1", DOOR_COLORS[0]),
        ("IR2", DOOR_COLORS[1]),
        ("IR3", DOOR_COLORS[2]),
        ("IR4", DOOR_COLORS[3]),
    ]
    CANALES_MOT = [
        ("Garra",   STAT_COLORS["X"], 0,  (30,  110)),
        ("BrazoA",  STAT_COLORS["A"], 1,  (10,  160)),
        ("BrazoB",  STAT_COLORS["B"], 2,  (10,  100)),
        ("RotRob",  STAT_COLORS["R"], 4,  (0,   180)),
    ]

    def __init__(self):
        self.hist_ir  = [deque(maxlen=self.MAX_PUNTOS) for _ in range(4)]
        self.hist_mot = [deque(maxlen=self.MAX_PUNTOS) for _ in range(4)]
        self.ultimo   = 0

    def muestrear(self, angulos, ir):
        ahora = pygame.time.get_ticks()
        if ahora - self.ultimo < self.INTERVALO:
            return
        self.ultimo = ahora
        for i in range(4):
            self.hist_ir[i].append(ir[i])
        for idx, (_, _, canal, _) in enumerate(self.CANALES_MOT):
            self.hist_mot[idx].append(angulos[canal])

    def draw(self, surf, font_small, font_tiny):
        W, H = surf.get_size()

        # Fondo semi-transparente
        bg = pygame.Surface((W, H), pygame.SRCALPHA)
        bg.fill((8, 8, 20, 210))
        surf.blit(bg, (0, 0))

        margen   = 60
        pad_izq  = 80
        pad_der  = 20
        ancho_g  = W - pad_izq - pad_der
        # Dos gráficas apiladas: IR arriba, Motores abajo
        alto_g   = (H - margen * 3) // 2

        graficas = [
            ("SENSORES IR  (0 – 4095)", self.hist_ir,  self.CANALES_IR,
             [(n, c) for n, c in self.CANALES_IR],
             0, 4095, margen),
            ("MOTORES  (grados)",        self.hist_mot, None,
             [(n, c) for n, c, _, _ in self.CANALES_MOT],
             0, 180,  margen * 2 + alto_g),
        ]

        for titulo, historiales, _, leyenda, vmin, vmax, gy in graficas:
            # Marco
            pygame.draw.rect(surf, (30, 40, 70),
                             (pad_izq - 4, gy - 4, ancho_g + 8, alto_g + 8), border_radius=4)
            pygame.draw.rect(surf, (50, 70, 120),
                             (pad_izq - 4, gy - 4, ancho_g + 8, alto_g + 8), 1, border_radius=4)

            # Título
            t = font_small.render(titulo, True, C_TITULO)
            surf.blit(t, (pad_izq, gy - 22))

            # Lineas de cuadrícula horizontales (4 líneas)
            for gi in range(5):
                vy = gy + int(alto_g * gi / 4)
                pygame.draw.line(surf, (35, 45, 75),
                                 (pad_izq, vy), (pad_izq + ancho_g, vy), 1)
                val_lbl = vmax - (vmax - vmin) * gi // 4
                lbl = font_tiny.render(str(val_lbl), True, (100, 100, 140))
                surf.blit(lbl, (pad_izq - lbl.get_width() - 6, vy - 6))

            # Líneas de tiempo (marcas cada 30s = 300 puntos)
            n_total = self.MAX_PUNTOS
            for ti in range(0, n_total + 1, 300):
                lx = pad_izq + int(ancho_g * ti / n_total)
                pygame.draw.line(surf, (35, 45, 75), (lx, gy), (lx, gy + alto_g), 1)
                seg = (n_total - ti) * self.INTERVALO // 1000
                if seg > 0:
                    tl = font_tiny.render(f"-{seg}s", True, (80, 80, 110))
                    surf.blit(tl, (lx - tl.get_width()//2, gy + alto_g + 3))

            # Datos
            for idx, hist in enumerate(historiales):
                if len(hist) < 2:
                    continue
                if leyenda and idx < len(leyenda):
                    color = leyenda[idx][1]
                else:
                    color = (200, 200, 200)

                pts = list(hist)
                n   = len(pts)
                coords = []
                for pi, v in enumerate(pts):
                    px = pad_izq + int(ancho_g * (pi + n_total - n) / n_total)
                    frac = max(0.0, min(1.0, (v - vmin) / max(vmax - vmin, 1)))
                    py = gy + int(alto_g * (1.0 - frac))
                    coords.append((px, py))

                if len(coords) >= 2:
                    pygame.draw.lines(surf, color, False, coords, 2)

            # Leyenda
            lx_leg = pad_izq
            for nombre, color in leyenda:
                pygame.draw.rect(surf, color, (lx_leg, gy + alto_g + 18, 12, 10))
                lt = font_tiny.render(nombre, True, C_TEXT)
                surf.blit(lt, (lx_leg + 15, gy + alto_g + 17))
                lx_leg += lt.get_width() + 35

        # Instrucción
        hint = font_tiny.render("TAB — cerrar gráfica", True, (80, 80, 120))
        surf.blit(hint, (W - hint.get_width() - 10, H - 18))


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
        self.cam_x    = 0.0
        self.cam_y    = 0.0
        self.modo_editor  = False
        self.editor       = None
        self.grafica      = Grafica()
        self.mostrar_graf = False
        self.pausado      = True
        self.t_inicio     = pygame.time.get_ticks()
        self.t_acum       = 0    # ms acumulados antes de pausas

        self.puertos    = []
        self.puerto_sel = 0
        self.navbar_h   = 48

        # Botones navbar — serial
        self.btn_prev   = Boton(170, 8,  28,  32, "<",           (30, 60, 100))
        self.btn_next   = Boton(320, 8,  28,  32, ">",           (30, 60, 100))
        self.btn_refr   = Boton(354, 8,  36,  32, "↺",           (30, 60, 100))
        self.btn_con    = Boton(396, 8,  110, 32, "Conectar",    (20, 100, 55))
        self.btn_discon = Boton(512, 8,  130, 32, "Desconectar", (100, 25, 25))

        # Botones navbar — niveles
        self.btn_n1     = Boton(670, 8, 70,  32, "Nivel 1", (40, 40, 100))
        self.btn_n2     = Boton(746, 8, 70,  32, "Nivel 2", (40, 40, 100))
        self.btn_n3     = Boton(822, 8, 70,  32, "Nivel 3", (40, 40, 100))
        self.btn_edit   = Boton(902,  8, 110, 32, "Editar Mapa", (80, 40, 80))
        self.btn_pausa  = Boton(1020, 8,  80, 32, "⏸ Pausa",    (60, 60, 20))

        self.btns_navbar = [self.btn_prev, self.btn_next, self.btn_refr,
                            self.btn_con, self.btn_discon,
                            self.btn_n1, self.btn_n2, self.btn_n3,
                            self.btn_edit, self.btn_pausa]

        self._recargar_nivel()
        self._refrescar_puertos()
        auto = self.serial.autodetectar()
        if auto:
            self.serial.conectar(auto)

    def _toggle_pausa(self):
        if self.nivel_completo:
            return
        ahora = pygame.time.get_ticks()
        if self.pausado:
            # Reanudar
            self.t_inicio = ahora
            self.pausado  = False
            self.serial.enviar_cmd("NIVEL_START_RESUME")
        else:
            # Pausar — acumular tiempo transcurrido
            self.t_acum  += ahora - self.t_inicio
            self.pausado  = True
            self.serial.enviar_cmd("PAUSA")

    def _ms_jugados(self):
        if self.pausado or self.nivel_completo:
            return self.t_acum
        return self.t_acum + pygame.time.get_ticks() - self.t_inicio

    def _fmt_tiempo(self, ms):
        seg = ms // 1000
        if seg < 100:
            dec = (ms % 1000) // 10
            return f"{seg:02d}:{dec:02d}"
        else:
            return f"{seg//60:02d}:{seg%60:02d}"

    def _recargar_nivel(self, n=None):
        if n:
            _cargar_nivel(n)
        self.doors   = [dict(d) for d in DOORS]
        self.tesoros = [dict(t) for t in TESOROS_BASE]
        self.brazos  = []
        for b in BRAZOS_MAP:
            if b["grande"]:
                self.brazos.append(BrazoRobotGrande(b["col"], b["row"]))
            else:
                br = BrazoRobot()
                br.pivot_x = float(b["col"] * TILE + TILE // 2)
                br.pivot_y = float(b["row"]  * TILE)
                self.brazos.append(br)
        if not self.brazos:
            self.brazos = [BrazoRobot()]
        # Spawn del jugador
        sx, sy = SPAWN_BASE if SPAWN_BASE else (TILE * 2, MAP_H - TILE * 3)
        self.jugador = Jugador(sx, sy)
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.nivel_completo = False
        self.pausado        = True
        self.t_inicio       = pygame.time.get_ticks()
        self.t_acum         = 0
        self.serial.enviar_cmd("PAUSA")

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
            # 0=arriba (plataforma, paso libre), 1000+=abajo (bloqueando)
            # open_h = desplazamiento hacia arriba (d["h"]=subida del todo, 0=abajo)
            frac   = max(0.0, min(1.0, val / 1000.0))
            target = (1.0 - frac) * d["h"]
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
                    if event.key == pygame.K_ESCAPE and self.modo_editor:
                        self.modo_editor = False
                        self._recargar_nivel()  # envía NIVEL_START internamente
                    elif event.key == pygame.K_r and not self.modo_editor:
                        self._recargar_nivel()
                    elif event.key == pygame.K_TAB:
                        self.mostrar_graf = not self.mostrar_graf
                    elif event.key == pygame.K_p and not self.modo_editor:
                        self._toggle_pausa()

                if event.type == pygame.KEYUP:
                    keys_held.discard(event.key)

                # Pasar eventos al editor si esta activo
                if self.modo_editor and self.editor:
                    self.editor.handle_event(event)

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
                    elif self.btn_n1.clicked(mp):
                        self.modo_editor = False
                        self._recargar_nivel("1")
                    elif self.btn_n2.clicked(mp):
                        self.modo_editor = False
                        self._recargar_nivel("2")
                    elif self.btn_n3.clicked(mp):
                        self.modo_editor = False
                        self._recargar_nivel("3")
                    elif self.btn_edit.clicked(mp):
                        self.modo_editor = not self.modo_editor
                        if self.modo_editor:
                            self.editor = Editor(NIVEL_ACT,
                                                 self.font_med, self.font_small)
                            self.serial.enviar_cmd("EDIT")
                        else:
                            self._recargar_nivel()
                    elif self.btn_pausa.clicked(mp):
                        self._toggle_pausa()

            if not self.modo_editor and not self.pausado:
                izq   = pygame.K_LEFT  in keys_held or pygame.K_a in keys_held
                der   = pygame.K_RIGHT in keys_held or pygame.K_d in keys_held
                salto = pygame.K_SPACE in keys_held or pygame.K_UP in keys_held or pygame.K_w in keys_held

                self._actualizar_puertas()

                with self.serial.lock:
                    angulos_snap = list(self.serial.angulos)
                    ir_snap      = list(self.serial.ir)
                self.grafica.muestrear(angulos_snap, ir_snap)
                for br in self.brazos:
                    br.update(angulos_snap)

                segs = []
                for br in self.brazos:
                    segs.extend(br.get_plataformas())
                self.jugador.update(izq, der, salto, self.doors, segs or None)

                # Recolectar tesoros
                jr = self.jugador.rect()
                for t in self.tesoros:
                    if not t["recogido"]:
                        tr = pygame.Rect(t["x"], t["y"], t["w"], t["h"])
                        if jr.colliderect(tr):
                            t["recogido"] = True
                if self.tesoros and all(t["recogido"] for t in self.tesoros):
                    if not self.nivel_completo:
                        self.serial.enviar_cmd("NIVEL_END")
                    self.nivel_completo = True

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
        nombres_puerta = ["IR1", "IR2", "IR3", "IR4"]
        for d in self.doors:
            rx  = d["x"] - cx
            ry  = int(d["y"] - d["open_h"]) - cy   # desplazada hacia arriba
            color = DOOR_COLORS[d["idx"]]
            h   = d["h"]
            w   = d["w"]
            subida = d["open_h"] / d["h"]           # 0=abajo, 1=arriba del todo

            if -TILE < rx < GAME_W and -h < ry < GAME_H + h:
                # Cuerpo principal
                pygame.draw.rect(game_surf, color, (rx, ry, w, h))

                if subida > 0.8:
                    # Patron diagonal negro — indica que esta arriba (plataforma)
                    paso = 10
                    clip = pygame.Rect(rx, ry, w, h)
                    for offset in range(-h, w + h, paso):
                        x1 = rx + offset
                        y1 = ry
                        x2 = rx + offset + h
                        y2 = ry + h
                        # Recortar manualmente a los limites del rect
                        if x2 < rx or x1 > rx + w:
                            continue
                        pygame.draw.line(game_surf, (0, 0, 0),
                                         (max(x1, rx), y1 + max(0, rx - x1)),
                                         (min(x2, rx + w), y2 - max(0, x2 - (rx + w))), 2)
                else:
                    # Lineas horizontales tipo persiana cuando esta bajando/abajo
                    stripe_c = tuple(min(c + 40, 255) for c in color)
                    for si in range(1, 5):
                        sy2 = ry + int(h * si / 5)
                        pygame.draw.line(game_surf, stripe_c, (rx, sy2), (rx + w, sy2), 1)

                    # Flecha hacia arriba cuando esta en movimiento
                    if subida > 0.05:
                        mid_x = rx + w // 2
                        arr_y = ry + h // 2
                        pygame.draw.polygon(game_surf, (255, 255, 255),
                            [(mid_x, arr_y - 8),
                             (mid_x - 6, arr_y + 2),
                             (mid_x + 6, arr_y + 2)])

                # Borde
                borde_c = (255, 255, 255) if subida > 0.8 else (180, 180, 180)
                pygame.draw.rect(game_surf, borde_c, (rx, ry, w, h), 2)

                # Etiqueta
                txt = self.font_tiny.render(nombres_puerta[d["idx"]], True,
                                            (0, 0, 0) if subida > 0.8 else (0, 0, 0))
                game_surf.blit(txt, (rx + 4, ry + 4))

        # Tesoros
        for t in self.tesoros:
            if not t["recogido"]:
                tx2 = t["x"] - cx
                ty2 = t["y"] - cy
                if -TILE < tx2 < GAME_W and -TILE < ty2 < GAME_H:
                    pygame.draw.rect(game_surf, C_TESORO,
                                     (tx2, ty2, t["w"], t["h"]), border_radius=4)
                    pygame.draw.rect(game_surf, (255, 220, 120),
                                     (tx2, ty2, t["w"], t["h"]), 2, border_radius=4)
                    pygame.draw.rect(game_surf, (255, 240, 180),
                                     (tx2+5, ty2+5, t["w"]//3, t["h"]//3), border_radius=2)

        # Brazos robot
        for br in self.brazos:
            br.draw(game_surf, cx, cy)

        # Jugador
        self.jugador.draw(game_surf, cx, cy, self.font_small)

        # Navbar del juego — dibujada sobre la pantalla principal, no game_surf
        # (se dibuja al final en _draw sobre self.screen directamente)
        # Estado serial debajo de navbar
        color_estado = C_OK if "Conectado" in self.serial.estado else C_ERROR
        e_surf = self.font_small.render(self.serial.estado, True, color_estado)
        game_surf.blit(e_surf, (12, self.navbar_h + 6))

        # HUD tiempo — estilo reloj TM1637 (misma lógica SS:dd / MM:SS)
        t_txt = self._fmt_tiempo(self._ms_jugados())
        t_surf = self.font_big.render(t_txt, True,
                                      (255, 220, 50) if self.nivel_completo else C_TEXT)
        game_surf.blit(t_surf, (GAME_W // 2 - t_surf.get_width() // 2, self.navbar_h + 6))

        # HUD tesoros
        total   = len(self.tesoros)
        cogidos = sum(1 for t in self.tesoros if t["recogido"])
        if total > 0:
            hud_txt = f"Tesoros: {cogidos}/{total}"
            hud_col = C_OK if cogidos == total else C_TESORO
            hud = self.font_med.render(hud_txt, True, hud_col)
            game_surf.blit(hud, (GAME_W - hud.get_width() - 12, self.navbar_h + 8))

        # Pantalla pausa
        if self.pausado and not self.nivel_completo:
            ov = pygame.Surface((GAME_W, GAME_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 160))
            game_surf.blit(ov, (0, 0))
            p1 = self.font_big.render("PAUSA", True, C_TITULO)
            # Expresion tipo reloj: 0 _ _ 0  animada
            tick = (pygame.time.get_ticks() // 600) % 2
            expr = "0     0" if tick == 0 else "-     -"
            p2   = self.font_big.render(expr, True, C_TEXT)
            p3   = self.font_small.render("P / ⏸ para continuar", True, (150, 150, 200))
            game_surf.blit(p1, (GAME_W//2 - p1.get_width()//2, GAME_H//2 - 70))
            game_surf.blit(p2, (GAME_W//2 - p2.get_width()//2, GAME_H//2 - 10))
            game_surf.blit(p3, (GAME_W//2 - p3.get_width()//2, GAME_H//2 + 50))

        # Pantalla nivel completo
        if self.nivel_completo:
            overlay = pygame.Surface((GAME_W, GAME_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 140))
            game_surf.blit(overlay, (0, 0))
            msg1 = self.font_big.render("¡NIVEL COMPLETO!", True, (255, 220, 50))
            msg2 = self.font_med.render("Todos los tesoros recolectados", True, C_TEXT)
            msg3 = self.font_small.render("Pulsa R para reiniciar", True, (150, 150, 200))
            game_surf.blit(msg1, (GAME_W//2 - msg1.get_width()//2, GAME_H//2 - 60))
            game_surf.blit(msg2, (GAME_W//2 - msg2.get_width()//2, GAME_H//2))
            game_surf.blit(msg3, (GAME_W//2 - msg3.get_width()//2, GAME_H//2 + 40))

        # HUD controles
        ctrl = "← → A D : moverse    SPACE W ↑ : saltar"
        c_surf = self.font_tiny.render(ctrl, True, (80, 80, 120))
        game_surf.blit(c_surf, (12, GAME_H - 20))

        # Editor superpuesto si esta activo
        if self.modo_editor and self.editor:
            self.editor.draw(game_surf)

        s.blit(game_surf, (0, 0))

        # ── NAVBAR ────────────────────────────────────────────
        pygame.draw.rect(s, C_NAVBAR, (0, 0, GAME_W, self.navbar_h))
        pygame.draw.line(s, C_TITULO, (0, self.navbar_h), (GAME_W, self.navbar_h), 1)

        t_surf = self.font_med.render("Robot Game", True, C_TITULO)
        s.blit(t_surf, (10, 13))

        lbl = self.font_small.render("Puerto:", True, C_TEXT)
        s.blit(lbl, (138, 17))

        p_txt  = self.puertos[self.puerto_sel] if self.puertos else "-"
        p_surf = self.font_med.render(p_txt, True, C_OK)
        s.blit(p_surf, (202, 13))

        for btn in self.btns_navbar:
            # Resaltar boton del nivel activo
            if btn in (self.btn_n1, self.btn_n2, self.btn_n3):
                n = ("1" if btn is self.btn_n1 else
                     "2" if btn is self.btn_n2 else "3")
                orig = btn.color
                if n == NIVEL_ACT:
                    btn.color = (80, 80, 180)
                btn.draw(s, self.font_small)
                btn.color = orig
            elif btn is self.btn_pausa and self.pausado:
                orig = btn.color
                btn.color = (140, 120, 20)
                btn.draw(s, self.font_small)
                btn.color = orig
            elif btn is self.btn_edit and self.modo_editor:
                orig = btn.color
                btn.color = (120, 40, 120)
                btn.draw(s, self.font_small)
                btn.color = orig
            else:
                btn.draw(s, self.font_small)

        color_estado = C_OK if "Conectado" in self.serial.estado else C_ERROR
        e_surf = self.font_small.render(self.serial.estado, True, color_estado)
        s.blit(e_surf, (1030, 17))

        # ── PANEL LATERAL ──────────────────────────────────────
        panel = pygame.Surface((PANEL_W, SCREEN_H))
        panel.fill(C_PANEL)
        pygame.draw.line(panel, C_TITULO, (0, 0), (0, SCREEN_H), 2)

        py = 14
        titulo = self.font_big.render("ROBOT", True, C_TITULO)
        panel.blit(titulo, (PANEL_W//2 - titulo.get_width()//2, py))
        py += 34

        # Temperatura ESP32
        with self.serial.lock:
            temp = self.serial.temp
        temp_col = (C_OK if temp < 60 else
                    (255, 200, 50) if temp < 75 else
                    C_ERROR)
        temp_txt = self.font_small.render(f"CPU: {temp:.1f}°C", True, temp_col)
        panel.blit(temp_txt, (PANEL_W//2 - temp_txt.get_width()//2, py))
        py += 18

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
        nombres_door = ["Verde", "Amarillo", "Rojo", "Azul"]
        for i, nd in enumerate(nombres_door):
            pygame.draw.rect(panel, DOOR_COLORS[i], (12, py + i*18, 14, 12), border_radius=2)
            nt = self.font_tiny.render(f"IR{i+1} - {nd}", True, C_TEXT)
            panel.blit(nt, (32, py + i*18))

        s.blit(panel, (GAME_W, 0))

        # Separador
        pygame.draw.line(s, C_TITULO, (GAME_W, 0), (GAME_W, SCREEN_H), 2)

        # Gráfica overlay (Tab)
        if self.mostrar_graf:
            self.grafica.draw(s, self.font_small, self.font_tiny)

        pygame.display.flip()


# ─────────────────────────────────────────────
if __name__ == "__main__":
    Juego().run()
