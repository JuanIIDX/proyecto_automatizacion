import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading

# ── Configuracion ──────────────────────────────────────────
BAUDRATE = 115200

NOMBRES = [
    "Garra",
    "Brazo A",
    "Brazo B",
    "Rotacion-Brazo",
    "Rotacion-Robot",
    "Canal 15 (auto)",
]

LIMITES = [
    (30,  110),
    (10,  160),
    (10,  100),
    (10,  160),
    (0,   180),
    (0,   180),
]

NOMBRES_IR = ["IR-1 (GPIO32)", "IR-2 (GPIO33)", "IR-3 (GPIO34)", "IR-4 (GPIO35)"]

COLOR_BARRA    = "#00ff99"
COLOR_BARRA_IR = "#ff9900"
COLOR_FONDO    = "#1a1a2e"
COLOR_PANEL    = "#16213e"
COLOR_PANEL_IR = "#1e1a0e"
COLOR_TEXTO    = "#e0e0e0"
COLOR_TITULO   = "#00d4ff"
COLOR_ERROR    = "#ff4444"
COLOR_BTN      = "#0f3460"
COLOR_BTN_A    = "#1a5580"
# ────────────────────────────────────────────────────────────


def listar_puertos():
    return [p.device for p in serial.tools.list_ports.comports()]


class Monitor:
    def __init__(self, root):
        self.root      = root
        self.root.title("Robot Monitor")
        self.root.configure(bg=COLOR_FONDO)
        self.root.resizable(False, False)

        self.angulos = [0] * len(NOMBRES)
        self.ir      = [0] * 4
        self.ser     = None
        self.corriendo = False

        self._construir_ui()
        self._refrescar_puertos()

    # ── UI ──────────────────────────────────────────────────

    def _construir_ui(self):
        tk.Label(
            self.root, text="Robot Monitor",
            font=("Consolas", 20, "bold"),
            bg=COLOR_FONDO, fg=COLOR_TITULO
        ).pack(pady=(16, 4))

        # Selector de puerto
        frame_puerto = tk.Frame(self.root, bg=COLOR_FONDO)
        frame_puerto.pack(pady=(0, 4))

        tk.Label(frame_puerto, text="Puerto:", font=("Consolas", 10),
                 bg=COLOR_FONDO, fg=COLOR_TEXTO).grid(row=0, column=0, padx=(0, 6))

        self.combo_puerto = ttk.Combobox(frame_puerto, width=14,
                                         font=("Consolas", 10), state="readonly")
        self.combo_puerto.grid(row=0, column=1, padx=(0, 6))

        tk.Button(frame_puerto, text="↺", font=("Consolas", 11, "bold"),
                  bg=COLOR_BTN, fg=COLOR_TEXTO, activebackground=COLOR_BTN_A,
                  relief="flat", padx=6, pady=2,
                  command=self._refrescar_puertos).grid(row=0, column=2, padx=(0, 10))

        tk.Button(frame_puerto, text="Conectar", font=("Consolas", 10),
                  bg="#1a6b3a", fg=COLOR_TEXTO, activebackground="#237a47",
                  relief="flat", padx=10, pady=2,
                  command=self._conectar_seleccionado).grid(row=0, column=3, padx=(0, 6))

        tk.Button(frame_puerto, text="Desconectar", font=("Consolas", 10),
                  bg="#6b1a1a", fg=COLOR_TEXTO, activebackground="#7a2323",
                  relief="flat", padx=10, pady=2,
                  command=self._desconectar).grid(row=0, column=4)

        self.lbl_estado = tk.Label(self.root, text="Sin conectar",
                                   font=("Consolas", 10), bg=COLOR_FONDO, fg=COLOR_TEXTO)
        self.lbl_estado.pack(pady=(4, 8))

        # ── Seccion angulos ──
        tk.Label(self.root, text="ÁNGULOS",
                 font=("Consolas", 11, "bold"),
                 bg=COLOR_FONDO, fg=COLOR_TITULO).pack(anchor="w", padx=20)

        self.barras  = []
        self.lbl_val = []

        for i, nombre in enumerate(NOMBRES):
            frame = tk.Frame(self.root, bg=COLOR_PANEL, padx=12, pady=6)
            frame.pack(fill="x", padx=20, pady=2)

            tk.Label(frame, text=nombre, font=("Consolas", 10, "bold"),
                     bg=COLOR_PANEL, fg=COLOR_TITULO,
                     width=18, anchor="w").grid(row=0, column=0, rowspan=2, sticky="w")

            canvas = tk.Canvas(frame, width=300, height=16,
                                bg="#0d0d1a", highlightthickness=0)
            canvas.grid(row=0, column=1, padx=(8, 8))
            canvas.create_rectangle(0, 0, 300, 16, fill="#0d0d1a", outline="")
            barra_id = canvas.create_rectangle(0, 0, 0, 16, fill=COLOR_BARRA, outline="")
            self.barras.append((canvas, barra_id))

            lv = tk.Label(frame, text="  0°", font=("Consolas", 11, "bold"),
                          bg=COLOR_PANEL, fg=COLOR_TEXTO, width=6, anchor="e")
            lv.grid(row=0, column=2)
            self.lbl_val.append(lv)

            lo, hi = LIMITES[i]
            tk.Label(frame, text=f"{lo}°–{hi}°", font=("Consolas", 7),
                     bg=COLOR_PANEL, fg="#666688").grid(row=1, column=1, sticky="w", padx=(8, 0))

        # ── Seccion sensores IR ──
        tk.Label(self.root, text="SENSORES IR (crudo 0–4095)",
                 font=("Consolas", 11, "bold"),
                 bg=COLOR_FONDO, fg="#ff9900").pack(anchor="w", padx=20, pady=(10, 2))

        self.barras_ir  = []
        self.lbl_val_ir = []

        for i, nombre in enumerate(NOMBRES_IR):
            frame = tk.Frame(self.root, bg=COLOR_PANEL_IR, padx=12, pady=6)
            frame.pack(fill="x", padx=20, pady=2)

            tk.Label(frame, text=nombre, font=("Consolas", 10, "bold"),
                     bg=COLOR_PANEL_IR, fg="#ff9900",
                     width=18, anchor="w").grid(row=0, column=0, sticky="w")

            canvas = tk.Canvas(frame, width=300, height=16,
                                bg="#0d0d1a", highlightthickness=0)
            canvas.grid(row=0, column=1, padx=(8, 8))
            canvas.create_rectangle(0, 0, 300, 16, fill="#0d0d1a", outline="")
            barra_id = canvas.create_rectangle(0, 0, 0, 16, fill=COLOR_BARRA_IR, outline="")
            self.barras_ir.append((canvas, barra_id))

            lv = tk.Label(frame, text="   0", font=("Consolas", 11, "bold"),
                          bg=COLOR_PANEL_IR, fg=COLOR_TEXTO, width=6, anchor="e")
            lv.grid(row=0, column=2)
            self.lbl_val_ir.append(lv)

    def _actualizar_barra(self, i, angulo):
        lo, hi = LIMITES[i]
        fraccion = (angulo - lo) / max(hi - lo, 1)
        ancho = int(300 * max(0.0, min(1.0, fraccion)))
        canvas, barra_id = self.barras[i]
        canvas.coords(barra_id, 0, 0, ancho, 16)
        self.lbl_val[i].config(text=f"{angulo:4d}°")

    def _actualizar_barra_ir(self, i, valor):
        fraccion = valor / 4095
        ancho = int(300 * max(0.0, min(1.0, fraccion)))
        canvas, barra_id = self.barras_ir[i]
        canvas.coords(barra_id, 0, 0, ancho, 16)
        self.lbl_val_ir[i].config(text=f"{valor:4d}")

    # ── Puertos ─────────────────────────────────────────────

    def _refrescar_puertos(self):
        puertos = listar_puertos()
        self.combo_puerto["values"] = puertos
        if puertos:
            for p in serial.tools.list_ports.comports():
                desc = (p.description or "").lower()
                if any(k in desc for k in ("cp210", "ch340", "esp32", "uart", "usb serial")):
                    self.combo_puerto.set(p.device)
                    return
            self.combo_puerto.current(0)
        else:
            self.combo_puerto.set("")
            self.lbl_estado.config(text="No hay puertos disponibles", fg=COLOR_ERROR)

    # ── Conexion ─────────────────────────────────────────────

    def _conectar_seleccionado(self):
        puerto = self.combo_puerto.get()
        if not puerto:
            self.lbl_estado.config(text="Selecciona un puerto primero", fg=COLOR_ERROR)
            return
        self._desconectar()
        try:
            self.ser = serial.Serial(puerto, BAUDRATE, timeout=1)
            self.corriendo = True
            self.lbl_estado.config(text=f"Conectado en {puerto}", fg="#00ff99")
            threading.Thread(target=self._leer_serial, daemon=True).start()
        except Exception as e:
            self.lbl_estado.config(text=f"Error: {e}", fg=COLOR_ERROR)

    def _desconectar(self):
        self.corriendo = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.lbl_estado.config(text="Desconectado", fg=COLOR_TEXTO)

    # ── Lectura serial ───────────────────────────────────────

    def _leer_serial(self):
        while self.corriendo:
            try:
                linea = self.ser.readline().decode("utf-8", errors="ignore").strip()

                if linea.startswith("ANGULOS:"):
                    partes = linea[8:].split(",")
                    if len(partes) == len(NOMBRES):
                        vals = [int(p) for p in partes]
                        self.root.after(0, self._aplicar_angulos, vals)

                elif linea.startswith("IR:"):
                    partes = linea[3:].split(",")
                    if len(partes) == 4:
                        vals = [int(p) for p in partes]
                        self.root.after(0, self._aplicar_ir, vals)

            except Exception:
                if self.corriendo:
                    self.root.after(0, self.lbl_estado.config,
                                    {"text": "Conexión perdida", "fg": COLOR_ERROR})
                break

    def _aplicar_angulos(self, vals):
        for i, v in enumerate(vals):
            self.angulos[i] = v
            self._actualizar_barra(i, v)

    def _aplicar_ir(self, vals):
        for i, v in enumerate(vals):
            self.ir[i] = v
            self._actualizar_barra_ir(i, v)


if __name__ == "__main__":
    root = tk.Tk()
    app  = Monitor(root)
    root.mainloop()
