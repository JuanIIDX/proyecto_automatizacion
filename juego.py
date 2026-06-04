import tkinter as tk
from tkinter import ttk
import threading
import serial
import serial.tools.list_ports
import math

# ─────────────────────────────────────────────
# CONFIGURACION
# ─────────────────────────────────────────────
BAUDRATE   = 115200
TILE       = 32          # tamaño de cada celda del tilemap
FPS        = 60
GAME_W     = 640
GAME_H     = 480
PANEL_W    = 220

GRAV       = 0.5
JUMP_V     = -10
PLAYER_SPD = 3

# Colores
C_BG       = "#0d0d1a"
C_TILE     = "#3a6fd8"
C_RAMP     = "#2a9d8f"
C_PLAYER   = "#57cc80"
C_TEXT     = "#e0e0e0"
C_TITULO   = "#00d4ff"
C_PANEL    = "#16213e"
C_NAVBAR   = "#0f3460"
C_ERROR    = "#ff4444"
C_OK       = "#00ff99"
C_BAR_A    = "#00d4ff"
C_BAR_B    = "#ff9900"
C_BAR_R    = "#cc44ff"
C_BAR_X    = "#ff4466"
C_BAR_IR   = "#ffdd44"

# Limites para las barras de estadisticas
LIMITES_STATS = {
    "A": (10, 160),   # Brazo A  - indice 1
    "B": (10, 100),   # Brazo B  - indice 2
    "R": (0,  180),   # Rot Robot- indice 4
    "X": (30, 110),   # Garra    - indice 0
}
STAT_INDICES = {"A": 1, "B": 2, "R": 4, "X": 0}
STAT_COLORS  = {"A": C_BAR_A, "B": C_BAR_B, "R": C_BAR_R, "X": C_BAR_X}

# ─────────────────────────────────────────────
# TILEMAP  (0=vacio, 1=bloque, 2=rampa-der, 3=rampa-izq)
# ─────────────────────────────────────────────
MAPA = [
    "                    ",
    "                    ",
    "                    ",
    "                    ",
    "         1          ",
    "       112          ",
    "                    ",
    "   1                ",
    "   1    2           ",
    "   1   11    3      ",
    "   1         1      ",
    "11111111111111111111",
    "11111111111111111111",
]

def parse_mapa(mapa):
    tiles  = []
    ramps  = []
    for row, line in enumerate(mapa):
        for col, ch in enumerate(line):
            x = col * TILE
            y = row * TILE
            if ch == "1":
                tiles.append((x, y, TILE, TILE))
            elif ch == "2":   # rampa sube de izq a der
                ramps.append(("R", x, y, TILE, TILE))
            elif ch == "3":   # rampa sube de der a izq
                ramps.append(("L", x, y, TILE, TILE))
    return tiles, ramps

TILES, RAMPS = parse_mapa(MAPA)
MAP_W = len(MAPA[0]) * TILE
MAP_H = len(MAPA)    * TILE

# ─────────────────────────────────────────────
# JUGADOR
# ─────────────────────────────────────────────
class Jugador:
    W = 24
    H = 28

    def __init__(self):
        self.x     = 80.0
        self.y     = 200.0
        self.vx    = 0.0
        self.vy    = 0.0
        self.suelo = False
        self.cara  = 1    # 1=der, -1=izq

    def rect(self):
        return (self.x, self.y, self.x + self.W, self.y + self.H)

    def mover(self, izq, der, salto):
        self.vx = 0
        if izq:
            self.vx = -PLAYER_SPD
            self.cara = -1
        if der:
            self.vx =  PLAYER_SPD
            self.cara =  1
        if salto and self.suelo:
            self.vy = JUMP_V
            self.suelo = False

        self.vy += GRAV
        if self.vy > 16: self.vy = 16

        # Mover X
        self.x += self.vx
        self._colision_x()

        # Mover Y
        self.y += self.vy
        self.suelo = False
        self._colision_y()
        self._colision_rampas()

        # Limites mapa
        if self.x < 0:           self.x = 0
        if self.x + self.W > MAP_W: self.x = MAP_W - self.W

    def _colision_x(self):
        for (tx, ty, tw, th) in TILES:
            if self._overlap(tx, ty, tx+tw, ty+th):
                if self.vx > 0:
                    self.x = tx - self.W
                elif self.vx < 0:
                    self.x = tx + tw
                self.vx = 0

    def _colision_y(self):
        for (tx, ty, tw, th) in TILES:
            if self._overlap(tx, ty, tx+tw, ty+th):
                if self.vy > 0:
                    self.y = ty - self.H
                    self.vy = 0
                    self.suelo = True
                elif self.vy < 0:
                    self.y = ty + th
                    self.vy = 0

    def _colision_rampas(self):
        cx = self.x + self.W / 2
        pie = self.y + self.H
        for (tipo, rx, ry, rw, rh) in RAMPS:
            if rx <= cx <= rx + rw and ry <= pie <= ry + rh + 4:
                t = (cx - rx) / rw
                if tipo == "R":
                    suelo_y = ry + rh - t * rh
                else:
                    suelo_y = ry + t * rh
                if pie >= suelo_y - 2:
                    self.y = suelo_y - self.H
                    self.vy = 0
                    self.suelo = True

    def _overlap(self, x1, y1, x2, y2):
        return (self.x < x2 and self.x + self.W > x1 and
                self.y < y2 and self.y + self.H > y1)


# ─────────────────────────────────────────────
# APLICACION PRINCIPAL
# ─────────────────────────────────────────────
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Robot Game")
        self.root.configure(bg=C_BG)
        self.root.resizable(False, False)

        # Datos del robot
        self.angulos = [0] * 6
        self.ir      = [0] * 4
        self.ser     = None
        self.corriendo_serial = False

        # Jugador y controles
        self.jugador  = Jugador()
        self.keys     = set()

        # Camara
        self.cam_x = 0.0

        # Texto animacion
        self.anim_texto = "Sin animacion"

        self._construir_ui()
        self._bind_keys()
        self._tick()

    # ─── UI ───────────────────────────────────

    def _construir_ui(self):
        # NAVBAR
        navbar = tk.Frame(self.root, bg=C_NAVBAR, height=36)
        navbar.pack(fill="x")
        navbar.pack_propagate(False)

        tk.Label(navbar, text="Robot Game", font=("Consolas", 13, "bold"),
                 bg=C_NAVBAR, fg=C_TITULO).pack(side="left", padx=12)

        tk.Label(navbar, text="Puerto:", font=("Consolas", 9),
                 bg=C_NAVBAR, fg=C_TEXT).pack(side="left", padx=(20, 4))

        self.combo = ttk.Combobox(navbar, width=10, font=("Consolas", 9), state="readonly")
        self.combo.pack(side="left", padx=(0, 4))

        tk.Button(navbar, text="↺", font=("Consolas", 10, "bold"),
                  bg=C_PANEL, fg=C_TEXT, relief="flat", padx=4,
                  command=self._refrescar_puertos).pack(side="left", padx=(0, 4))

        tk.Button(navbar, text="Conectar", font=("Consolas", 9),
                  bg="#1a6b3a", fg=C_TEXT, relief="flat", padx=8,
                  command=self._conectar).pack(side="left", padx=(0, 4))

        tk.Button(navbar, text="Desconectar", font=("Consolas", 9),
                  bg="#6b1a1a", fg=C_TEXT, relief="flat", padx=8,
                  command=self._desconectar).pack(side="left")

        self.lbl_estado = tk.Label(navbar, text="Sin conectar",
                                   font=("Consolas", 9), bg=C_NAVBAR, fg=C_TEXT)
        self.lbl_estado.pack(side="right", padx=12)

        # CUERPO
        cuerpo = tk.Frame(self.root, bg=C_BG)
        cuerpo.pack()

        # Canvas del juego
        frame_juego = tk.Frame(cuerpo, bg=C_BG)
        frame_juego.pack(side="left")

        self.lbl_anim = tk.Label(frame_juego, text=self.anim_texto,
                                 font=("Consolas", 10), bg=C_BG, fg=C_TITULO,
                                 width=GAME_W // 8)
        self.lbl_anim.pack(pady=(4, 0))

        self.canvas = tk.Canvas(frame_juego, width=GAME_W, height=GAME_H,
                                bg=C_BG, highlightthickness=0)
        self.canvas.pack()

        # Panel lateral
        panel = tk.Frame(cuerpo, bg=C_PANEL, width=PANEL_W)
        panel.pack(side="left", fill="y", padx=(4, 0))
        panel.pack_propagate(False)

        tk.Label(panel, text="ROBOT STATS", font=("Consolas", 10, "bold"),
                 bg=C_PANEL, fg=C_TITULO).pack(pady=(10, 4))

        # Barras de motores
        self.bar_frames = {}
        self.bar_canvas = {}
        self.bar_val    = {}
        self.bar_ids    = {}

        frame_bars = tk.Frame(panel, bg=C_PANEL)
        frame_bars.pack(padx=8, pady=4)

        bar_h  = 120
        bar_w  = 30
        nombres_stats = ["A", "B", "R", "X"]

        for i, nombre in enumerate(nombres_stats):
            col = tk.Frame(frame_bars, bg=C_PANEL)
            col.grid(row=0, column=i, padx=6)

            c = tk.Canvas(col, width=bar_w, height=bar_h,
                          bg="#0d0d1a", highlightthickness=1,
                          highlightbackground="#333355")
            c.pack()
            fondo_id = c.create_rectangle(0, 0, bar_w, bar_h, fill="#0d0d1a", outline="")
            barra_id = c.create_rectangle(0, bar_h, bar_w, bar_h,
                                          fill=STAT_COLORS[nombre], outline="")
            self.bar_canvas[nombre] = c
            self.bar_ids[nombre]    = (fondo_id, barra_id)

            tk.Label(col, text=nombre, font=("Consolas", 11, "bold"),
                     bg=C_PANEL, fg=STAT_COLORS[nombre]).pack()

            lv = tk.Label(col, text="0", font=("Consolas", 8),
                          bg=C_PANEL, fg=C_TEXT)
            lv.pack()
            self.bar_val[nombre] = lv

        # Limites pequeños
        for i, nombre in enumerate(nombres_stats):
            lo, hi = LIMITES_STATS[nombre]
            col_frame = frame_bars.grid_slaves(row=0, column=i)[0]
            tk.Label(col_frame, text=f"{lo}-{hi}", font=("Consolas", 7),
                     bg=C_PANEL, fg="#666688").pack()

        # Separador
        tk.Frame(panel, bg="#333355", height=1).pack(fill="x", padx=8, pady=8)

        # Barras IR
        tk.Label(panel, text="SENSORES IR", font=("Consolas", 10, "bold"),
                 bg=C_PANEL, fg="#ff9900").pack(pady=(0, 4))

        frame_ir = tk.Frame(panel, bg=C_PANEL)
        frame_ir.pack(padx=8)

        self.bar_ir_canvas = []
        self.bar_ir_ids    = []
        self.bar_ir_val    = []

        bar_h_ir = 80

        for i in range(4):
            col = tk.Frame(frame_ir, bg=C_PANEL)
            col.grid(row=0, column=i, padx=4)

            c = tk.Canvas(col, width=bar_w, height=bar_h_ir,
                          bg="#0d0d1a", highlightthickness=1,
                          highlightbackground="#333322")
            c.pack()
            barra_id = c.create_rectangle(0, bar_h_ir, bar_w, bar_h_ir,
                                          fill=C_BAR_IR, outline="")
            self.bar_ir_canvas.append(c)
            self.bar_ir_ids.append(barra_id)

            tk.Label(col, text=str(i+1), font=("Consolas", 10, "bold"),
                     bg=C_PANEL, fg=C_BAR_IR).pack()

            lv = tk.Label(col, text="0", font=("Consolas", 7),
                          bg=C_PANEL, fg=C_TEXT)
            lv.pack()
            self.bar_ir_val.append(lv)

        self._refrescar_puertos()

    def _actualizar_panel(self):
        bar_h = 120
        for nombre, idx in STAT_INDICES.items():
            val = self.angulos[idx]
            lo, hi = LIMITES_STATS[nombre]
            frac = (val - lo) / max(hi - lo, 1)
            frac = max(0.0, min(1.0, frac))
            top  = bar_h - int(bar_h * frac)
            c    = self.bar_canvas[nombre]
            _, barra_id = self.bar_ids[nombre]
            c.coords(barra_id, 0, top, 30, bar_h)
            self.bar_val[nombre].config(text=str(val))

        bar_h_ir = 80
        for i, val in enumerate(self.ir):
            frac = val / 4095
            top  = bar_h_ir - int(bar_h_ir * frac)
            self.bar_ir_canvas[i].coords(self.bar_ir_ids[i], 0, top, 30, bar_h_ir)
            self.bar_ir_val[i].config(text=str(val))

    # ─── JUEGO ────────────────────────────────

    def _bind_keys(self):
        self.root.bind("<KeyPress>",   lambda e: self.keys.add(e.keysym))
        self.root.bind("<KeyRelease>", lambda e: self.keys.discard(e.keysym))

    def _tick(self):
        izq   = "Left"  in self.keys or "a" in self.keys
        der   = "Right" in self.keys or "d" in self.keys
        salto = "space" in self.keys or "Up" in self.keys or "w" in self.keys

        self.jugador.mover(izq, der, salto)

        # Camara sigue al jugador
        target_cam = self.jugador.x - GAME_W // 2 + self.jugador.W // 2
        self.cam_x += (target_cam - self.cam_x) * 0.15
        self.cam_x = max(0, min(self.cam_x, MAP_W - GAME_W))

        self._dibujar()
        self._actualizar_panel()
        self.root.after(1000 // FPS, self._tick)

    def _dibujar(self):
        c  = self.canvas
        cx = int(self.cam_x)
        c.delete("all")

        # Fondo degradado simple
        c.create_rectangle(0, 0, GAME_W, GAME_H, fill=C_BG, outline="")

        # Tiles
        for (tx, ty, tw, th) in TILES:
            x1 = tx - cx
            if x1 > GAME_W or x1 + tw < 0: continue
            c.create_rectangle(x1, ty, x1+tw, ty+th,
                               fill=C_TILE, outline="#2255aa")

        # Rampas (triangulos)
        for (tipo, rx, ry, rw, rh) in RAMPS:
            x1 = rx - cx
            if x1 > GAME_W or x1 + rw < 0: continue
            if tipo == "R":
                pts = [x1, ry+rh,  x1+rw, ry,  x1+rw, ry+rh]
            else:
                pts = [x1, ry,     x1+rw, ry+rh, x1, ry+rh]
            c.create_polygon(pts, fill=C_RAMP, outline="#1a7a70")

        # Jugador
        jx = self.jugador.x - cx
        jy = self.jugador.y
        jw = self.jugador.W
        jh = self.jugador.H
        c.create_rectangle(jx, jy, jx+jw, jy+jh, fill=C_PLAYER, outline="#2a8a50")
        # Ojitos
        ojo_dx = 6 if self.jugador.cara == 1 else 2
        c.create_oval(jx+ojo_dx, jy+6, jx+ojo_dx+5, jy+11, fill="white", outline="")
        c.create_oval(jx+ojo_dx+2, jy+7, jx+ojo_dx+4, jy+9, fill="#0d0d1a", outline="")

        # HUD
        c.create_text(8, 8, text="← → moverse   SPACE saltar",
                      font=("Consolas", 8), fill="#444466", anchor="nw")

    # ─── SERIAL ───────────────────────────────

    def _refrescar_puertos(self):
        puertos = [p.device for p in serial.tools.list_ports.comports()]
        self.combo["values"] = puertos
        if puertos:
            for p in serial.tools.list_ports.comports():
                desc = (p.description or "").lower()
                if any(k in desc for k in ("cp210", "ch340", "esp32", "uart")):
                    self.combo.set(p.device)
                    return
            self.combo.current(0)
        else:
            self.combo.set("")

    def _conectar(self):
        puerto = self.combo.get()
        if not puerto:
            self.lbl_estado.config(text="Selecciona un puerto", fg=C_ERROR)
            return
        self._desconectar()
        try:
            self.ser = serial.Serial(puerto, BAUDRATE, timeout=1)
            self.corriendo_serial = True
            self.lbl_estado.config(text=f"✓ {puerto}", fg=C_OK)
            threading.Thread(target=self._leer_serial, daemon=True).start()
        except Exception as e:
            self.lbl_estado.config(text=f"Error: {e}", fg=C_ERROR)

    def _desconectar(self):
        self.corriendo_serial = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.lbl_estado.config(text="Desconectado", fg=C_TEXT)

    def _leer_serial(self):
        while self.corriendo_serial:
            try:
                linea = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if linea.startswith("ANGULOS:"):
                    partes = linea[8:].split(",")
                    if len(partes) == 6:
                        self.angulos = [int(p) for p in partes]
                elif linea.startswith("IR:"):
                    partes = linea[3:].split(",")
                    if len(partes) == 4:
                        self.ir = [int(p) for p in partes]
            except Exception:
                if self.corriendo_serial:
                    self.root.after(0, self.lbl_estado.config,
                                    {"text": "Conexión perdida", "fg": C_ERROR})
                break


if __name__ == "__main__":
    root = tk.Tk()
    app  = App(root)
    root.mainloop()
