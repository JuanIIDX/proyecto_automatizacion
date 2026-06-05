#include <Wire.h>
#include <string.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_PWMServoDriver.h>
#include <Bluepad32.h>
#include <TM1637Display.h>

#include "config.h"
#include "servos.h"
#include "pantalla.h"

// Declarado aqui para que procesarComandoSerial (que aparece antes
// de las variables globales) pueda escribirlo sin error de scope.
// El loop() lo lee y aplica el cambio de modo.
int cmdModoPendiente = -1;

// Hardware
Adafruit_SSD1306        oled(128, 64, &Wire, -1);
TwoWire                 I2CPCA = TwoWire(1);
Adafruit_PWMServoDriver pca(0x40, I2CPCA);
TM1637Display           tm(18, 19);   // CLK=18, DIO=19

// =========================
// RELOJ TM1637
// =========================

#define RELOJ_NORMAL   0
#define RELOJ_EDIT     1
#define RELOJ_FELIZ    2
#define RELOJ_PAUSA    3

int           relojModo       = RELOJ_NORMAL;
bool          relojCorriendo  = false;
unsigned long relojInicio     = 0;
unsigned long relojPausadoMs  = 0;   // ms acumulados antes de pausa

// ── Segmentos custom ──────────────────────────────────────────
// TM1637 segmentos: A=bit0 B=bit1 C=bit2 D=bit3 E=bit4 F=bit5 G=bit6
//
//  _A_
// F   B
//  _G_
// E   C
//  _D_
//
// Guion: G                     = 0b01000000
// Cero:  A+B+C+D+E+F           = 0b00111111
// "n" feliz (U invertida baja): C+D+E = 0b00011100
//   se ve como arco hacia abajo en la mitad inferior del digit

static const uint8_t SEG_GUION = 0b01000000;  // -
static const uint8_t SEG_CERO  = 0b00111111;  // 0
static const uint8_t SEG_OJO_F = 0b00011100;  // n (arco feliz)

// Estado animacion edicion
unsigned long animEditUltimo = 0;
bool          animEditFase   = false;

// Estado animacion feliz
// Fase 0-5: parpadeo del tiempo (3 veces encendido/apagado)
// Fase 6+:  ojitos fijos
int           felizFase      = 0;
unsigned long felizUltimo    = 0;
// Guarda el tiempo final para mostrarlo durante el parpadeo
uint8_t       felizSegs[4]  = {0,0,0,0};

void relojIniciaNivel()
{
  relojModo      = RELOJ_NORMAL;
  relojCorriendo = true;
  relojInicio    = millis();
  relojPausadoMs = 0;
}

void relojFin()
{
  // Acumular el tiempo transcurrido antes de parar
  if(relojCorriendo)
    relojPausadoMs += millis() - relojInicio;
  relojCorriendo = false;
  relojModo      = RELOJ_FELIZ;
  felizFase      = 0;
  felizUltimo    = millis();
  // Guardar los segmentos del tiempo actual para el parpadeo
  unsigned long ms_total  = relojPausadoMs;
  unsigned long seg_total = ms_total / 1000;
  unsigned long ms_resto  = ms_total % 1000;
  int d0, d1, d2, d3;
  if(seg_total < 100)
  {
    d0 = (int)seg_total / 10; d1 = (int)seg_total % 10;
    d2 = (int)(ms_resto / 10) / 10; d3 = (int)(ms_resto / 10) % 10;
  }
  else
  {
    int mm = (int)min((unsigned long)99, seg_total / 60);
    int ss = (int)(seg_total % 60);
    d0 = mm/10; d1 = mm%10; d2 = ss/10; d3 = ss%10;
  }
  felizSegs[0] = tm.encodeDigit(d0);
  felizSegs[1] = tm.encodeDigit(d1) | 0x80;  // con puntos
  felizSegs[2] = tm.encodeDigit(d2);
  felizSegs[3] = tm.encodeDigit(d3);
}

void relojModoEdicion()
{
  relojCorriendo = false;
  relojModo      = RELOJ_EDIT;
  animEditFase   = false;
  animEditUltimo = 0;
}

void relojModoPausa()
{
  if(relojCorriendo)
    relojPausadoMs += millis() - relojInicio;
  relojCorriendo = false;
  relojModo      = RELOJ_PAUSA;
  animEditFase   = false;
  animEditUltimo = 0;
}

void tickReloj()
{
  // ── FELIZ ────────────────────────────────────────────────────
  if(relojModo == RELOJ_FELIZ)
  {
    unsigned long ahora = millis();
    if(felizFase < 6)
    {
      // Parpadea 3 veces: encendido 400ms / apagado 300ms
      unsigned long intervalo = (felizFase % 2 == 0) ? 400 : 300;
      if(ahora - felizUltimo >= intervalo)
      {
        felizUltimo = ahora;
        felizFase++;
      }
      // Par = encendido, impar = apagado
      if(felizFase % 2 == 0)
        tm.setSegments(felizSegs);
      else
      {
        uint8_t apagado[4] = {0,0,0,0};
        tm.setSegments(apagado);
      }
    }
    else
    {
      // Ojitos felices: n _ _ n  (sin puntos centrales)
      uint8_t segs[4] = { SEG_OJO_F, 0, 0, SEG_OJO_F };
      tm.setSegments(segs);
    }
    return;
  }

  // ── PAUSA ────────────────────────────────────────────────────
  if(relojModo == RELOJ_PAUSA)
  {
    unsigned long ahora = millis();
    if(ahora - animEditUltimo >= 600)
    {
      animEditUltimo = ahora;
      animEditFase   = !animEditFase;
    }
    uint8_t segs[4];
    // Alterna 0 _ _ 0  /  - _ _ -  (sin puntos)
    uint8_t izq = animEditFase ? SEG_CERO : SEG_GUION;
    segs[0] = izq; segs[1] = 0; segs[2] = 0; segs[3] = izq;
    tm.setSegments(segs);
    return;
  }

  // ── EDICION ──────────────────────────────────────────────────
  if(relojModo == RELOJ_EDIT)
  {
    unsigned long ahora = millis();
    if(ahora - animEditUltimo >= 600)
    {
      animEditUltimo = ahora;
      animEditFase   = !animEditFase;
    }
    uint8_t segs[4];
    if(animEditFase)
    {
      // 0 _ _ 0  (ojos abiertos en extremos, sin puntos)
      segs[0] = SEG_CERO;
      segs[1] = 0;
      segs[2] = 0;
      segs[3] = SEG_CERO;
    }
    else
    {
      // - _ _ -  (guion en extremos)
      segs[0] = SEG_GUION;
      segs[1] = 0;
      segs[2] = 0;
      segs[3] = SEG_GUION;
    }
    tm.setSegments(segs);
    return;
  }

  // Modo normal: temporizador
  unsigned long ms_total;
  if(relojCorriendo)
    ms_total = millis() - relojInicio + relojPausadoMs;
  else
    ms_total = relojPausadoMs;

  unsigned long seg_total = ms_total / 1000;
  unsigned long ms_resto  = ms_total % 1000;

  int d0, d1, d2, d3;

  if(seg_total < 100)
  {
    // SS:dd  (segundos : decimas*10, 00-99)
    int ss = (int)seg_total;
    int dd = (int)(ms_resto / 10);  // 0-99
    d0 = ss / 10;
    d1 = ss % 10;
    d2 = dd / 10;
    d3 = dd % 10;
  }
  else
  {
    // MM:SS
    int mm = (int)min((unsigned long)99, seg_total / 60);
    int ss = (int)(seg_total % 60);
    d0 = mm / 10;
    d1 = mm % 10;
    d2 = ss / 10;
    d3 = ss % 10;
  }

  uint8_t segs[4];
  segs[0] = tm.encodeDigit(d0);
  segs[1] = tm.encodeDigit(d1);
  segs[2] = tm.encodeDigit(d2);
  segs[3] = tm.encodeDigit(d3);
  // Encender los dos puntos centrales (bit 7 del segmento 1)
  segs[1] |= 0x80;
  tm.setSegments(segs);
}

// =========================
// PARSER DE COMANDOS SERIAL
// =========================
void procesarComandoSerial(const String& linea)
{
  if(!linea.startsWith("CMD:")) return;
  String cmd = linea.substring(4);
  cmd.trim();

  if(cmd == "NIVEL_START")         relojIniciaNivel();
  else if(cmd == "NIVEL_START_RESUME") {
    relojModo      = RELOJ_NORMAL;
    relojCorriendo = true;
    relojInicio    = millis();
  }
  else if(cmd == "NIVEL_END")      relojFin();
  else if(cmd == "EDIT")           relojModoEdicion();
  else if(cmd == "PAUSA")          relojModoPausa();
  else if(cmd == "MODO_CTRL_PC")     cmdModoPendiente = MODO_CTRL_PC;
  else if(cmd == "MODO_CTRL_PC_OFF") cmdModoPendiente = MODO_MENU;
  else if(cmd == "AGARRAR_CENTRO")   iniciarSecuenciaAgarrar();
  else if(cmd.startsWith("SET_MOTOR:"))
  {
    // Formato: SET_MOTOR:indice_canal:grados
    int p1 = cmd.indexOf(':', 10);
    if(p1 > 0)
    {
      int idx = cmd.substring(10, p1).toInt();
      int val = cmd.substring(p1 + 1).toInt();
      if(idx >= 0 && idx < NUM_CANALES)
      {
        posActual[idx] = constrain(val, canales[idx].limMin, canales[idx].limMax);
        selManual[idx] = posActual[idx];
        moverCanalCompleto(idx, posActual[idx]);
        Serial.print("DBG SET_MOTOR idx="); Serial.print(idx);
        Serial.print(" val="); Serial.print(val);
        Serial.print(" posActual="); Serial.println(posActual[idx]);
      }
    }
  }
}

// Gamepad
GamepadPtr myGamepad;

// Estado global
int  modo        = MODO_MENU;
int  menuSel     = 0;
int  indiceCanal = 0;
bool pcaOk       = false;


// Estado botones
bool triAnt   = false;
bool cirAnt   = false;
bool xAnt     = false;
bool cuadAnt  = false;
bool l1Ant    = false;
bool r1Ant    = false;
bool homeAnt  = false;
bool dpadUAnt = false;
bool dpadDAnt = false;
bool dpadRAnt = false;
bool dpadLAnt = false;

// Emergencia
volatile bool emergenciaFlag = false;

// =========================
// DUAL CORE
// =========================

SemaphoreHandle_t mutexOled;

// Datos que la tarea de pantalla necesita leer
// Se copian bajo mutex para evitar race conditions
struct EstadoPantalla
{
  int  modo;
  int  menuSel;
  int  indiceCanal;
  bool ctrOk;
  // debug
  int  debugModo;
  int  debugIdxPantalla;
  int  debugPos;
  int  debugSel;
  bool debugMostrarNumero;
  // analogico
  int  posActual[NUM_CANALES];
  // auto15
  int  posAuto15;
  int  debugDelay;
  // homing
  char homingNombre[20];
  int  homingPos;
  int  homingTarget;
  int  homingPaso;
  int  homingTotal;
};

EstadoPantalla snapPantalla;

// Tarea del Core 0 — dibuja la pantalla en loop continuo
// NO usa flags ni mutex para el dibujo — solo lee el snapshot
// El snapshot se escribe atomicamente desde Core 1
void tareaPantalla(void* param)
{
  // Dar tiempo a Core 1 para terminar setup() completamente
  vTaskDelay(pdMS_TO_TICKS(2000));

  for(;;)
  {
    // Copiar snapshot bajo mutex (operacion rapida, solo copia de struct)
    EstadoPantalla s;
    if(xSemaphoreTake(mutexOled, pdMS_TO_TICKS(5)) == pdTRUE)
    {
      s = snapPantalla;
      xSemaphoreGive(mutexOled);
    }
    else
    {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }

    // Dibujar segun modo
    switch(s.modo)
    {
      case MODO_MENU:
        pantalla_menu(s.menuSel);
        break;
      case MODO_CONTROL:
        pantalla_control(
          s.indiceCanal,
          s.posActual[s.indiceCanal],
          selManual[s.indiceCanal],
          s.ctrOk
        );
        break;
      case MODO_AUTO15:
        pantalla_auto15(s.posAuto15, s.ctrOk);
        break;
      case MODO_ANALOGICO:
        pantalla_analogico(s.ctrOk);
        break;
      case MODO_CONFIG:
        pantalla_config(s.indiceCanal, s.ctrOk);
        break;
      case MODO_DEBUG:
        if(s.debugModo == 1)
          pantalla_debug_auto(s.debugPos, s.ctrOk);
        else
          pantalla_debug(
            s.debugIdxPantalla,
            s.debugPos,
            s.debugSel,
            s.ctrOk,
            s.debugMostrarNumero,
            s.debugDelay
          );
        break;
      case MODO_HOMING:
        pantalla_homing(
          s.homingNombre,
          s.homingPos,
          s.homingTarget,
          s.homingPaso,
          s.homingTotal,
          s.ctrOk
        );
        break;
      case MODO_CTRL_PC:
        pantalla_ctrl_pc(s.ctrOk);
        break;
    }

    // ~15 FPS para la pantalla — suficiente y sin sobrecargar I2C
    vTaskDelay(pdMS_TO_TICKS(66));
  }
}

// Actualiza el snapshot y pide redibujo
void actualizarSnap()
{
  if(xSemaphoreTake(mutexOled, pdMS_TO_TICKS(10)))
  {
    snapPantalla.modo        = modo;
    snapPantalla.menuSel     = menuSel;
    snapPantalla.indiceCanal = indiceCanal;
    snapPantalla.ctrOk       = myGamepad && myGamepad->isConnected();
    snapPantalla.posAuto15   = posAuto15;
    for(int i = 0; i < NUM_CANALES; i++)
      snapPantalla.posActual[i] = posActual[i];
    xSemaphoreGive(mutexOled);
  }
}


// =========================

bool ctrOk()
{
  return myGamepad && myGamepad->isConnected();
}

bool chequearHome()
{
  if(!ctrOk()) return false;
  bool home = (myGamepad->miscButtons() & 0x01);
  if(home && !homeAnt)
  {
    homeAnt = home;
    modo = MODO_MENU;
    actualizarSnap();
    return true;
  }
  homeAnt = home;
  return false;
}

void onConnectedGamepad(GamepadPtr gp)
{
  myGamepad = gp;
  Serial.println("Control conectado");
  actualizarSnap();
}

void onDisconnectedGamepad(GamepadPtr gp)
{
  myGamepad = nullptr;
  Serial.println("Control desconectado");
  actualizarSnap();
}

// =========================
// MENU
// =========================

void loopMenu()
{
  BP32.update();

  if(!ctrOk())
  {
    actualizarSnap();
    return;
  }

  uint8_t dpad = myGamepad->dpad();
  uint16_t botones = myGamepad->buttons();

  bool dpadR = (dpad & 0x04);
  bool dpadL = (dpad & 0x08);
  bool x     = (botones & 0x0001);

  bool cambio = false;

  if(dpadR && !dpadRAnt) { if(menuSel < MENU_TOTAL - 1) menuSel++; cambio = true; }
  if(dpadL && !dpadLAnt) { if(menuSel > 0)              menuSel--; cambio = true; }

  if(x && !xAnt)
  {
    switch(menuSel)
    {
      case MENU_CONTROL:
        if(!ctrOk())
        {
          oled.clearDisplay();
          oled.setTextColor(SSD1306_WHITE);
          navbar(false);
          oled.setTextSize(1);
          oled.setCursor(5, NAVBAR_H + 8);
          oled.print("Sin control");
          oled.setCursor(5, NAVBAR_H + 20);
          oled.print("conectado");
          oled.display();
          delay(1500);
          cambio = true;
        }
        else
        {
          iniciarHoming(MODO_ANALOGICO);
          modo = MODO_HOMING;
          cambio = true;
        }
        break;

      case MENU_DEBUG:
        modo = MODO_DEBUG;
        cambio = true;
        break;

      case MENU_HOMING:
        iniciarHoming(MODO_MENU);
        modo = MODO_HOMING;
        cambio = true;
        break;

      case MENU_CTRL_PC:
        iniciarHoming(MODO_CTRL_PC);
        modo = MODO_HOMING;
        cambio = true;
        break;
    }
  }

  if(cambio) actualizarSnap();

  dpadRAnt = dpadR;
  dpadLAnt = dpadL;
  xAnt     = x;
}

// =========================
// CONTROL MANUAL
// =========================

void loopControl()
{
  BP32.update();

  bool ok = ctrOk();
  if(!ok) { actualizarSnap(); return; }

  uint16_t botones = myGamepad->buttons();
  uint8_t  dpad    = myGamepad->dpad();

  bool cir  = (botones & 0x0002);
  bool x    = (botones & 0x0001);
  bool cuad = (botones & 0x0004);
  bool l1   = (botones & 0x0010);
  bool r1   = (botones & 0x0020);

  bool dpadU = (dpad & 0x01);
  bool dpadD = (dpad & 0x02);
  bool dpadR = (dpad & 0x04);
  bool dpadL = (dpad & 0x08);

  int limMin = canales[indiceCanal].limMin;
  int limMax = canales[indiceCanal].limMax;

  if(chequearHome()) return;

  bool cambio = false;

  if(l1 && !l1Ant)
  {
    indiceCanal--;
    if(indiceCanal < 0) indiceCanal = NUM_CANALES - 2;
    cambio = true;
  }

  if(r1 && !r1Ant)
  {
    indiceCanal++;
    if(indiceCanal >= NUM_CANALES - 1) indiceCanal = 0;
    cambio = true;
  }

  if(dpadU && !dpadUAnt) { selManual[indiceCanal] = min(selManual[indiceCanal] + 1,  limMax); cambio = true; }
  if(dpadD && !dpadDAnt) { selManual[indiceCanal] = max(selManual[indiceCanal] - 1,  limMin); cambio = true; }
  if(dpadR && !dpadRAnt) { selManual[indiceCanal] = min(selManual[indiceCanal] + 10, limMax); cambio = true; }
  if(dpadL && !dpadLAnt) { selManual[indiceCanal] = max(selManual[indiceCanal] - 10, limMin); cambio = true; }

  if(x && !xAnt)
  {
    posActual[indiceCanal] = selManual[indiceCanal];
    moverCanalCompleto(indiceCanal, posActual[indiceCanal]);
    cambio = true;
  }

  if(cambio) actualizarSnap();

  triAnt   = false;
  cirAnt   = cir;
  xAnt     = x;
  cuadAnt  = cuad;
  l1Ant    = l1;
  r1Ant    = r1;
  dpadUAnt = dpadU;
  dpadDAnt = dpadD;
  dpadRAnt = dpadR;
  dpadLAnt = dpadL;

  delay(10);
}

// =========================
// AUTO CANAL 15
// =========================

void loopAuto15()
{
  BP32.update();
  chequearHome();

  int posAntes = posAuto15;
  tickAuto15();

  if(posAuto15 != posAntes)
    actualizarSnap();
}

// =========================
// CONFIG LIMITES
// =========================

void loopConfig()
{
  BP32.update();
  if(!ctrOk()) return;

  uint16_t botones = myGamepad->buttons();
  uint8_t  dpad    = myGamepad->dpad();

  bool l1   = (botones & 0x0010);
  bool r1   = (botones & 0x0020);

  bool dpadU = (dpad & 0x01);
  bool dpadD = (dpad & 0x02);
  bool dpadR = (dpad & 0x04);
  bool dpadL = (dpad & 0x08);

  if(chequearHome()) return;

  bool cambio = false;

  if(l1 && !l1Ant) { indiceCanal = (indiceCanal - 1 + NUM_CANALES - 1) % (NUM_CANALES - 1); cambio = true; }
  if(r1 && !r1Ant) { indiceCanal = (indiceCanal + 1) % (NUM_CANALES - 1);                   cambio = true; }

  if(dpadU && !dpadUAnt)
  {
    canales[indiceCanal].limMax = min(canales[indiceCanal].limMax + 1, 180);
    cambio = true;
  }
  if(dpadD && !dpadDAnt)
  {
    canales[indiceCanal].limMax = max(canales[indiceCanal].limMax - 1, canales[indiceCanal].limMin + 1);
    cambio = true;
  }
  if(dpadR && !dpadRAnt)
  {
    canales[indiceCanal].limMin = min(canales[indiceCanal].limMin + 1, canales[indiceCanal].limMax - 1);
    cambio = true;
  }
  if(dpadL && !dpadLAnt)
  {
    canales[indiceCanal].limMin = max(canales[indiceCanal].limMin - 1, 0);
    cambio = true;
  }

  if(cambio) actualizarSnap();

  l1Ant    = l1;
  r1Ant    = r1;
  dpadUAnt = dpadU;
  dpadDAnt = dpadD;
  dpadRAnt = dpadR;
  dpadLAnt = dpadL;

  delay(10);
}

// =========================
// DEBUG
// =========================

#define DEBUG_CANALES 0
#define DEBUG_AUTO    1

int  debugModo          = DEBUG_CANALES;
int  debugCanal         = 0;
int  debugCanalRaw      = 0;
int  debugSel           = 90;
int  debugPos           = 90;
bool debugMostrarNumero = false;

int   debugFase         = 0;
unsigned long debugUltimoPaso = 0;
int   debugDelay        = 20;  // ms entre comandos al servo

void actualizarSnapDebug()
{
  if(xSemaphoreTake(mutexOled, pdMS_TO_TICKS(10)))
  {
    snapPantalla.modo               = modo;
    snapPantalla.ctrOk              = ctrOk();
    snapPantalla.debugModo          = debugModo;
    snapPantalla.debugIdxPantalla   = debugMostrarNumero ? debugCanalRaw : debugCanal;
    snapPantalla.debugPos           = debugPos;
    snapPantalla.debugSel           = debugSel;
    snapPantalla.debugMostrarNumero = debugMostrarNumero;
    snapPantalla.debugDelay         = debugDelay;
    xSemaphoreGive(mutexOled);
  }
}


void loopDebug()
{
  BP32.update();
  bool ok = ctrOk();

  if(chequearHome())
  {
    debugModo          = DEBUG_CANALES;
    debugCanal         = 0;
    debugSel           = 90;
    debugMostrarNumero = false;
    return;
  }

  if(debugModo == DEBUG_AUTO)
  {
    if(ok)
    {
      uint16_t botones = myGamepad->buttons();
      bool cir = (botones & 0x0002);

      if(cir && !cirAnt)
      {
        pca.setPWM(15, 0, 0);
        debugModo = DEBUG_CANALES;
        actualizarSnapDebug();
      }
      cirAnt = cir;
    }

    unsigned long ahora = millis();
    if(ahora - debugUltimoPaso >= INTERVALO_AUTO)
    {
      debugUltimoPaso = ahora;
      int posAntes = debugPos;

      if(debugFase == 0) { debugPos++; if(debugPos >= 180) { debugPos = 180; debugFase = 1; debugUltimoPaso = ahora + 500; } }
      else if(debugFase == 1) { debugPos--; if(debugPos <= 90)  { debugPos = 90;  debugFase = 2; debugUltimoPaso = ahora + 300; } }
      else if(debugFase == 2) { debugPos--; if(debugPos <= 0)   { debugPos = 0;   debugFase = 3; debugUltimoPaso = ahora + 500; } }
      else if(debugFase == 3) { debugPos++; if(debugPos >= 90)  { debugPos = 90;  debugFase = 0; debugUltimoPaso = ahora + 300; } }

      pca.setPWM(15, 0, angleToPulse(debugPos));

      if(debugPos != posAntes)
        actualizarSnapDebug();
    }
    return;
  }

  if(!ok) { actualizarSnapDebug(); return; }

  uint16_t botones = myGamepad->buttons();
  uint8_t  dpad    = myGamepad->dpad();

  bool x    = (botones & 0x0001);
  bool cir  = (botones & 0x0002);
  bool cuad = (botones & 0x0004);
  bool tri  = (botones & 0x0008);
  bool l1   = (botones & 0x0010);
  bool r1   = (botones & 0x0020);

  bool dpadU = (dpad & 0x01);
  bool dpadD = (dpad & 0x02);
  bool dpadR = (dpad & 0x04);
  bool dpadL = (dpad & 0x08);

  int l2val = myGamepad->brake();
  int r2val = myGamepad->throttle();

  bool cambio = false;

  // L2 = bajar delay (mas rapido), R2 = subir delay (mas lento)
  static unsigned long ultimoAjusteDelay = 0;
  if(millis() - ultimoAjusteDelay > 200)
  {
    if(l2val > 50)
    {
      debugDelay = max(5, debugDelay - 5);
      ultimoAjusteDelay = millis();
      cambio = true;
      Serial.print("debugDelay: "); Serial.println(debugDelay);
    }
    else if(r2val > 50)
    {
      debugDelay = min(200, debugDelay + 5);
      ultimoAjusteDelay = millis();
      cambio = true;
      Serial.print("debugDelay: "); Serial.println(debugDelay);
    }
  }

  if(l1 && !l1Ant)
  {
    if(debugMostrarNumero) { debugCanalRaw = (debugCanalRaw - 1 + 16) % 16; }
    else                   { debugCanal    = (debugCanal - 1 + NUM_CANALES) % NUM_CANALES; }
    debugSel = debugPos;
    cambio = true;
  }

  if(r1 && !r1Ant)
  {
    if(debugMostrarNumero) { debugCanalRaw = (debugCanalRaw + 1) % 16; }
    else                   { debugCanal    = (debugCanal + 1) % NUM_CANALES; }
    debugSel = debugPos;
    cambio = true;
  }

  int lx = myGamepad->axisX();
  if(abs(lx) > DEADZONE)
  {
    int paso = map(abs(lx), DEADZONE, 512, 1, 4);
    debugSel = constrain(debugSel + (lx > 0 ? paso : -paso), 0, 180);
    cambio = true;
  }

  if(dpadR && !dpadRAnt) { debugSel = constrain(debugSel + 10, 0, 180); cambio = true; }
  if(dpadL && !dpadLAnt) { debugSel = constrain(debugSel - 10, 0, 180); cambio = true; }
  if(dpadU && !dpadUAnt) { debugSel = constrain(debugSel + 1,  0, 180); cambio = true; }
  if(dpadD && !dpadDAnt) { debugSel = constrain(debugSel - 1,  0, 180); cambio = true; }

  int canalFisico = debugMostrarNumero ? debugCanalRaw : canales[debugCanal].numero;

  if(x && !xAnt)
  {
    debugPos = debugSel;
    pca.setPWM(canalFisico, 0, angleToPulse(debugPos));
    cambio = true;
  }

  if(cir && !cirAnt)
  {
    pca.setPWM(canalFisico, 0, 0);
    cambio = true;
  }

  if(cuad && !cuadAnt)
  {
    debugModo = DEBUG_AUTO;
    debugPos  = 90;
    debugFase = 0;
    debugUltimoPaso = millis();
    cambio = true;
  }

  if(tri && !triAnt)
  {
    debugMostrarNumero = !debugMostrarNumero;
    debugCanalRaw = debugMostrarNumero ? canales[debugCanal].numero : 0;
    cambio = true;
  }

  if(cambio) actualizarSnapDebug();

  xAnt     = x;
  cirAnt   = cir;
  cuadAnt  = cuad;
  triAnt   = tri;
  l1Ant    = l1;
  r1Ant    = r1;
  dpadUAnt = dpadU;
  dpadDAnt = dpadD;
  dpadRAnt = dpadR;
  dpadLAnt = dpadL;

  delay(debugDelay);
}

// =========================
// HOMING — restauracion lenta al entrar en Control
// =========================

// Secuencia: { indice_canal, target }
struct HomingPaso { int indice; int target; const char* nombre; unsigned long intervalo; };
static const HomingPaso HOMING_SEQ[] = {
  { 4, 180, "Rotacion Robot", HOMING_INTERVALO_LENTO  },
  { 2, 100, "Brazo B",        HOMING_INTERVALO_NORMAL },
  { 1,  90, "Brazo A",        HOMING_INTERVALO_NORMAL },
};
static const int HOMING_TOTAL = 3;

int  homingPasoActual      = 0;
unsigned long homingUltimo = 0;
int  homingDistInicial[HOMING_TOTAL] = {0, 0, 0};
int  homingModoDest        = MODO_MENU;  // modo al que se va al terminar homing

void resetearBotones()
{
  triAnt   = false;
  cirAnt   = false;
  xAnt     = false;
  cuadAnt  = false;
  l1Ant    = false;
  r1Ant    = false;
  homeAnt  = false;
  dpadUAnt = false;
  dpadDAnt = false;
  dpadRAnt = false;
  dpadLAnt = false;
}

void iniciarHoming(int modoDest)
{
  homingPasoActual  = 0;
  homingUltimo      = 0;
  homingModoDest    = modoDest;
  for(int i = 0; i < HOMING_TOTAL; i++)
    homingDistInicial[i] = 0;
}

void actualizarSnapHoming(const char* nombre, int pos, int target, int paso, int total)
{
  if(xSemaphoreTake(mutexOled, pdMS_TO_TICKS(10)))
  {
    snapPantalla.modo        = MODO_HOMING;
    snapPantalla.ctrOk       = ctrOk();
    strncpy(snapPantalla.homingNombre, nombre, sizeof(snapPantalla.homingNombre) - 1);
    snapPantalla.homingNombre[sizeof(snapPantalla.homingNombre) - 1] = '\0';
    snapPantalla.homingPos    = pos;
    snapPantalla.homingTarget = target;
    snapPantalla.homingPaso   = paso;
    snapPantalla.homingTotal  = total;
    xSemaphoreGive(mutexOled);
  }
}


// Devuelve true cuando termino toda la secuencia
bool tickHoming()
{
  if(homingPasoActual >= HOMING_TOTAL)
    return true;

  unsigned long ahora = millis();
  if(ahora - homingUltimo < HOMING_SEQ[homingPasoActual].intervalo)
    return false;
  homingUltimo = ahora;

  const HomingPaso& p = HOMING_SEQ[homingPasoActual];
  int idx    = p.indice;
  int target = p.target;
  int actual = posActual[idx];

  // Guardar distancia inicial la primera vez (incluye si ya esta en target)
  if(homingDistInicial[homingPasoActual] == 0)
  {
    // Si ya esta en el target, forzar igualmente el PWM durante al menos 20 ticks
    // para asegurar que el servo fisico llegue ahi
    homingDistInicial[homingPasoActual] = max(abs(target - actual), 20);
    // Enviar posicion target de inmediato para que el servo empiece a moverse
    moverCanalCompleto(idx, actual);
  }

  // Mover un paso hacia el target
  if(actual < target)       actual++;
  else if(actual > target)  actual--;

  posActual[idx] = actual;
  selManual[idx] = actual;
  moverCanalCompleto(idx, actual);

  int distInicial = homingDistInicial[homingPasoActual];
  int paso        = distInicial - abs(target - actual);

  actualizarSnapHoming(p.nombre, actual, target, paso, distInicial);

  if(actual == target)
  {
    homingDistInicial[homingPasoActual] = 0;
    homingPasoActual++;
  }

  return (homingPasoActual >= HOMING_TOTAL);
}

void loopHoming()
{
  BP32.update();

  // El boton Home cancela el homing y vuelve al menu
  if(chequearHome())
  {
    resetearBotones();
    return;
  }

  if(tickHoming())
  {
    resetearBotones();
    modo = homingModoDest;
    actualizarSnap();
  }
}

// =========================
// MODO CTRL PC
// =========================

// Garra: 70 grados = ABIERTA  /  110 grados = CERRADA

// ── Secuencia "Agarrar centro" ────────────────────────────────
// Cada paso: { indice_canal, grados_objetivo, delay_antes_del_siguiente_ms }
struct PasoSecuencia { int indice; int grados; unsigned long espera; };

static const PasoSecuencia SEQ_AGARRAR[] = {
  { 4,  90,  900 },   // 1. Rotacion  → 90°
  { 1, 160,  900 },   // 2. BrazoA    → 160°
  { 2,  25,  900 },   // 3. BrazoB    → 25°
  { 0,  70,  700 },   // 4. Garra     → 70° (abierta)
  { 1, 129,  900 },   // 5. BrazoA    → 129°
  { 0, 110,    0 },   // 6. Garra     → 110° (cerrada, ultimo)
};
static const int SEQ_AGARRAR_TOTAL = 6;

int           seqPaso        = -1;   // -1 = inactivo
unsigned long seqProximoMs   = 0;

void tickSecuencia()
{
  if(seqPaso < 0 || seqPaso >= SEQ_AGARRAR_TOTAL) return;
  if(millis() < seqProximoMs) return;

  const PasoSecuencia& p = SEQ_AGARRAR[seqPaso];
  posActual[p.indice] = constrain(p.grados,
                                   canales[p.indice].limMin,
                                   canales[p.indice].limMax);
  selManual[p.indice] = posActual[p.indice];
  moverCanalCompleto(p.indice, posActual[p.indice]);
  actualizarSnap();

  seqProximoMs = millis() + p.espera;
  seqPaso++;
  if(seqPaso >= SEQ_AGARRAR_TOTAL) seqPaso = -1;
}

void iniciarSecuenciaAgarrar()
{
  seqPaso      = 0;
  seqProximoMs = millis();   // primer paso inmediato
}

void loopCtrlPC()
{
  BP32.update();
  if(chequearHome()) { seqPaso = -1; return; }
  actualizarSnap();
}

// =========================
// CONTROL ANALOGICO
// =========================

// Swap de analogicos (Share): false=izq→B/der→A, true=izq→A/der→B
bool analogoSwap    = false;
// Modo eje Brazo A: false=vertical(Y), true=horizontal(X) — Start para alternar
bool brazoAEjeX     = false;

void moverConVelocidad(int indice, int eje)
{
  if(abs(eje) <= DEADZONE) return;

  int paso = map(abs(eje), DEADZONE, 512, 1, 2);

  posActual[indice] = constrain(
    posActual[indice] + (eje > 0 ? paso : -paso),
    canales[indice].limMin,
    canales[indice].limMax
  );
  moverCanalCompleto(indice, posActual[indice]);
}

void loopAnalogico()
{
  static unsigned long ultimoTickAnalogico = 0;
  if(millis() - ultimoTickAnalogico < 20) return;
  ultimoTickAnalogico = millis();

  BP32.update();

  bool ok = ctrOk();
  if(!ok) { actualizarSnap(); return; }

  if(chequearHome()) return;

  uint16_t botones = myGamepad->buttons();
  uint8_t  misc    = myGamepad->miscButtons();

  bool l1    = (botones & 0x0010);
  bool r1    = (botones & 0x0020);
  bool share = (misc    & 0x0002);
  bool start = (misc    & 0x0004);   // Start / Options

  // Ejes de los dos analogicos
  int lx = myGamepad->axisX();   // izquierdo horizontal
  int ly = myGamepad->axisY();   // izquierdo vertical
  int rx = myGamepad->axisRX();  // derecho horizontal
  int ry = myGamepad->axisRY();  // derecho vertical
  int l2 = myGamepad->brake();
  int r2 = myGamepad->throttle();

  bool cambio = false;

  // Share = intercambiar cual analogico controla A y cual controla B
  if(share && !cirAnt)
  {
    analogoSwap = !analogoSwap;
    cambio = true;
  }
  cirAnt = share;

  // Start = alternar eje del Brazo A entre vertical(Y) y horizontal(X)
  static bool startAnt = false;
  if(start && !startAnt)
  {
    brazoAEjeX = !brazoAEjeX;
    cambio = true;
  }
  startAnt = start;

  // Garra L2/R2 (indice 0)
  if(l2 > 50)
  {
    posActual[0] = constrain(posActual[0] - map(l2, 50, 1023, 1, 4), canales[0].limMin, canales[0].limMax);
    moverCanalCompleto(0, posActual[0]);
    cambio = true;
  }
  else if(r2 > 50)
  {
    posActual[0] = constrain(posActual[0] + map(r2, 50, 1023, 1, 4), canales[0].limMin, canales[0].limMax);
    moverCanalCompleto(0, posActual[0]);
    cambio = true;
  }

  // Brazo A (indice 1): siempre eje Y — arriba/abajo
  // Brazo B (indice 2): siempre eje X — izquierda/derecha
  // Sin swap: analogo izquierdo → BrazoB(lx), analogo derecho → BrazoA(ry)
  // Con swap: analogo izquierdo → BrazoA(ly), analogo derecho → BrazoB(rx)
  // Analogo asignado a A: izquierdo si swap, derecho si no
  // Eje de A: Y invertido por defecto, X si brazoAEjeX
  // Analogo asignado a B: derecho si swap, izquierdo si no — siempre eje X
  int ejeA_raw, ejeB;
  if(analogoSwap) { ejeA_raw = brazoAEjeX ? lx : -ly;  ejeB = rx; }
  else            { ejeA_raw = brazoAEjeX ? rx : -ry;  ejeB = lx; }

  if(abs(ejeA_raw) > DEADZONE)
  {
    moverConVelocidad(1, ejeA_raw);  // BrazoA
    cambio = true;
  }
  if(abs(ejeB) > DEADZONE)
  {
    moverConVelocidad(2, ejeB);  // BrazoB
    cambio = true;
  }

  // L1/R1 = Rotacion-Robot (indice 4)
  static unsigned long ultimoRotRobot = 0;
  if(millis() - ultimoRotRobot >= 28)
  {
    if(l1)
    {
      posActual[4] = constrain(posActual[4] - 1, canales[4].limMin, canales[4].limMax);
      moverCanalCompleto(4, posActual[4]);
      ultimoRotRobot = millis();
      cambio = true;
    }
    else if(r1)
    {
      posActual[4] = constrain(posActual[4] + 1, canales[4].limMin, canales[4].limMax);
      moverCanalCompleto(4, posActual[4]);
      ultimoRotRobot = millis();
      cambio = true;
    }
  }

  if(cambio) actualizarSnap();
}

// =========================

void IRAM_ATTR emergenciaISR()
{
  emergenciaFlag = true;
}

void apagarTodosMotores()
{
  for(int i = 0; i < NUM_CANALES; i++)
  {
    pca.setPWM(canales[i].numero, 0, 0);
    if(canales[i].numeroB != -1)
      pca.setPWM(canales[i].numeroB, 0, 0);
    pwmActivo[i] = false;
  }
}

// =========================

void setup()
{
  Serial.begin(115200);
  pinMode(0, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(0), emergenciaISR, FALLING);
  delay(1000);

  // Crear mutex ANTES de lanzar la tarea
  mutexOled = xSemaphoreCreateMutex();

  // Inicializar todo el hardware primero
  Wire.begin(4, 5);

  // Escanear I2C bus 0 (OLED)
  Serial.println("=== SCAN I2C BUS 0 (SDA=4 SCL=5) ===");
  for(uint8_t addr = 1; addr < 127; addr++)
  {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();
    if(err == 0)
    {
      Serial.print("  Encontrado en 0x");
      if(addr < 16) Serial.print("0");
      Serial.println(addr, HEX);
    }
  }
  Serial.println("=== FIN SCAN BUS 0 ===");

  pantalla_init();
  Serial.println("pantalla_init() completado");

  tm.setBrightness(5);
  tm.clear();
  relojModoPausa();   // parpadea al inicio hasta que Python envie NIVEL_START_RESUME

  I2CPCA.begin(16, 17);

  // Escanear I2C bus 1 (PCA9685)
  Serial.println("=== SCAN I2C BUS 1 (SDA=16 SCL=17) ===");
  for(uint8_t addr = 1; addr < 127; addr++)
  {
    I2CPCA.beginTransmission(addr);
    uint8_t err = I2CPCA.endTransmission();
    if(err == 0)
    {
      Serial.print("  Encontrado en 0x");
      if(addr < 16) Serial.print("0");
      Serial.println(addr, HEX);
    }
  }
  Serial.println("=== FIN SCAN BUS 1 ===");

  pca.begin();
  pca.setPWMFreq(50);

  I2CPCA.beginTransmission(0x40);
  pcaOk = (I2CPCA.endTransmission() == 0);
  Serial.print("PCA9685 ok: "); Serial.println(pcaOk);

  servos_init();

  // Crear mutex
  mutexOled = xSemaphoreCreateMutex();

  // Inicializar snapshot
  snapPantalla.modo        = MODO_MENU;
  snapPantalla.menuSel     = 0;
  snapPantalla.ctrOk       = false;
  snapPantalla.posAuto15   = 90;
  snapPantalla.debugModo   = 0;
  snapPantalla.debugPos    = 90;
  snapPantalla.debugSel    = 90;
  for(int i = 0; i < NUM_CANALES; i++)
    snapPantalla.posActual[i] = 90;

  BP32.setup(
    &onConnectedGamepad,
    &onDisconnectedGamepad
  );

  // Snapshot inicial
  actualizarSnap();

  // Lanzar tarea de pantalla en Core 0
  // Todo el hardware ya esta inicializado — la tarea espera 2s de seguridad
  xTaskCreatePinnedToCore(
    tareaPantalla,
    "Pantalla",
    4096,
    NULL,
    1,
    NULL,
    0
  );
}

// =========================

void loop()
{
  // Aplicar cambio de modo pedido desde serial
  if(cmdModoPendiente >= 0)
  {
    int dest = cmdModoPendiente;
    cmdModoPendiente = -1;
    if(dest == MODO_CTRL_PC)
    {
      // Homing antes de entrar a Ctrl PC, igual que desde el menu fisico
      iniciarHoming(MODO_CTRL_PC);
      modo = MODO_HOMING;
    }
    else
    {
      modo = dest;
    }
    actualizarSnap();
  }

  // Leer comandos del PC — no bloqueante, caracter a caracter
  static String bufSerial = "";
  while(Serial.available())
  {
    char c = (char)Serial.read();
    if(c == '\n')
    {
      bufSerial.trim();
      if(bufSerial.length() > 0)
        procesarComandoSerial(bufSerial);
      bufSerial = "";
    }
    else if(c != '\r')
    {
      bufSerial += c;
      if(bufSerial.length() > 64)  // evitar desbordamiento
        bufSerial = "";
    }
  }

  // Tick del reloj TM1637 — cada 100ms es suficiente
  static unsigned long ultimoTickReloj = 0;
  if(millis() - ultimoTickReloj >= 100)
  {
    ultimoTickReloj = millis();
    tickReloj();
  }

  if(emergenciaFlag)
  {
    emergenciaFlag = false;
    apagarTodosMotores();
    Serial.println("EMERGENCIA: motores apagados");
  }

  // Secuencia no bloqueante — corre en cualquier modo
  tickSecuencia();

  switch(modo)
  {
    case MODO_MENU:      loopMenu();      break;
    case MODO_CONTROL:   loopControl();   break;
    case MODO_AUTO15:    loopAuto15();    break;
    case MODO_ANALOGICO: loopAnalogico(); break;
    case MODO_CONFIG:    loopConfig();    break;
    case MODO_DEBUG:     loopDebug();     break;
    case MODO_HOMING:    loopHoming();    break;
    case MODO_CTRL_PC:   loopCtrlPC();    break;
  }

  // Canal 15 siempre girando
  tickAuto15();

  verificarTimeoutPWM();

  // Enviar datos al PC cada 100ms
  static unsigned long ultimoEnvio = 0;
  if(millis() - ultimoEnvio >= 100)
  {
    ultimoEnvio = millis();

    // Angulos
    Serial.print("ANGULOS:");
    Serial.print(posActual[0]); Serial.print(",");
    Serial.print(posActual[1]); Serial.print(",");
    Serial.print(posActual[2]); Serial.print(",");
    Serial.print(posActual[3]); Serial.print(",");
    Serial.print(posActual[4]); Serial.print(",");
    Serial.println(posAuto15);

    // Sensores IR — orden remapeado segun posicion fisica:
    // IR1=Verde(GPIO33), IR2=Amarillo(GPIO32), IR3=Rojo(GPIO35), IR4=Azul(GPIO34)
    Serial.print("IR:");
    Serial.print(analogRead(33)); Serial.print(",");
    Serial.print(analogRead(32)); Serial.print(",");
    Serial.print(analogRead(35)); Serial.print(",");
    Serial.println(analogRead(34));

    // Sensor MQ-3 alcohol (GPIO25)
    Serial.print("MQ3:");
    Serial.println(analogRead(25));

    // Temperatura interna del ESP32
    float tempC = temperatureRead();
    Serial.print("TEMP:");
    Serial.println(tempC, 1);
  }
}
