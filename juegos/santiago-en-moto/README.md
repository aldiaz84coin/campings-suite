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
   te hace señas.
2. **El atún mosqueado**: espanta las moscas del atún de Nha Bia.
3. **Pinta la casa vieja**: llena de color la casa de piedra de la antigua
   capital… sin manchar la ventana azul ni a Anita.
4. **Celebración en el Alquimia**: Strelas deslizándose por la barra (estilo
   *Tapper*), con el colega de las rastas robando alguna.
5. **Cidade Velha > Rui Vaz** (carrera): curvas con fiestas, coches tuneados y
   electrónica; lanza mangas.
6. **El cartel caído de Rui Vaz**: vuelve a colocar las letras R-U-I V-A-Z en lo
   alto de la montaña.
7. **¡Bomba en la piscina!**: saltos desde el trampolín; Anita puntúa y el
   colega del donut acaba empapado.
8. **Rui Vaz > Poilão de Boa Entrada** (carrera): niebla y periódicos para la
   gente de los pueblos, como en el *Paperboy* original.
9. **Selfie con el Poilão** (minijuego de *timing*).
10. **Gafas de buzo**: fotos a peces, conchas, medusas y la chancla del colega.
11. **¡Galinhas a la bolsa!**: persecución en un corral de la Serra da Malagueta,
    con plancha, gallo defensor y gallina-sombrero.
12. **Malagueta > Tarrafal** (carrera): las bolsas cuelgan de la moto, las
    gallinas se escapan y hay que repartirlas a las senhoras de la brasa.
13. **Pinchitos en Tarrafal**: atrapa pinchitos; evita malaguetas, carbón y
    gallinas que siguen vivas.

En todas las carreras la carretera está llena de gente (andando, charlando,
bailando, durmiendo en una silla), vacas, burros, gallinas y *aluguers*, y el
freno delantero de la moto se activa solo de vez en cuando.

Power-ups: **grogue** (turbo: más velocidad y puntos dobles), **Strela Kriola**
(modo estrella invencible), **cachupa** (vida extra) y estrellas de *morabeza*.
Cada fase desbloquea una postal con una foto del viaje.

## Controles

| Acción | Teclado | Móvil |
| --- | --- | --- |
| Mover / acelerar / frenar | Flechas o WASD | Cruceta |
| Lanzar a izquierda / derecha | Z / X | ◀ LANZA / LANZA ▶ |
| Lanzar automático, confirmar, golpear, lanzarse | Espacio / Enter / clic | OK o tocar la pantalla |
| Música / voces | M / V | Botones bajo la pantalla |
| Pausa / seguir | P o Esc (seguir: también Espacio) | Botón PAUSA / SEGUIR o tocar la pantalla |

`?paso=N` en la URL salta a un paso concreto del guion (útil para probar).

## Recursos

- `assets/`: caras, cabezas recortadas (para los sprites de Anita y Alvarito) y
  postales pixeladas a partir de las fotos del viaje.
- Música chiptune (aire de funaná con gaita y ferrinho) y efectos generados con
  Web Audio; voces con la síntesis de voz del navegador (`speechSynthesis`).
- Fuente *Press Start 2P* (Google Fonts).
- El mapa de la isla está dibujado a mano siguiendo la geografía real
  (Tarrafal, Malagueta, Boa Entrada, Assomada, Pico da Antónia, Rui Vaz,
  Cidade Velha y Praia).
