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

  // Icono control derecha
  dibujarIconoControl(119, 2, ctrConectado);
}

// =========================
// PANTALLAS
// =========================

void pantalla_menu(int seleccion)
{
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);

  navbar(true);

  // 4 cuadros en grilla 2x2
  // Cada cuadro: 60x24 px, margen 2px
  // Fila 0: y = NAVBAR_H + 2
  // Fila 1: y = NAVBAR_H + 2 + 26

  const char* titulos[MENU_TOTAL] = {
    "Programa",
    "Juego",
    "Control",
    "Debug"
  };

  const char* subtitulos[MENU_TOTAL] = {
    "En desarrollo",
    "En desarrollo",
    "Robot",
    "Pruebas"
  };

  for(int i = 0; i < MENU_TOTAL; i++)
  {
    int col = i % 2;
    int row = i / 2;

    int x = 2 + col * 63;
    int y = NAVBAR_H + 2 + row * 26;
    int w = 60;
    int h = 24;

    // Borde: relleno si seleccionado, solo borde si no
    if(i == seleccion)
      oled.fillRect(x, y, w, h, SSD1306_WHITE);
    else
      oled.drawRect(x, y, w, h, SSD1306_WHITE);

    // Texto: invertido si seleccionado
    oled.setTextColor(i == seleccion ? SSD1306_BLACK : SSD1306_WHITE);

    oled.setTextSize(1);
    oled.setCursor(x + 3, y + 4);
    oled.print(titulos[i]);

    oled.setTextSize(1);
    oled.setCursor(x + 3, y + 14);
    oled.print(subtitulos[i]);
  }

  oled.setTextColor(SSD1306_WHITE);
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

void pantalla_debug(int indiceCanal, int pos, int sel, bool ctrOk, bool mostrarNumero)
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
  oled.print("LX=BrzA  RX=BrzB");
  oled.setCursor(0, NAVBAR_H + 38);
  oled.print("[]/O=RBrz L2/R2=RRob");

  oled.display();
}
