import tkinter as tk
import math

CANVAS_W = 700
CANVAS_H = 600
MARGIN = 50

DEFAULT_W_MM = 100
DEFAULT_H_MM = 150
DEFAULT_N = 12


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Líneas radiales con radio")
        self.root.resizable(False, False)

        # Posición vertical del origen en mm desde la línea superior (0 = tope)
        self.origin_offset_mm = 0.0
        self._ctrl_held = False

        # ── Panel de control ────────────────────────────────────────────────
        ctrl = tk.Frame(root, padx=8, pady=6)
        ctrl.pack(side=tk.TOP, fill=tk.X)

        tk.Label(ctrl, text="Ancho (mm):").grid(row=0, column=0, sticky="e")
        self.var_w = tk.IntVar(value=DEFAULT_W_MM)
        tk.Spinbox(ctrl, from_=10, to=2000, textvariable=self.var_w, width=6).grid(row=0, column=1, padx=4)

        tk.Label(ctrl, text="Alto (mm):").grid(row=0, column=2, sticky="e")
        self.var_h = tk.IntVar(value=DEFAULT_H_MM)
        tk.Spinbox(ctrl, from_=10, to=2000, textvariable=self.var_h, width=6).grid(row=0, column=3, padx=4)

        tk.Label(ctrl, text="Líneas:").grid(row=0, column=4, sticky="e")
        self.var_n = tk.IntVar(value=DEFAULT_N)
        tk.Spinbox(ctrl, from_=2, to=72, textvariable=self.var_n, width=5).grid(row=0, column=5, padx=4)

        tk.Button(ctrl, text="Redibujar", command=self._reset_and_redraw).grid(row=0, column=6, padx=10)

        self.lbl_scale = tk.Label(ctrl, text="", fg="gray40", font=("Arial", 8))
        self.lbl_scale.grid(row=0, column=7, padx=6)

        # Etiqueta de posición del origen (visible siempre)
        self.lbl_origin_pos = tk.Label(root,
            text="Origen: 0.00 mm desde la línea superior  |  Ctrl+arrastrar para mover",
            fg="darkred", font=("Arial", 9, "bold"))
        self.lbl_origin_pos.pack(side=tk.TOP, pady=(2, 0))

        self.lbl_info = tk.Label(root, text="Haz click en una línea para medir",
                                  fg="blue", font=("Arial", 9))
        self.lbl_info.pack(side=tk.TOP, pady=1)

        # ── Canvas fijo ─────────────────────────────────────────────────────
        self.canvas = tk.Canvas(root, width=CANVAS_W, height=CANVAS_H,
                                bg="white", cursor="crosshair")
        self.canvas.pack(padx=10, pady=(0, 10))

        # Bindings de click normal
        self.canvas.bind("<Button-1>",        self.on_click)
        self.canvas.bind("<B1-Motion>",       self.on_drag)

        # Ctrl: detectar si está presionado en el momento del click
        self.root.bind("<KeyPress-Control_L>",   self._ctrl_press)
        self.root.bind("<KeyPress-Control_R>",   self._ctrl_press)
        self.root.bind("<KeyRelease-Control_L>", self._ctrl_release)
        self.root.bind("<KeyRelease-Control_R>", self._ctrl_release)

        # Estado interno
        self.scale = 1.0
        self.rect_top_py = 0      # px Y de la línea superior del rectángulo
        self.rect_px = (0, 0, 0, 0)  # (rx, ry, rx+w, ry+h) en px
        self.origin_px = (0, 0)
        self.ray_data = []
        self._dragging_origin = False

        self.redraw()

    # ── Ctrl ────────────────────────────────────────────────────────────────

    def _ctrl_press(self, event):
        self._ctrl_held = True
        self.canvas.config(cursor="sb_v_double_arrow")

    def _ctrl_release(self, event):
        self._ctrl_held = False
        self._dragging_origin = False
        self.canvas.config(cursor="crosshair")

    # ── Utilidades ──────────────────────────────────────────────────────────

    def _compute_scale(self, w_mm, h_mm):
        avail_w = CANVAS_W - 2 * MARGIN
        avail_h = CANVAS_H - 2 * MARGIN
        return min(avail_w / w_mm, avail_h / h_mm)

    def _to_px(self, mm):
        return mm * self.scale

    def _to_mm(self, px):
        return px / self.scale

    # ── Dibujo ──────────────────────────────────────────────────────────────

    def _reset_and_redraw(self):
        self.origin_offset_mm = 0.0
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        self.ray_data = []

        w_mm = self.var_w.get()
        h_mm = self.var_h.get()
        n    = self.var_n.get()

        self.scale = self._compute_scale(w_mm, h_mm)

        w_px = self._to_px(w_mm)
        h_px = self._to_px(h_mm)

        rx = (CANVAS_W - w_px) / 2
        ry = (CANVAS_H - h_px) / 2

        self.rect_px = (rx, ry, rx + w_px, ry + h_px)
        self.rect_top_py = ry

        self.lbl_scale.config(text=f"Escala: 1 mm = {self.scale:.2f} px  |  {w_mm}×{h_mm} mm")

        # Rectángulo
        self.canvas.create_rectangle(rx, ry, rx + w_px, ry + h_px,
                                     outline="black", width=2)

        # Regla
        self._draw_ruler(rx, ry + h_px, w_mm)

        # Origen: centro horizontal, desplazado verticalmente
        ox = rx + w_px / 2
        oy = ry + self._to_px(self.origin_offset_mm)
        # Clamp dentro del rectángulo
        oy = max(ry, min(ry + h_px, oy))
        self.origin_px = (ox, oy)

        self._update_origin_label()
        self._draw_rays(n)
        self._draw_origin_dot()

        self.lbl_info.config(text="Haz click en una línea para medir")
        self.canvas.delete("marker")
        self.canvas.delete("dist_label")

    def _draw_rays(self, n):
        ox, oy = self.origin_px
        rx, ry, rx2, ry2 = self.rect_px
        angle_step = 360.0 / n

        for i in range(n):
            angle_deg = i * angle_step
            angle_rad = math.radians(angle_deg)
            dx = math.cos(angle_rad)
            dy = math.sin(angle_rad)

            end = self._clip_ray_to_rect(ox, oy, dx, dy, rx, ry, rx2, ry2)
            tag = f"ray_{i}"

            if end:
                ex2, ey2 = end
                self.canvas.create_line(ox, oy, ex2, ey2,
                                        fill="steelblue", width=1.5,
                                        tags=(tag, "ray"))
                ray_len = math.hypot(ex2 - ox, ey2 - oy)
                lx = ox + dx * (ray_len + 12)
                ly = oy + dy * (ray_len + 12)
                self.canvas.create_text(lx, ly, text=f"{angle_deg:.0f}°",
                                        font=("Arial", 7), fill="gray50", tags=tag)
                self.ray_data.append({
                    "idx": i, "angle_deg": angle_deg,
                    "dx": dx, "dy": dy, "end_px": (ex2, ey2),
                })
            else:
                self.ray_data.append({
                    "idx": i, "angle_deg": angle_deg,
                    "dx": dx, "dy": dy, "end_px": None,
                })

    def _draw_origin_dot(self):
        ox, oy = self.origin_px
        rx, ry, rx2, ry2 = self.rect_px

        # Línea de referencia horizontal punteada desde el borde izquierdo al origen
        self.canvas.create_line(rx, ry, rx, oy,
                                 fill="salmon", width=1, dash=(3, 3),
                                 tags="origin_guide")
        self.canvas.create_line(rx - 8, oy, rx + 8, oy,
                                 fill="darkred", width=1, tags="origin_guide")

        r = 5
        self.canvas.create_oval(ox - r, oy - r, ox + r, oy + r,
                                 fill="red", outline="darkred", width=2,
                                 tags="origin")
        self.canvas.create_text(ox + 14, oy - 10, text="Origen",
                                 fill="red", font=("Arial", 8, "bold"),
                                 tags="origin")

    def _update_origin_label(self):
        h_mm = self.var_h.get()
        offset = max(0.0, min(h_mm, self.origin_offset_mm))
        self.lbl_origin_pos.config(
            text=f"Origen: {offset:.2f} mm desde la línea superior  |  "
                 "Ctrl+arrastrar para mover"
        )

    def _draw_ruler(self, rx, ry_bottom, w_mm):
        tick_interval = self._nice_interval(w_mm)
        y0 = ry_bottom + 6
        y1 = y0 + 6
        self.canvas.create_line(rx, y0, rx + self._to_px(w_mm), y0,
                                 fill="gray60", width=1)
        mm = 0
        while mm <= w_mm + 0.001:
            xp = rx + self._to_px(mm)
            self.canvas.create_line(xp, y0, xp, y1, fill="gray60")
            self.canvas.create_text(xp, y1 + 7, text=str(int(mm)),
                                     font=("Arial", 6), fill="gray50")
            mm += tick_interval

    def _nice_interval(self, total_mm):
        for step in [1, 2, 5, 10, 20, 25, 50, 100, 200, 500]:
            if self._to_px(step) >= 20:
                return step
        return total_mm / 5

    # ── Recorte de rayo ──────────────────────────────────────────────────────

    def _clip_ray_to_rect(self, ox, oy, dx, dy, x1, y1, x2, y2):
        t_min = 1e-6
        t_max = 1e9
        for o, d, lo, hi in [(ox, dx, x1, x2), (oy, dy, y1, y2)]:
            if abs(d) < 1e-12:
                if o < lo or o > hi:
                    return None
            else:
                t1 = (lo - o) / d
                t2 = (hi - o) / d
                if t1 > t2:
                    t1, t2 = t2, t1
                t_min = max(t_min, t1)
                t_max = min(t_max, t2)
                if t_min > t_max:
                    return None
        t = t_max
        return (ox + dx * t, oy + dy * t)

    # ── Etiqueta de punto ────────────────────────────────────────────────────

    def _draw_point_label(self, px, py, dist_mm, color, font_size=7):
        """Dibuja encima: distancia en mm. Debajo: (X,Y) desde borde sup-izq del rect."""
        rx, ry, rx2, ry2 = self.rect_px
        x_mm = self._to_mm(px - rx)
        y_mm = self._to_mm(py - ry)
        # Radio arriba del punto
        self.canvas.create_text(px, py - 10,
                                 text=f"{dist_mm:.2f} mm",
                                 font=("Arial", font_size, "bold"), fill=color,
                                 tags="dist_label")
        # Coordenadas debajo
        self.canvas.create_text(px, py + 11,
                                 text=f"({x_mm:.1f}, {y_mm:.1f})",
                                 font=("Arial", font_size), fill=color,
                                 tags="dist_label")

    # ── Interacción ─────────────────────────────────────────────────────────

    def on_click(self, event):
        if self._ctrl_held:
            self._dragging_origin = True
            self._move_origin_to_y(event.y)
            return

        self._dragging_origin = False
        cx, cy = event.x, event.y
        hit = self._find_nearest_ray(cx, cy, threshold=10)
        if hit is None:
            return

        ray = hit["ray"]
        t   = hit["t"]
        ox, oy = self.origin_px
        dist_mm = t / self.scale

        px_click = ox + ray["dx"] * t
        py_click = oy + ray["dy"] * t

        self.lbl_info.config(
            text=f"Línea {ray['idx']+1} ({ray['angle_deg']:.0f}°)  |  "
                 f"radio = {dist_mm:.2f} mm"
        )

        self.canvas.delete("marker")
        self.canvas.delete("dist_label")

        self.canvas.create_oval(ox - t, oy - t, ox + t, oy + t,
                                  outline="lightgreen", width=1, dash=(3, 4),
                                  tags="marker")
        self.canvas.create_line(ox, oy, px_click, py_click,
                                 fill="green", width=2, dash=(5, 3), tags="marker")
        r = 5
        self.canvas.create_oval(px_click - r, py_click - r,
                                  px_click + r, py_click + r,
                                  fill="orange", outline="darkorange", tags="marker")
        self._draw_point_label(px_click, py_click, dist_mm, "darkorange", font_size=8)

        for other in self.ray_data:
            if other["idx"] == ray["idx"] or other["end_px"] is None:
                continue
            end_dist = math.hypot(other["end_px"][0] - ox, other["end_px"][1] - oy)
            if t > end_dist + 1:
                continue
            px2 = ox + other["dx"] * t
            py2 = oy + other["dy"] * t
            self.canvas.create_oval(px2 - 4, py2 - 4, px2 + 4, py2 + 4,
                                     fill="gold", outline="orange", tags="marker")
            self.canvas.create_line(ox, oy, px2, py2,
                                     fill="green", width=1, dash=(2, 4), tags="marker")
            self._draw_point_label(px2, py2, dist_mm, "darkgreen")

    def on_drag(self, event):
        if self._ctrl_held and self._dragging_origin:
            self._move_origin_to_y(event.y)

    def _move_origin_to_y(self, y_px):
        rx, ry, rx2, ry2 = self.rect_px
        # Clamp dentro del rectángulo
        y_clamped = max(ry, min(ry2, y_px))
        self.origin_offset_mm = self._to_mm(y_clamped - ry)
        self.redraw()

    def _find_nearest_ray(self, cx, cy, threshold=10):
        ox, oy = self.origin_px
        best = None
        best_dist = threshold + 1
        for ray in self.ray_data:
            if ray["end_px"] is None:
                continue
            dx, dy = ray["dx"], ray["dy"]
            t = (cx - ox) * dx + (cy - oy) * dy
            if t < 0:
                continue
            perp = abs((cx - ox) * dy - (cy - oy) * dx)
            if perp < best_dist:
                end_dist = math.hypot(ray["end_px"][0] - ox, ray["end_px"][1] - oy)
                if t <= end_dist + 1:
                    best_dist = perp
                    best = {"ray": ray, "t": t}
        return best


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
