import tkinter as tk
from tkinter import ttk
import math

SCALE = 3  # pixels por milímetro

RECT_W_MM = 100
RECT_H_MM = 150
NUM_LINES = 12

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Líneas con radio")

        # Panel de control
        ctrl = tk.Frame(root, padx=8, pady=8)
        ctrl.pack(side=tk.TOP, fill=tk.X)

        tk.Label(ctrl, text="Ancho (mm):").grid(row=0, column=0, sticky="e")
        self.var_w = tk.IntVar(value=RECT_W_MM)
        tk.Spinbox(ctrl, from_=10, to=500, textvariable=self.var_w, width=6).grid(row=0, column=1, padx=4)

        tk.Label(ctrl, text="Alto (mm):").grid(row=0, column=2, sticky="e")
        self.var_h = tk.IntVar(value=RECT_H_MM)
        tk.Spinbox(ctrl, from_=10, to=500, textvariable=self.var_h, width=6).grid(row=0, column=3, padx=4)

        tk.Label(ctrl, text="Líneas:").grid(row=0, column=4, sticky="e")
        self.var_n = tk.IntVar(value=NUM_LINES)
        tk.Spinbox(ctrl, from_=2, to=50, textvariable=self.var_n, width=5).grid(row=0, column=5, padx=4)

        tk.Button(ctrl, text="Redibujar", command=self.redraw).grid(row=0, column=6, padx=8)

        self.lbl_info = tk.Label(ctrl, text="Click en una línea para medir", fg="blue")
        self.lbl_info.grid(row=0, column=7, padx=8)

        # Canvas
        self.canvas = tk.Canvas(root, bg="white", cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_click)

        self.margin = 40  # px
        self.lines_coords = []  # lista de (x1,y1,x2,y2) en px de cada línea
        self.origin_px = (0, 0)  # punto superior central en px

        self.redraw()

    # ── helpers de coordenadas ────────────────────────────────────────────────

    def mm_to_px(self, val):
        return val * SCALE

    def rect_origin(self):
        """Esquina superior-izquierda del rectángulo en px (canvas)."""
        return (self.margin, self.margin)

    def redraw(self):
        self.canvas.delete("all")
        self.lines_coords = []

        w_mm = self.var_w.get()
        h_mm = self.var_h.get()
        n = self.var_n.get()

        w_px = self.mm_to_px(w_mm)
        h_px = self.mm_to_px(h_mm)

        rx, ry = self.rect_origin()

        # Ajustar tamaño del canvas
        self.canvas.config(width=w_px + 2 * self.margin, height=h_px + 2 * self.margin + 30)

        # Rectángulo
        self.canvas.create_rectangle(rx, ry, rx + w_px, ry + h_px,
                                     outline="black", width=2, tags="rect")

        # Punto de origen: mitad superior del rectángulo
        ox = rx + w_px / 2
        oy = ry
        self.origin_px = (ox, oy)

        r = 6
        self.canvas.create_oval(ox - r, oy - r, ox + r, oy + r,
                                 fill="red", outline="darkred", width=2, tags="origin")

        # Etiqueta del origen
        self.canvas.create_text(ox, oy - 14, text="Origen", fill="red", font=("Arial", 9))

        # 12 líneas equidistantes a lo largo del alto del rectángulo
        # Se distribuyen desde y=0 mm hasta y=h_mm inclusive usando n puntos
        # Cada línea va de (0, yi) a (w_mm, yi) — horizontales
        spacing_mm = h_mm / (n - 1) if n > 1 else 0

        for i in range(n):
            y_mm = i * spacing_mm
            y_px = ry + self.mm_to_px(y_mm)
            x1, x2 = rx, rx + w_px

            tag = f"line_{i}"
            self.canvas.create_line(x1, y_px, x2, y_px,
                                    fill="steelblue", width=2,
                                    tags=(tag, "linea"))
            self.lines_coords.append((x1, y_px, x2, y_px, i, y_mm))

            # Etiqueta de distancia al origen (en mm)
            dist = abs(y_mm)  # origen está en y=0
            self.canvas.create_text(x1 - 5, y_px, text=f"{dist:.1f}", anchor="e",
                                    font=("Arial", 7), fill="gray40", tags=f"lbl_{i}")

        self.lbl_info.config(text="Click en una línea para medir")
        # Limpiar marcadores previos
        self.canvas.delete("marker")
        self.canvas.delete("dist_label")

    # ── interacción ──────────────────────────────────────────────────────────

    def on_click(self, event):
        cx, cy = event.x, event.y
        hit = self._find_nearest_line(cx, cy, threshold=8)
        if hit is None:
            return

        idx, x1, y_px, x2, _, y_mm = hit

        # Punto en la línea clickeada: misma X que el click, Y de la línea
        click_on_line_x = max(x1, min(cx, x2))
        click_on_line_y = y_px

        ox, oy = self.origin_px

        # Distancia en px y en mm
        dist_px = math.hypot(click_on_line_x - ox, click_on_line_y - oy)
        dist_mm = dist_px / SCALE

        self.lbl_info.config(
            text=f"Línea {idx+1} | punto ({(click_on_line_x - x1)/SCALE:.1f}, {y_mm:.1f}) mm "
                 f"| radio = {dist_mm:.2f} mm"
        )

        # Limpiar marcadores anteriores
        self.canvas.delete("marker")
        self.canvas.delete("dist_label")

        # Dibujar punto en línea clickeada
        r = 5
        self.canvas.create_oval(click_on_line_x - r, click_on_line_y - r,
                                 click_on_line_x + r, click_on_line_y + r,
                                 fill="orange", outline="darkorange", tags="marker")

        # Línea de radio desde origen al punto clickeado
        self.canvas.create_line(ox, oy, click_on_line_x, click_on_line_y,
                                 fill="green", width=2, dash=(4, 3), tags="marker")

        # Calcular X del punto a igual distancia en cada otra línea
        # Mantener misma distancia (radio) desde el origen
        # En cada línea i: y fija, buscar x tal que dist(origen, (x,y)) = dist_mm
        # (ox-x)^2 + (oy-y)^2 = dist_mm^2  =>  dx^2 = dist_mm^2 - dy^2
        for lc in self.lines_coords:
            lx1, ly_px, lx2, _, li, ly_mm = lc
            if li == idx:
                continue

            dy_px = ly_px - oy
            radicand = dist_px ** 2 - dy_px ** 2

            if radicand < 0:
                # La distancia es menor que la separación vertical → no hay punto real
                self._mark_impossible(lx1, lx2, ly_px, li)
                continue

            dx_px = math.sqrt(radicand)
            # Hay dos posibles x (a izquierda y derecha del origen)
            # Tomamos el del mismo lado que el click respecto al origen
            sign = 1 if click_on_line_x >= ox else -1
            px = ox + sign * dx_px

            if lx1 <= px <= lx2:
                # Punto dentro del rectángulo
                self.canvas.create_oval(px - 4, ly_px - 4, px + 4, ly_px + 4,
                                        fill="gold", outline="orange", tags="marker")
                self.canvas.create_line(ox, oy, px, ly_px,
                                        fill="green", width=1, dash=(2, 4), tags="marker")
                # Etiqueta de la distancia
                self.canvas.create_text(px + 6, ly_px - 8,
                                        text=f"{dist_mm:.1f}mm",
                                        font=("Arial", 7), fill="darkgreen",
                                        tags="dist_label")
            else:
                self._mark_impossible(lx1, lx2, ly_px, li)

    def _mark_impossible(self, x1, x2, y_px, idx):
        """Marca una línea donde el radio no alcanza o sale del rectángulo."""
        mid_x = (x1 + x2) / 2
        self.canvas.create_text(mid_x, y_px - 8,
                                 text="—",
                                 font=("Arial", 8), fill="red",
                                 tags="dist_label")

    def _find_nearest_line(self, cx, cy, threshold=8):
        """Devuelve la línea más cercana al click (dentro del umbral en Y)."""
        best = None
        best_dist = threshold + 1
        for lc in self.lines_coords:
            x1, y_px, x2, _, li, ly_mm = lc
            if x1 <= cx <= x2:
                d = abs(cy - y_px)
                if d < best_dist:
                    best_dist = d
                    best = (li, x1, y_px, x2, _, ly_mm)
        return best


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
