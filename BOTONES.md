# Mapa de botones del mando (Bluepad32)

Mapeado manualmente con el modo Debug del proyecto.

## Botones (`myGamepad->buttons()`)

| Botón | Máscara | Bit |
|-------|---------|-----|
| X | `0x0001` | 0 |
| Círculo | `0x0002` | 1 |
| Cuadrado | `0x0004` | 2 |
| Triángulo | `0x0008` | 3 |
| L1 | `0x0010` | 4 |
| R1 | `0x0020` | 5 |
| L2 (digital) | `0x0040` | 6 |
| R2 (digital) | `0x0080` | 7 |
| L3 | `0x0100` | 8 |
| R3 | `0x0200` | 9 |

## DPAD (`myGamepad->dpad()`)

| Dirección | Máscara |
|-----------|---------|
| Arriba | `0x01` |
| Abajo | `0x02` |
| Derecha | `0x04` |
| Izquierda | `0x08` |

## Analógicos

| Función | Método | Rango |
|---------|--------|-------|
| Joystick izquierdo X | `myGamepad->axisX()` | -512 a 512 |
| Joystick izquierdo Y | `myGamepad->axisY()` | -512 a 512 |
| Joystick derecho X | `myGamepad->axisRX()` | -512 a 512 |
| Joystick derecho Y | `myGamepad->axisRY()` | -512 a 512 |
| L2 analógico | `myGamepad->brake()` | 0 a 1023 |
| R2 analógico | `myGamepad->throttle()` | 0 a 1023 |

## Botones no mapeados

Share, Options y el botón táctil (PS4/PS5) **no aparecen en `buttons()`**.
Bluepad32 los expone en `myGamepad->miscButtons()`:

| Botón | Máscara `miscButtons()` |
|-------|------------------------|
| Share / Create | `0x02` |
| Options | `0x04` |
| Botón táctil | no soportado por Bluepad32 |
| PS / Home | `0x01` |
