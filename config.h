#pragma once

// Servo PWM
#define SERVOMIN 100
#define SERVOMAX 600

// Timeout para apagar PWM tras movimiento (ms)
#define TIMEOUT_PWM 30000

// Intervalo del movimiento automatico (ms)
#define INTERVALO_AUTO 30

// Modos del sistema
#define MODO_MENU      0
#define MODO_CONTROL   1
#define MODO_AUTO15    2
#define MODO_ANALOGICO 3
#define MODO_CONFIG    4
#define MODO_DEBUG     5

// Opciones del menu
#define MENU_PROGRAMA  0
#define MENU_JUEGO     1
#define MENU_CONTROL   2
#define MENU_DEBUG     3
#define MENU_TOTAL     4

// Deadzone analogicos
#define DEADZONE 30

// Canales
#define NUM_CANALES 6

struct Canal
{
  int  numero;
  int  numeroB;
  bool invertido;
  const char* nombre;
  int  limMin;
  int  limMax;
};
