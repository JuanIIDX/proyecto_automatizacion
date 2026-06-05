# Mapa de Puertos GPIO — ESP32 (Proyecto_Rob)

## Puertos de Entrada/Salida Digital

| GPIO | Tipo | Dispositivo | Descripción |
|------|------|-------------|-------------|
| **0** | Input (PULLUP) | Botón de Emergencia | Interrupción por flanco de bajada (`FALLING`). Activa `emergenciaISR()` que apaga todos los motores inmediatamente. |

---

## Bus I2C — Wire (Bus 0)

**SDA = GPIO 4 · SCL = GPIO 5**

| Dispositivo | Dirección I2C | Descripción |
|-------------|--------------|-------------|
| **SSD1306** (OLED 128×64) | `0x3C` | Pantalla principal. Muestra menús, estado del robot, posiciones de servos y barra de homing. Controlada desde Core 0 (tarea `tareaPantalla`). |

---

## Bus I2C — I2CPCA / TwoWire(1) (Bus 1)

**SDA = GPIO 16 · SCL = GPIO 17**

| Dispositivo | Dirección I2C | Descripción |
|-------------|--------------|-------------|
| **PCA9685** (PWM Servo Driver) | `0x40` | Controlador de 16 canales PWM para todos los servos del robot. Opera a 50 Hz. |

### Canales PCA9685 asignados

| Canal PCA | Servo | Rango | Notas |
|-----------|-------|-------|-------|
| **0** | Garra | 30°–110° | Canal único |
| **3** | Brazo A | 10°–160° | Canal único |
| **4** | Brazo B | 10°–100° | Canal único |
| **7** | Rotación-Reloj (espejo) | 0°–180° | Espejo invertido de Rotación-Robot (`180 - ángulo`), calculado en software |
| **8** | Rotación-Brazo (principal) | 10°–160° | Canal A del par |
| **9** | Rotación-Brazo (espejo) | 10°–160° | Canal B invertido (`180 - ángulo`) |
| **12** | Rotación-Robot | 0°–180° | Canal único, homing arranca en 180° |
| **15** | Auto15 | 0°–180° | Movimiento automático continuo, siempre activo en el `loop()` |

---

## GPIO Digitales — TM1637 (Display 7 segmentos)

| GPIO | Pin TM1637 | Descripción |
|------|-----------|-------------|
| **18** | CLK | Reloj del display de 4 dígitos TM1637. Muestra cronómetro de nivel (SS:dd o MM:SS). |
| **19** | DIO | Datos del display TM1637. |

---

## GPIO Analógicos — Sensores IR

| GPIO | Sensor | Color (físico) | Descripción |
|------|--------|---------------|-------------|
| **32** | IR2 | Amarillo | Sensor infrarrojo analógico. Enviado por Serial como `IR:v1,v2,v3,v4` cada 100 ms. |
| **33** | IR1 | Verde | Sensor infrarrojo analógico. |
| **34** | IR4 | Azul | Sensor infrarrojo analógico (solo entrada, pin input-only). |
| **35** | IR3 | Rojo | Sensor infrarrojo analógico (solo entrada, pin input-only). |

> Los GPIOs 34 y 35 son **input-only** en el ESP32 (sin pull-up interno disponible).

---

## USB / UART (interno)

| Periférico | Descripción |
|-----------|-------------|
| **Serial (USB)** | Comunicación con PC a 115200 baud. Recibe comandos `CMD:*` desde Python. Envía `ANGULOS:`, `IR:` y `TEMP:` cada 100 ms. |
| **Bluetooth (Bluepad32)** | Gamepad inalámbrico tipo PS4. Usa el stack BT interno del ESP32. No ocupa GPIO. |
| **Sensor de temperatura** | Sensor interno del chip ESP32, leído con `temperatureRead()`. Mostrado en la navbar del OLED y enviado por Serial. |

---

## Resumen visual

```
ESP32
├── GPIO 0   → Botón Emergencia (INT FALLING)
├── GPIO 4   → SDA  Bus I2C 0 → OLED SSD1306 (0x3C)
├── GPIO 5   → SCL  Bus I2C 0 ↗
├── GPIO 16  → SDA  Bus I2C 1 → PCA9685 (0x40)
├── GPIO 17  → SCL  Bus I2C 1 ↗
├── GPIO 18  → TM1637 CLK  → Display 7-seg
├── GPIO 19  → TM1637 DIO  → Display 7-seg
├── GPIO 32  → IR2 (Amarillo) analógico
├── GPIO 33  → IR1 (Verde)    analógico
├── GPIO 34  → IR4 (Azul)     analógico [input-only]
├── GPIO 35  → IR3 (Rojo)     analógico [input-only]
├── USB/UART → PC (115200 baud, comandos + telemetría)
└── BT       → Gamepad Bluepad32 (interno, sin GPIO)
```
