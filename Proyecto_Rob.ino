#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_PWMServoDriver.h>
#include <Bluepad32.h>

#include "config.h"
#include "servos.h"
#include "pantalla.h"

// Hardware
Adafruit_SSD1306     oled(128, 64, &Wire, -1);
TwoWire              I2CPCA = TwoWire(1);
Adafruit_PWMServoDriver pca(0x40, I2CPCA);

// Gamepad
GamepadPtr myGamepad;

// Estado global
int  modo       = MODO_MENU;
int  menuSel    = 0;
int  indiceCanal = 0;
bool pcaOk      = false;

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
    pantalla_menu(menuSel);
    return true;
  }
  homeAnt = home;
  return false;
}

void onConnectedGamepad(GamepadPtr gp)
{
  myGamepad = gp;
  Serial.println("Control conectado");
}

void onDisconnectedGamepad(GamepadPtr gp)
{
  myGamepad = nullptr;
  Serial.println("Control desconectado");
}

// =========================
// MENU
// =========================

void loopMenu()
{
  BP32.update();

  // Navegacion con dpad (funciona aunque el control no este conectado
  // solo cuando si esta conectado)
  if(!ctrOk())
  {
    pantalla_menu(menuSel);
    return;
  }

  uint16_t botones = myGamepad->buttons();
  uint8_t  dpad    = myGamepad->dpad();

  bool dpadU = (dpad & 0x01);
  bool dpadD = (dpad & 0x02);
  bool dpadR = (dpad & 0x04);
  bool dpadL = (dpad & 0x08);
  bool x     = (botones & 0x0001);

  // Grilla 2x2: izq/der cambia columna, arriba/abajo cambia fila
  if(dpadR && !dpadRAnt)
  {
    if(menuSel % 2 == 0) menuSel++;
    pantalla_menu(menuSel);
  }

  if(dpadL && !dpadLAnt)
  {
    if(menuSel % 2 == 1) menuSel--;
    pantalla_menu(menuSel);
  }

  if(dpadD && !dpadDAnt)
  {
    if(menuSel < 2) menuSel += 2;
    pantalla_menu(menuSel);
  }

  if(dpadU && !dpadUAnt)
  {
    if(menuSel >= 2) menuSel -= 2;
    pantalla_menu(menuSel);
  }

  if(x && !xAnt)
  {
    switch(menuSel)
    {
      case MENU_PROGRAMA:
      case MENU_JUEGO:
        // En desarrollo — no hace nada todavia
        break;

      case MENU_CONTROL:
        if(!ctrOk())
        {
          // Aviso: no hay control conectado
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
          pantalla_menu(menuSel);
        }
        else
        {
          modo = MODO_ANALOGICO;
        }
        break;

      case MENU_DEBUG:
        modo = MODO_DEBUG;
        break;
    }
  }

  dpadUAnt = dpadU;
  dpadDAnt = dpadD;
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

  if(!ok)
  {
    pantalla_control(indiceCanal, posActual[indiceCanal], selManual[indiceCanal], false);
    return;
  }

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

  // L1/R1 = cambiar canal
  if(l1 && !l1Ant)
  {
    indiceCanal--;
    // Saltar el canal 15 (auto)
    if(indiceCanal < 0) indiceCanal = NUM_CANALES - 2;
    pantalla_control(indiceCanal, posActual[indiceCanal], selManual[indiceCanal], ok);
  }

  if(r1 && !r1Ant)
  {
    indiceCanal++;
    if(indiceCanal >= NUM_CANALES - 1) indiceCanal = 0;
    pantalla_control(indiceCanal, posActual[indiceCanal], selManual[indiceCanal], ok);
  }

  // Dpad: cambia seleccion
  if(dpadU && !dpadUAnt)
  {
    selManual[indiceCanal]++;
    if(selManual[indiceCanal] > limMax) selManual[indiceCanal] = limMax;
    pantalla_control(indiceCanal, posActual[indiceCanal], selManual[indiceCanal], ok);
  }

  if(dpadD && !dpadDAnt)
  {
    selManual[indiceCanal]--;
    if(selManual[indiceCanal] < limMin) selManual[indiceCanal] = limMin;
    pantalla_control(indiceCanal, posActual[indiceCanal], selManual[indiceCanal], ok);
  }

  if(dpadR && !dpadRAnt)
  {
    selManual[indiceCanal] += 10;
    if(selManual[indiceCanal] > limMax) selManual[indiceCanal] = limMax;
    pantalla_control(indiceCanal, posActual[indiceCanal], selManual[indiceCanal], ok);
  }

  if(dpadL && !dpadLAnt)
  {
    selManual[indiceCanal] -= 10;
    if(selManual[indiceCanal] < limMin) selManual[indiceCanal] = limMin;
    pantalla_control(indiceCanal, posActual[indiceCanal], selManual[indiceCanal], ok);
  }

  // X = mover servo
  if(x && !xAnt)
  {
    posActual[indiceCanal] = selManual[indiceCanal];
    moverCanalCompleto(indiceCanal, posActual[indiceCanal]);
    pantalla_control(indiceCanal, posActual[indiceCanal], selManual[indiceCanal], ok);
  }

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

  // Solo redibujar cuando el servo realmente avanzó
  if(posAuto15 != posAntes)
    pantalla_auto15(posAuto15, ctrOk());
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

  bool cir  = (botones & 0x0002);
  bool cuad = (botones & 0x0004);
  bool l1   = (botones & 0x0010);
  bool r1   = (botones & 0x0020);

  bool dpadU = (dpad & 0x01);
  bool dpadD = (dpad & 0x02);
  bool dpadR = (dpad & 0x04);
  bool dpadL = (dpad & 0x08);

  if(chequearHome()) return;

  // L1/R1 = cambiar canal a configurar
  if(l1 && !l1Ant)
  {
    indiceCanal--;
    if(indiceCanal < 0) indiceCanal = NUM_CANALES - 2;
    pantalla_config(indiceCanal, true);
  }

  if(r1 && !r1Ant)
  {
    indiceCanal++;
    if(indiceCanal >= NUM_CANALES - 1) indiceCanal = 0;
    pantalla_config(indiceCanal, true);
  }

  // Dpad arriba/abajo = ajusta limite maximo
  if(dpadU && !dpadUAnt)
  {
    canales[indiceCanal].limMax++;
    if(canales[indiceCanal].limMax > 180) canales[indiceCanal].limMax = 180;
    pantalla_config(indiceCanal, true);
  }

  if(dpadD && !dpadDAnt)
  {
    canales[indiceCanal].limMax--;
    if(canales[indiceCanal].limMax <= canales[indiceCanal].limMin)
      canales[indiceCanal].limMax = canales[indiceCanal].limMin + 1;
    pantalla_config(indiceCanal, true);
  }

  // Dpad derecha/izquierda = ajusta limite minimo
  if(dpadR && !dpadRAnt)
  {
    canales[indiceCanal].limMin++;
    if(canales[indiceCanal].limMin >= canales[indiceCanal].limMax)
      canales[indiceCanal].limMin = canales[indiceCanal].limMax - 1;
    pantalla_config(indiceCanal, true);
  }

  if(dpadL && !dpadLAnt)
  {
    canales[indiceCanal].limMin--;
    if(canales[indiceCanal].limMin < 0) canales[indiceCanal].limMin = 0;
    pantalla_config(indiceCanal, true);
  }

  cirAnt   = cir;
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
// DEBUG
// =========================

// Sub-modos del debug
#define DEBUG_CANALES 0
#define DEBUG_AUTO    1

int  debugModo          = DEBUG_CANALES;
int  debugCanal         = 0;   // indice en canales[] cuando mostrarNumero=false
int  debugCanalRaw      = 0;   // numero de canal PCA (0-15) cuando mostrarNumero=true
int  debugSel           = 90;
int  debugPos           = 90;
bool debugMostrarNumero = false;

// Auto debug (canal 15)
int   debugFase    = 0;
unsigned long debugUltimoPaso = 0;

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

  // =====================
  // SUB-MODO AUTO
  // =====================
  if(debugModo == DEBUG_AUTO)
  {
    if(ok)
    {
      uint16_t botones = myGamepad->buttons();
      bool cir  = (botones & 0x0002);
      bool cuad = (botones & 0x0004);

      // Circulo = detener y volver a canales
      if(cir && !cirAnt)
      {
        pca.setPWM(15, 0, 0);
        debugModo = DEBUG_CANALES;
        pantalla_debug(debugMostrarNumero ? debugCanalRaw : debugCanal, debugPos, debugSel, ok, debugMostrarNumero);
      }
      cirAnt  = cir;
      cuadAnt = cuad;
    }

    // Tick automatico canal 15
    unsigned long ahora = millis();
    if(ahora - debugUltimoPaso >= INTERVALO_AUTO)
    {
      debugUltimoPaso = ahora;

      if(debugFase == 0)
      {
        debugPos++;
        if(debugPos >= 180) { debugPos = 180; debugFase = 1; debugUltimoPaso = ahora + 500; }
      }
      else if(debugFase == 1)
      {
        debugPos--;
        if(debugPos <= 90)  { debugPos = 90;  debugFase = 2; debugUltimoPaso = ahora + 300; }
      }
      else if(debugFase == 2)
      {
        debugPos--;
        if(debugPos <= 0)   { debugPos = 0;   debugFase = 3; debugUltimoPaso = ahora + 500; }
      }
      else if(debugFase == 3)
      {
        debugPos++;
        if(debugPos >= 90)  { debugPos = 90;  debugFase = 0; debugUltimoPaso = ahora + 300; }
      }

      pca.setPWM(15, 0, angleToPulse(debugPos));
    }

    pantalla_debug_auto(debugPos, ok);
    return;
  }

  // =====================
  // SUB-MODO CANALES
  // =====================
  if(!ok)
  {
    pantalla_debug(debugMostrarNumero ? debugCanalRaw : debugCanal, debugPos, debugSel, false, debugMostrarNumero);
    return;
  }

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

  // L1/R1 = cambiar canal
  if(l1 && !l1Ant)
  {
    if(debugMostrarNumero)
    {
      debugCanalRaw--;
      if(debugCanalRaw < 0) debugCanalRaw = 15;
    }
    else
    {
      debugCanal--;
      if(debugCanal < 0) debugCanal = NUM_CANALES - 1;
    }
    debugSel = debugPos;
    int idx = debugMostrarNumero ? debugCanalRaw : debugCanal;
    pantalla_debug(idx, debugPos, debugSel, ok, debugMostrarNumero);
  }

  if(r1 && !r1Ant)
  {
    if(debugMostrarNumero)
    {
      debugCanalRaw++;
      if(debugCanalRaw > 15) debugCanalRaw = 0;
    }
    else
    {
      debugCanal++;
      if(debugCanal >= NUM_CANALES) debugCanal = 0;
    }
    debugSel = debugPos;
    int idx = debugMostrarNumero ? debugCanalRaw : debugCanal;
    pantalla_debug(idx, debugPos, debugSel, ok, debugMostrarNumero);
  }

  // Analogo izquierdo X y dpad = ajustar seleccion
  int lx = myGamepad->axisX();
  if(abs(lx) > DEADZONE)
  {
    int paso = map(abs(lx), DEADZONE, 512, 1, 4);
    if(lx > 0) debugSel += paso;
    else        debugSel -= paso;
    debugSel = constrain(debugSel, 0, 180);
    pantalla_debug(debugMostrarNumero ? debugCanalRaw : debugCanal, debugPos, debugSel, ok, debugMostrarNumero);
  }

  if(dpadR && !dpadRAnt)
  {
    debugSel += 10;
    debugSel = constrain(debugSel, 0, 180);
    pantalla_debug(debugMostrarNumero ? debugCanalRaw : debugCanal, debugPos, debugSel, ok, debugMostrarNumero);
  }

  if(dpadL && !dpadLAnt)
  {
    debugSel -= 10;
    debugSel = constrain(debugSel, 0, 180);
    pantalla_debug(debugMostrarNumero ? debugCanalRaw : debugCanal, debugPos, debugSel, ok, debugMostrarNumero);
  }

  if(dpadU && !dpadUAnt)
  {
    debugSel++;
    debugSel = constrain(debugSel, 0, 180);
    pantalla_debug(debugMostrarNumero ? debugCanalRaw : debugCanal, debugPos, debugSel, ok, debugMostrarNumero);
  }

  if(dpadD && !dpadDAnt)
  {
    debugSel--;
    debugSel = constrain(debugSel, 0, 180);
    pantalla_debug(debugMostrarNumero ? debugCanalRaw : debugCanal, debugPos, debugSel, ok, debugMostrarNumero);
  }

  // Canal fisico activo segun modo
  int canalFisico = debugMostrarNumero
    ? debugCanalRaw
    : canales[debugCanal].numero;
  int idxPantalla = debugMostrarNumero ? debugCanalRaw : debugCanal;

  // X = mover servo al angulo seleccionado (sin timeout)
  if(x && !xAnt)
  {
    debugPos = debugSel;
    pca.setPWM(canalFisico, 0, angleToPulse(debugPos));
    pantalla_debug(idxPantalla, debugPos, debugSel, ok, debugMostrarNumero);
  }

  // Circulo = apagar PWM del canal actual
  if(cir && !cirAnt)
  {
    pca.setPWM(canalFisico, 0, 0);
    pantalla_debug(idxPantalla, debugPos, debugSel, ok, debugMostrarNumero);
  }

  // Cuadrado = entrar a modo automatico canal 15
  if(cuad && !cuadAnt)
  {
    debugModo  = DEBUG_AUTO;
    debugPos   = 90;
    debugFase  = 0;
    debugUltimoPaso = millis();
    pantalla_debug_auto(debugPos, ok);
  }

  // Triangulo = toggle entre nombre de pieza y numero de canal
  if(tri && !triAnt)
  {
    debugMostrarNumero = !debugMostrarNumero;
    if(debugMostrarNumero)
      debugCanalRaw = canales[debugCanal].numero;
    else
      debugCanalRaw = 0;
    int idx = debugMostrarNumero ? debugCanalRaw : debugCanal;
    pantalla_debug(idx, debugPos, debugSel, ok, debugMostrarNumero);
  }

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

  delay(10);
}

// =========================
// CONTROL ANALOGICO
// =========================

void moverConVelocidad(int indice, int eje)
{
  if(abs(eje) <= DEADZONE) return;

  int paso = map(abs(eje), DEADZONE, 512, 1, 4);

  if(eje > 0)
    posActual[indice] += paso;
  else
    posActual[indice] -= paso;

  posActual[indice] = constrain(
    posActual[indice],
    canales[indice].limMin,
    canales[indice].limMax
  );
  moverCanalCompleto(indice, posActual[indice]);
}

void loopAnalogico()
{
  BP32.update();

  bool ok = ctrOk();
  pantalla_analogico(ok);

  if(!ok) return;

  if(chequearHome()) return;

  uint16_t botones = myGamepad->buttons();

  bool cir = (botones & 0x0002);
  bool l1  = (botones & 0x0010);
  bool r1  = (botones & 0x0020);

  int lx = myGamepad->axisX();
  int rx = myGamepad->axisRX();
  int l2 = myGamepad->brake();    // 0-1023
  int r2 = myGamepad->throttle(); // 0-1023

  // Circulo = detener todos los motores
  if(cir && !cirAnt)
  {
    for(int i = 0; i < NUM_CANALES - 1; i++)
    {
      pca.setPWM(canales[i].numero, 0, 0);
      if(canales[i].numeroB != -1)
        pca.setPWM(canales[i].numeroB, 0, 0);
      pwmActivo[i] = false;
    }
  }

  cirAnt = cir;
  l1Ant  = l1;
  r1Ant  = r1;

  // Garra con L2 (cierra) y R2 (abre) — indice 0
  if(l2 > 50)
  {
    int paso = map(l2, 50, 1023, 1, 4);
    posActual[0] -= paso;
    posActual[0] = constrain(posActual[0], canales[0].limMin, canales[0].limMax);
    moverCanalCompleto(0, posActual[0]);
  }
  else if(r2 > 50)
  {
    int paso = map(r2, 50, 1023, 1, 4);
    posActual[0] += paso;
    posActual[0] = constrain(posActual[0], canales[0].limMin, canales[0].limMax);
    moverCanalCompleto(0, posActual[0]);
  }

  // Analogo izquierdo:
  // L1 mantenido → Rotacion-Brazo (indice 3)
  // Normal       → Brazo A (indice 1)
  if(l1)
    moverConVelocidad(3, lx);
  else
    moverConVelocidad(1, lx);

  // Analogo derecho:
  // R1 mantenido → Rotacion-Robot (indice 4)
  // Normal       → Brazo B (indice 2)
  if(r1)
    moverConVelocidad(4, rx);
  else
    moverConVelocidad(2, rx);

  delay(20);
}

// =========================

volatile bool emergenciaFlag = false;

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

void setup()
{
  Serial.begin(115200);
  pinMode(0, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(0), emergenciaISR, FALLING);
  delay(1000);

  Wire.begin(21, 22);
  pantalla_init();

  I2CPCA.begin(26, 25);
  pca.begin();
  pca.setPWMFreq(50);

  // Verificar si el PCA9685 responde
  I2CPCA.beginTransmission(0x40);
  pcaOk = (I2CPCA.endTransmission() == 0);

  servos_init();

  BP32.setup(
    &onConnectedGamepad,
    &onDisconnectedGamepad
  );

  pantalla_menu(menuSel);
}

// =========================

void loop()
{
  // Boton BOOT = apagado de emergencia (manejado por interrupcion)
  if(emergenciaFlag)
  {
    emergenciaFlag = false;
    apagarTodosMotores();
    Serial.println("EMERGENCIA: motores apagados");
  }

  switch(modo)
  {
    case MODO_MENU:      loopMenu();      break;
    case MODO_CONTROL:   loopControl();   break;
    case MODO_AUTO15:    loopAuto15();    break;
    case MODO_ANALOGICO: loopAnalogico(); break;
    case MODO_CONFIG:    loopConfig();    break;
    case MODO_DEBUG:     loopDebug();     break;
  }

  // Canal 15 siempre girando
  tickAuto15();

  verificarTimeoutPWM();
}
