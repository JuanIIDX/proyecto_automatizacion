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
#define MODO_HOMING    6

// Intervalo entre pasos del homing (ms) — mas alto = mas lento
#define HOMING_INTERVALO 18

// Opciones del menu (lista horizontal, se desplaza con dpad izq/der)
#define MENU_CONTROL   0
#define MENU_DEBUG     1
#define MENU_HOMING    2
#define MENU_TOTAL     3

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
