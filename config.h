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
#define MODO_CTRL_PC   7

// Intervalo entre pasos del homing (ms) por canal — mas alto = mas lento y suave
#define HOMING_INTERVALO_NORMAL  35   // Brazo A y B
#define HOMING_INTERVALO_LENTO   60   // Rotacion Robot (carga pesada)

// Opciones del menu (lista horizontal, se desplaza con dpad izq/der)
#define MENU_CONTROL   0
#define MENU_DEBUG     1
#define MENU_HOMING    2
#define MENU_CTRL_PC   3
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
