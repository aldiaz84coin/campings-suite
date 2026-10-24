# Danielito contra Alvarito

Juego retro para móvil para **aprender las tablas de multiplicar**, en un único
archivo (`index.html`), sin dependencias ni servidor. Se abre en el navegador
del móvil y se juega tocando la pantalla.

## De qué va

Danielito construye un castillo y necesita **6 piezas** escondidas por la casa
(salón, cocina, su cuarto, baño, jardín y desván). En cada habitación tiene que
superar **3 retos de las tablas** para conseguir la pieza.

Mientras piensa, **Alvarito** va acercándose desde la puerta. Si llega antes de
que Danielito acierte, hace una **trastada** (pinta las paredes, tira los
cereales, esconde el mando…), garabatea el tablero y Danielito pierde un
corazón. Cada fallo hace que Alvarito se acerque 5 segundos más rápido.

- En la pantalla de inicio se eligen **qué tablas** se practican (del 2 al 10,
  o todas) y el ritmo: *Con calma* (más tiempo) o *Rápido*.
- 3 corazones. Si terminas una habitación sin ninguna trastada, recuperas uno.
- Puntos: 10 por acierto más los segundos que sobren.

## Tipos de reto

Todos usan solo las tablas elegidas:

- **Multiplicación**: `7 × 6 = ?`
- **Cuenta los grupos**: filas de dibujos («3 filas de 5 dinosaurios»).
- **El número escondido**: `7 × ? = 42`
- **Contar saltando**: `7 · 14 · ? · 28`
- **¿Verdad o mentira?**: `6 × 8 = 46`
- **¿Qué multiplicación?**: cuál de cuatro da un número.
- **El intruso**: qué número no está en la tabla.
- **Problemas**: patas de perros, ruedas de bicis, galletas en platos…

## Voces

El juego habla con la voz del navegador, y cada personaje tiene su tono:

- Una narradora lee cada reto («¿Cuánto es 7 por 6?»), las pistas, las
  trastadas y cada habitación. El botón 🔊 repite el reto.
- **Alvarito** mete prisa: «¡Se lía! ¡Se lía!», «¡Vamos a romper todo!» y, en
  los últimos 5 segundos, «¡Corre, corre, que se lía!». Cuando llega: «¡Se lió!
  ¡Trastada!».
- **Danielito** celebra cada acierto diciendo la multiplicación entera
  («¡Toma ya! 7 por 6 es 42»), para que se le quede.
- El botón ♪ quita los sonidos y las voces.

## Para aprender, no solo para acertar

- Las respuestas falsas son los errores típicos (una vez más o una vez menos,
  la tabla de al lado, fallar por uno), así que hay que saberla de verdad.
- Al fallar aparece una **pista** («7 × 5 = 35. Súmale 7 más»).
- Al acertar se muestra la multiplicación completa; tras una trastada,
  «Recuerda: 7 × 6 = 42».
- Al terminar, una lista **Para repasar** con las multiplicaciones falladas.

## Cómo publicarlo

Es un HTML estático: basta con servir `index.html` desde cualquier hosting de
archivos estáticos (GitHub Pages, Netlify, un bucket…). En el móvil, «Añadir a
pantalla de inicio» lo deja como una app más.

Para probarlo en local: `python3 -m http.server` dentro de esta carpeta y abrir
`http://localhost:8000` (o abrir el archivo directamente en el navegador).
