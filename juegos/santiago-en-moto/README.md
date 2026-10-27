# Santiago en Moto

Videojuego retro (estilo *Paperboy*) en el que **Anita y Alvarito** recorren la
isla de Santiago (Cabo Verde) en su scooter amarilla TORO TANK.

Es una página HTML autónoma: no depende de la app de campings ni de ningún
servidor propio. Para jugar en local:

```bash
cd juegos/santiago-en-moto
python3 -m http.server 8000
# abre http://localhost:8000
```

## Fases

1. **Praia > Cidade Velha** (carrera): lanza *pastéis com diabo dentro* a quien
   te hace señas; esquiva cabras, perros, baches, cáscaras de plátano, turistas
   y *aluguer*.
2. **El atún mosqueado** (minijuego): espanta las moscas del atún de Nha Bia.
3. **Pinta la casa vieja** (minijuego): llena de color la casa de piedra de la
   antigua capital… sin manchar la ventana azul ni a Anita.
4. **Rui Vaz > Poilão de Boa Entrada** (carrera): montaña, niebla, las letras de
   Rui Vaz y bananas para los macacos verdes.
5. **Selfie con el Poilão** (minijuego de *timing*).
6. **Malagueta > Tarrafal** (carrera): recoge gallinas en bolsas de plástico y
   lánzalas a las senhoras del frango assado; cuidado con los monos ladrones.
7. **Frango assado** (minijuego): atrapa los trozos de pollo y evita las
   malaguetas y el carbón.

Power-ups: **grogue** (turbo: más velocidad y puntos dobles), **Strela Kriola**
(modo estrella invencible), **cachupa** (vida extra) y estrellas de *morabeza*.
Cada fase desbloquea una postal con una foto del viaje.

## Controles

| Acción | Teclado | Móvil |
| --- | --- | --- |
| Mover / acelerar / frenar | Flechas o WASD | Cruceta |
| Lanzar a izquierda / derecha | Z / X | ◀ LANZA / LANZA ▶ |
| Lanzar automático, confirmar, golpear | Espacio / Enter / clic | OK o tocar la pantalla |
| Música / voces / pausa | M / V / P | Botones bajo la pantalla |

`?paso=N` en la URL salta a un paso concreto del guion (útil para probar).

## Recursos

- `assets/`: caras y postales pixeladas a partir de las fotos del viaje.
- Música chiptune (aire de funaná con gaita y ferrinho) y efectos generados con
  Web Audio; voces con la síntesis de voz del navegador (`speechSynthesis`).
- Fuente *Press Start 2P* (Google Fonts).
- El mapa de la isla está dibujado a mano siguiendo la geografía real
  (Tarrafal, Malagueta, Boa Entrada, Assomada, Pico da Antónia, Rui Vaz,
  Cidade Velha y Praia).
