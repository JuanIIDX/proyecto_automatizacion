#include "servos.h"

Canal canales[NUM_CANALES] = {
  {  0, -1, false, "Garra",          30, 110 },
  {  3, -1, false, "Brazo A",        10, 160 },
  {  4, -1, false, "Brazo B",        10, 100 },
  {  8,  9, true,  "Rotacion-Brazo", 10, 160 },
  { 12, -1, false, "Rotacion-Robot",  0, 180 },
  { 15, -1, false, "Auto15",          0, 180 },
};

int  posActual[NUM_CANALES];
int  selManual[NUM_CANALES];
unsigned long ultimoMovimiento[NUM_CANALES];
bool pwmActivo[NUM_CANALES];

// Canal 15 automatico
int  posAuto15      = 90;
int  faseAuto15     = 0;
unsigned long ultimoPasoAuto15 = 0;

int angleToPulse(int angulo)
{
  return map(angulo, 0, 180, SERVOMIN, SERVOMAX);
}

void moverServo(int canal, int angulo)
{
  pca.setPWM(canal, 0, angleToPulse(angulo));
}

void moverCanalCompleto(int indice, int angulo)
{
  pca.setPWM(canales[indice].numero, 0, angleToPulse(angulo));

  if(canales[indice].numeroB != -1)
  {
    int anguloB = canales[indice].invertido
      ? (180 - angulo)
      : angulo;
    pca.setPWM(canales[indice].numeroB, 0, angleToPulse(anguloB));
  }

  // Canal 7 = Rotacion-Reloj: espejo invertido de Rotacion-Robot (indice 4)
  if(indice == 4)
    pca.setPWM(7, 0, angleToPulse(180 - angulo));

  ultimoMovimiento[indice] = millis();
  pwmActivo[indice] = true;
}

void verificarTimeoutPWM()
{
  // Sin timeout — los servos mantienen su posicion indefinidamente
}

void tickAuto15()
{
  unsigned long ahora = millis();
  if(ahora - ultimoPasoAuto15 < INTERVALO_AUTO)
    return;
  ultimoPasoAuto15 = ahora;

  if(faseAuto15 == 0)
  {
    posAuto15++;
    if(posAuto15 >= 180) { posAuto15 = 180; faseAuto15 = 1; ultimoPasoAuto15 = ahora + 500; }
  }
  else if(faseAuto15 == 1)
  {
    posAuto15--;
    if(posAuto15 <= 0)  { posAuto15 = 0;   faseAuto15 = 2; ultimoPasoAuto15 = ahora + 500; }
  }
  else if(faseAuto15 == 2)
  {
    posAuto15++;
    if(posAuto15 >= 90) { posAuto15 = 90;  faseAuto15 = 0; ultimoPasoAuto15 = ahora + 1000; }
  }

  pca.setPWM(15, 0, angleToPulse(posAuto15));
}

void servos_init()
{
  for(int i = 0; i < NUM_CANALES; i++)
  {
    // Rotacion-Robot (indice 4) arranca en limMax (180)
    int inicio = (i == 4) ? canales[i].limMax : canales[i].limMin;
    posActual[i]        = inicio;
    selManual[i]        = inicio;
    ultimoMovimiento[i] = 0;
    pwmActivo[i]        = false;
    pca.setPWM(canales[i].numero, 0, 0);
    if(canales[i].numeroB != -1)
      pca.setPWM(canales[i].numeroB, 0, 0);
  }
  // Canal 7 Rotacion-Reloj: espejo de Rotacion-Robot (arranca en 180-180=0)
  pca.setPWM(7, 0, angleToPulse(180 - canales[4].limMax));
}
