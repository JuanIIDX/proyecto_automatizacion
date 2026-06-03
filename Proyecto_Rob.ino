#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_PWMServoDriver.h>
#include <Bluepad32.h>

#include "config.h"
#include "servos.h"
#include "pantalla.h"

// Hardware
Adafruit_SSD1306        oled(128, 64, &Wire, -1);
TwoWire                 I2CPCA = TwoWire(1);
Adafruit_PWMServoDriver pca(0x40, I2CPCA);

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
  // config
  // (usa canales[] directamente — protegido por mutex)
};

volatile bool pantallaActualizar = false;
EstadoPantalla snapPantalla;

void solicitarPantalla()
{
  pantallaActualizar = true;
}

// Tarea del Core 0 — solo dibuja la pantalla
void tareaPantalla(void* param)
{
  for(;;)
  {
    if(pantallaActualizar)
    {
      pantallaActualizar = false;

      // Tomar snapshot bajo mutex
      EstadoPantalla s;
      if(xSemaphoreTake(mutexOled, pdMS_TO_TICKS(10)))
      {
        s = snapPantalla;
        xSemaphoreGive(mutexOled);
      }
      else
      {
        vTaskDelay(1);
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
      }
    }
    vTaskDelay(1);  // ceder tiempo al sistema
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
  solicitarPantalla();
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

  uint16_t botones = myGamepad->buttons();
  uint8_t  dpad    = myGamepad->dpad();

  bool dpadU = (dpad & 0x01);
  bool dpadD = (dpad & 0x02);
  bool dpadR = (dpad & 0x04);
  bool dpadL = (dpad & 0x08);
  bool x     = (botones & 0x0001);

  bool cambio = false;

  if(dpadR && !dpadRAnt) { if(menuSel % 2 == 0) menuSel++; cambio = true; }
  if(dpadL && !dpadLAnt) { if(menuSel % 2 == 1) menuSel--; cambio = true; }
  if(dpadD && !dpadDAnt) { if(menuSel < 2) menuSel += 2;   cambio = true; }
  if(dpadU && !dpadUAnt) { if(menuSel >= 2) menuSel -= 2;  cambio = true; }

  if(x && !xAnt)
  {
    switch(menuSel)
    {
      case MENU_PROGRAMA:
      case MENU_JUEGO:
        break;

      case MENU_CONTROL:
        if(!ctrOk())
        {
          // Aviso sin bloquear — lo dibujamos directamente
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
          modo = MODO_ANALOGICO;
          cambio = true;
        }
        break;

      case MENU_DEBUG:
        modo = MODO_DEBUG;
        cambio = true;
        break;
    }
  }

  if(cambio) actualizarSnap();

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
  solicitarPantalla();
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
// CONTROL ANALOGICO
// =========================

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
  BP32.update();

  bool ok = ctrOk();
  if(!ok) { actualizarSnap(); return; }

  if(chequearHome()) return;

  uint16_t botones = myGamepad->buttons();

  bool cir = (botones & 0x0002);
  bool l1  = (botones & 0x0010);
  bool r1  = (botones & 0x0020);

  int lx = myGamepad->axisX();
  int rx = myGamepad->axisRX();
  int l2 = myGamepad->brake();
  int r2 = myGamepad->throttle();

  bool cambio = false;

  if(cir && !cirAnt)
  {
    for(int i = 0; i < NUM_CANALES - 1; i++)
    {
      pca.setPWM(canales[i].numero, 0, 0);
      if(canales[i].numeroB != -1)
        pca.setPWM(canales[i].numeroB, 0, 0);
      pwmActivo[i] = false;
    }
    cambio = true;
  }

  cirAnt = cir;
  l1Ant  = l1;
  r1Ant  = r1;

  // Garra L2/R2
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

  // Analogo izq
  if(abs(lx) > DEADZONE)
  {
    if(l1) moverConVelocidad(3, lx);
    else   moverConVelocidad(1, lx);
    cambio = true;
  }

  // Analogo der
  if(abs(rx) > DEADZONE)
  {
    if(r1) moverConVelocidad(4, rx);
    else   moverConVelocidad(2, rx);
    cambio = true;
  }

  if(cambio) actualizarSnap();

  delay(20);
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

  Wire.begin(21, 22);
  pantalla_init();

  I2CPCA.begin(26, 25);
  pca.begin();
  pca.setPWMFreq(50);

  I2CPCA.beginTransmission(0x40);
  pcaOk = (I2CPCA.endTransmission() == 0);

  servos_init();

  BP32.setup(
    &onConnectedGamepad,
    &onDisconnectedGamepad
  );

  // Crear mutex para el OLED
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

  // Lanzar tarea de pantalla en Core 0
  // Core 1 es el que corre loop() por defecto en ESP32
  xTaskCreatePinnedToCore(
    tareaPantalla,   // funcion
    "Pantalla",      // nombre
    4096,            // stack
    NULL,            // parametro
    1,               // prioridad
    NULL,            // handle
    0                // core 0
  );

  pantalla_menu(0);
}

// =========================

void loop()
{
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

  // Enviar angulos al PC cada 100ms
  static unsigned long ultimoEnvio = 0;
  if(millis() - ultimoEnvio >= 100)
  {
    ultimoEnvio = millis();
    Serial.print("ANGULOS:");
    Serial.print(posActual[0]); Serial.print(",");  // Garra
    Serial.print(posActual[1]); Serial.print(",");  // Brazo A
    Serial.print(posActual[2]); Serial.print(",");  // Brazo B
    Serial.print(posActual[3]); Serial.print(",");  // Rotacion-Brazo
    Serial.print(posActual[4]); Serial.print(",");  // Rotacion-Robot
    Serial.println(posAuto15);                      // Canal 15
  }
}
