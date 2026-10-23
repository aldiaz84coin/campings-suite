# Danielito contra Alvarito

Juego retro para móvil, en un único archivo (`index.html`), sin dependencias ni
servidor. Se abre en el navegador del móvil y se juega tocando la pantalla.

## De qué va

Danielito construye un castillo y necesita **6 piezas** escondidas por la casa
(salón, cocina, su cuarto, baño, jardín y desván). En cada habitación tiene que
superar **3 retos** para conseguir la pieza.

Mientras piensa, **Alvarito** va acercándose desde la puerta. Si llega antes de
que Danielito acierte, hace una **trastada** (pinta las paredes, tira los
cereales, esconde el mando…), garabatea el tablero y Danielito pierde un
corazón. Cada fallo hace que Alvarito se acerque 5 segundos más rápido.

- 3 corazones. Si terminas una habitación sin ninguna trastada, recuperas uno.
- Las trastadas dejan la habitación manchada el resto de la partida.
- Puntos: 10 por acierto más los segundos que sobren.

## Retos (pensados para 7 años)

- **Multiplicaciones**: en *Fácil*, tablas del 2, 5 y 10; en *Normal*, todas.
- **Problemas**: patas de perros, ruedas de bicis, galletas en platos…
- **Cuentas**: sumas y restas (hasta 20 en Fácil, hasta 60 en Normal).
- **Series**: qué número sigue o falta, y patrones de dibujos.
- **El intruso**: cuál no es de la misma familia.
- **Adivinanzas** clásicas.
- **Lógica**: quién corre más rápido, días de la semana, pares e impares…

## Cómo publicarlo

Es un HTML estático: basta con servir `index.html` desde cualquier hosting de
archivos estáticos (GitHub Pages, Netlify, un bucket…). En el móvil, «Añadir a
pantalla de inicio» lo deja como una app más.

Para probarlo en local: `python3 -m http.server` dentro de esta carpeta y abrir
`http://localhost:8000` (o abrir el archivo directamente en el navegador).
