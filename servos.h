#pragma once
#include "config.h"
#include <Adafruit_PWMServoDriver.h>

extern Adafruit_PWMServoDriver pca;

extern Canal canales[NUM_CANALES];
extern int   posActual[NUM_CANALES];
extern int   selManual[NUM_CANALES];
extern unsigned long ultimoMovimiento[NUM_CANALES];
extern bool  pwmActivo[NUM_CANALES];

void servos_init();
int  angleToPulse(int angulo);
void moverServo(int canal, int angulo);
void moverCanalCompleto(int indice, int angulo);
void verificarTimeoutPWM();

// Canal 15 automatico
extern int   posAuto15;
extern int   faseAuto15;
extern unsigned long ultimoPasoAuto15;
void tickAuto15();
