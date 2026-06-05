#include "pantalla.h"
#include "config.h"
#include "servos.h"


bool pantalla_init()
{
  bool ok = false;
  for(int i = 0; i < 10; i++)
  {
    if(oled.begin(SSD1306_SWITCHCAPVCC, 0x3C))
    {
      ok = true;
      break;
    }
    delay(500);
  }
  if(ok)
  {
    oled.clearDisplay();
    oled.display();
  }
  return ok;
}

// =========================
// NAVBAR
// =========================

// Icono control (mando) 11x8 px
static const uint8_t ICONO_CTRL[] = {
  0b00111100,
  0b01111110,
  0b11011011,
  0b11111111,
  0b11111111,
  0b01101110,
  0b00111100,
  0b00011000,
};

// Dibuja icono de control (conectado) o X (desconectado)
static void dibujarIconoControl(int x, int y, bool conectado)
{
  if(conectado)
  {
    for(int row = 0; row < 8; row++)
      for(int col = 0; col < 8; col++)
        if(ICONO_CTRL[row] & (0x80 >> col))
          oled.drawPixel(x + col, y + row, SSD1306_WHITE);
  }
  else
  {
    // X simple 7x7
    oled.drawLine(x,   y,   x+6, y+6, SSD1306_WHITE);
    oled.drawLine(x+6, y,   x,   y+6, SSD1306_WHITE);
  }
}

// Cuadro izquierdo: O si PCA ok, X si no
static void dibujarIconoPCA(int x, int y, bool ok)
{
  oled.drawRect(x, y, 11, 11, SSD1306_WHITE);
  if(ok)
  {
    // Circulo dentro
    oled.drawCircle(x + 5, y + 5, 3, SSD1306_WHITE);
  }
  else
  {
    // X dentro
    oled.drawLine(x+2, y+2, x+8, y+8, SSD1306_WHITE);
    oled.drawLine(x+8, y+2, x+2, y+8, SSD1306_WHITE);
  }
}

void navbar(bool ctrConectado)
{
  // Fondo de la barra
  oled.fillRect(0, 0, 128, NAVBAR_H, SSD1306_BLACK);
  oled.drawFastHLine(0, NAVBAR_H, 128, SSD1306_WHITE);

  // Cuadro PCA izquierda
  dibujarIconoPCA(1, 1, pcaOk);

  // Temperatura en el centro
  float tempC = temperatureRead();
  char buf[8];
  snprintf(buf, sizeof(buf), "%d\xDF" "C", (int)tempC);  // \xDF = simbolo grado en SSD1306
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  // Centrar: cada caracter mide 6px, buf tiene ~5 chars
  int tx = (128 - (int)strlen(buf) * 6) / 2;
  oled.setCursor(tx, 3);
  oled.print(buf);

  // Icono control derecha
  dibujarIconoControl(119, 2, ctrConectado);
}

// =========================
// PANTALLAS
// =========================

void pantalla_menu(int seleccion)
{
  // Menu horizontal: 4 opciones, se muestran 3 a la vez.
  // La ventana visible se desplaza para mantener el seleccionado visible.

  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  navbar(true);

  const char* titulos[MENU_TOTAL]    = { "Control", "Debug",   "Homing",   "Ctrl PC" };
  const char* subtitulos[MENU_TOTAL] = { "Robot",   "Pruebas", "Pos.",     "PC" };

  // Ventana de 3 cuadros — desplazar para mantener seleccion visible
  int primerVisible = seleccion - 1;
  if(primerVisible < 0)              primerVisible = 0;
  if(primerVisible + 3 > MENU_TOTAL) primerVisible = MENU_TOTAL - 3;

  // Dimensiones: 3 cuadros en 128px con margenes de 2px
  int margen = 2;
  int w      = (128 - margen * 4) / 3;   // ~38px cada uno
  int h      = 64 - NAVBAR_H - margen * 2 - 6;  // dejar 6px abajo para puntos
  int y      = NAVBAR_H + margen;

  for(int slot = 0; slot < 3; slot++)
  {
    int idx = primerVisible + slot;
    if(idx >= MENU_TOTAL) break;

    int x   = margen + slot * (w + margen);
    bool sel = (idx == seleccion);

    if(sel)
      oled.fillRect(x, y, w, h, SSD1306_WHITE);
    else
      oled.drawRect(x, y, w, h, SSD1306_WHITE);

    oled.setTextColor(sel ? SSD1306_BLACK : SSD1306_WHITE);
    oled.setTextSize(1);

    // Titulo centrado (puede que no quepa todo — usar subtitulo corto si no)
    const char* lbl = (strlen(titulos[idx]) * 6 <= (unsigned)w) ? titulos[idx] : subtitulos[idx];
    int tx = x + (w - (int)strlen(lbl) * 6) / 2;
    oled.setCursor(tx, y + 8);
    oled.print(lbl);

    // Subtitulo solo si hay espacio (cuadro > 36px)
    if(w > 36)
    {
      int sx = x + (w - (int)strlen(subtitulos[idx]) * 6) / 2;
      oled.setCursor(sx, y + 20);
      oled.print(subtitulos[idx]);
    }
  }

  // Indicador de posicion (puntos en la parte inferior)
  oled.setTextColor(SSD1306_WHITE);
  int dotY       = 62;
  int dotSpacing = 8;
  int dotStartX  = 64 - (MENU_TOTAL * dotSpacing) / 2;
  for(int i = 0; i < MENU_TOTAL; i++)
  {
    int dx = dotStartX + i * dotSpacing;
    if(i == seleccion)
      oled.fillCircle(dx, dotY, 2, SSD1306_WHITE);
    else
      oled.drawCircle(dx, dotY, 2, SSD1306_WHITE);
  }

  oled.display();
}

void pantalla_control(int indiceCanal, int pos, int sel, bool ctrOk)
{
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  navbar(ctrOk);

  oled.setTextSize(1);
  oled.setCursor(0, NAVBAR_H + 2);
  oled.print(canales[indiceCanal].nombre);
  oled.print(" (");
  oled.print(canales[indiceCanal].limMin);
  oled.print("-");
  oled.print(canales[indiceCanal].limMax);
  oled.print(")");

  oled.setTextSize(2);
  oled.setCursor(0, NAVBAR_H + 14);
  oled.print("POS:");
  oled.print(pos);

  oled.setCursor(0, NAVBAR_H + 34);
  oled.print("SEL:");
  oled.print(sel);

  oled.display();
}

void pantalla_auto15(int pos, bool ctrOk)
{
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  navbar(ctrOk);

  oled.setTextSize(1);
  oled.setCursor(15, NAVBAR_H + 2);
  oled.print("AUTO CANAL 15");

  oled.setTextSize(2);
  oled.setCursor(0, NAVBAR_H + 16);
  oled.print("POS:");
  oled.print(pos);

  oled.display();
}

void pantalla_config(int indiceCanal, bool ctrOk)
{
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  navbar(ctrOk);

  oled.setTextSize(1);
  oled.setCursor(0, NAVBAR_H + 2);
  oled.print(canales[indiceCanal].nombre);

  oled.setTextSize(2);
  oled.setCursor(0, NAVBAR_H + 14);
  oled.print("MIN:");
  oled.print(canales[indiceCanal].limMin);

  oled.setCursor(0, NAVBAR_H + 34);
  oled.print("MAX:");
  oled.print(canales[indiceCanal].limMax);

  oled.display();
}

void pantalla_debug(int indiceCanal, int pos, int sel, bool ctrOk, bool mostrarNumero, int delayMs)
{
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  navbar(ctrOk);

  // Fila 1: nombre o "CANAL X"
  oled.setTextSize(1);
  oled.setCursor(0, NAVBAR_H + 2);
  if(mostrarNumero)
  {
    oled.print("CANAL ");
    oled.print(indiceCanal);  // en este modo indiceCanal ES el numero de canal
  }
  else
  {
    oled.print(canales[indiceCanal].nombre);
    oled.print(" [CH");
    oled.print(canales[indiceCanal].numero);
    oled.print("]");
  }

  // Pos y Sel siempre visibles
  oled.setTextSize(2);
  oled.setCursor(0, NAVBAR_H + 14);
  oled.print("POS:");
  oled.print(pos);

  oled.setCursor(0, NAVBAR_H + 34);
  oled.print("SEL:");
  oled.print(sel);

  oled.setTextSize(1);
  oled.setCursor(0, NAVBAR_H + 52);
  oled.print("DLY:");
  oled.print(delayMs);
  oled.print("ms  L2- R2+");

  oled.display();
}

void pantalla_debug_auto(int pos, bool ctrOk)
{
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  navbar(ctrOk);

  oled.setTextSize(1);
  oled.setCursor(0, NAVBAR_H + 2);
  oled.print("AUTO CH15");

  oled.setTextSize(2);
  oled.setCursor(0, NAVBAR_H + 14);
  oled.print("POS:");
  oled.print(pos);

  oled.setTextSize(1);
  oled.setCursor(0, NAVBAR_H + 38);
  oled.print("[]=auto  O=detener");

  oled.display();
}

void pantalla_debug_select(int indiceCanal, bool ctrOk)
{
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  navbar(ctrOk);

  oled.setTextSize(1);
  oled.setCursor(0, NAVBAR_H + 2);
  oled.print("SELEC. CANAL:");

  // Lista de canales, el seleccionado resaltado
  for(int i = 0; i < NUM_CANALES; i++)
  {
    int y = NAVBAR_H + 14 + i * 9;
    if(y > 63) break;

    if(i == indiceCanal)
    {
      oled.fillRect(0, y - 1, 128, 9, SSD1306_WHITE);
      oled.setTextColor(SSD1306_BLACK);
    }
    else
    {
      oled.setTextColor(SSD1306_WHITE);
    }

    oled.setCursor(2, y);
    oled.print(canales[i].nombre);
    oled.print(" [CH");
    oled.print(canales[i].numero);
    oled.print("]");
  }

  oled.setTextColor(SSD1306_WHITE);
  oled.display();
}

void pantalla_homing(const char* nombre, int pos, int target, int paso, int total, bool ctrOk)
{
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  navbar(ctrOk);

  oled.setTextSize(1);
  oled.setCursor(0, NAVBAR_H + 2);
  oled.print("RESTAURANDO...");

  // Nombre del canal
  oled.setCursor(0, NAVBAR_H + 14);
  oled.print(nombre);

  // Posicion actual y objetivo
  oled.setTextSize(2);
  oled.setCursor(0, NAVBAR_H + 26);
  oled.print(pos);
  oled.setTextSize(1);
  oled.print(" -> ");
  oled.setTextSize(2);
  oled.print(target);

  // Barra de progreso
  int barW = 124;
  int barY = NAVBAR_H + 50;
  oled.drawRect(2, barY, barW, 8, SSD1306_WHITE);
  int fill = 0;
  if(total > 0)
    fill = map(paso, 0, total, 0, barW - 2);
  if(fill > 0)
    oled.fillRect(3, barY + 1, fill, 6, SSD1306_WHITE);

  oled.display();
}

void pantalla_ctrl_pc(bool ctrOk)
{
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  navbar(ctrOk);

  // Titulo
  oled.setTextSize(1);
  int tx = (128 - 12 * 6) / 2;
  oled.setCursor(tx, NAVBAR_H + 2);
  oled.print("-- CTRL PC --");

  // Posiciones de los 4 canales principales en dos columnas
  // Izquierda: BrzA (1), BrzB (2)   Derecha: RBrz (3), RRob (4)
  oled.setCursor(0,  NAVBAR_H + 14);
  oled.print("BrzA:");
  oled.print(posActual[1]);

  oled.setCursor(64, NAVBAR_H + 14);
  oled.print("BrzB:");
  oled.print(posActual[2]);

  oled.setCursor(0,  NAVBAR_H + 26);
  oled.print("RBrz:");
  oled.print(posActual[3]);

  oled.setCursor(64, NAVBAR_H + 26);
  oled.print("RRob:");
  oled.print(posActual[4]);

  // Garra en linea separada
  oled.setCursor(0,  NAVBAR_H + 38);
  oled.print("Garra:");
  oled.print(posActual[0]);

  oled.setCursor(0, NAVBAR_H + 52);
  oled.print("HOME=menu");

  oled.display();
}

void pantalla_analogico(bool ctrOk)
{
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  navbar(ctrOk);

  oled.setTextSize(1);

  oled.setCursor(0, NAVBAR_H + 2);
  oled.print("BrzA:");
  oled.print(posActual[1]);

  oled.setCursor(64, NAVBAR_H + 2);
  oled.print("BrzB:");
  oled.print(posActual[2]);

  oled.setCursor(0, NAVBAR_H + 14);
  oled.print("RBrz:");
  oled.print(posActual[3]);

  oled.setCursor(64, NAVBAR_H + 14);
  oled.print("RRob:");
  oled.print(posActual[4]);

  oled.setCursor(0, NAVBAR_H + 28);
  oled.print("LY=BrzA  LX=BrzB");
  oled.setCursor(0, NAVBAR_H + 38);
  oled.print("[]/O=RBrz L2/R2=RRob");

  oled.display();
}
