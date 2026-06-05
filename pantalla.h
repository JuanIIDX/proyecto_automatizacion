#pragma once
#include <Adafruit_SSD1306.h>

#define NAVBAR_H 13

extern Adafruit_SSD1306 oled;
extern bool pcaOk;

bool pantalla_init();
void navbar(bool ctrOk);
void pantalla_menu(int seleccion);
void pantalla_control(int indiceCanal, int posActual, int selManual, bool ctrOk);
void pantalla_auto15(int pos, bool ctrOk);
void pantalla_config(int indiceCanal, bool ctrOk);
void pantalla_debug(int indiceCanal, int pos, int sel, bool ctrOk, bool mostrarNumero, int delayMs = 20);
void pantalla_debug_auto(int pos, bool ctrOk);
void pantalla_analogico(bool ctrOk);
void pantalla_homing(const char* nombre, int pos, int target, int paso, int total, bool ctrOk);
void pantalla_ctrl_pc(bool ctrOk);
