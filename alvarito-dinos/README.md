# Alvarito y los Dinos

Juego retro para móvil para **aprender las letras mayúsculas**, en un único
archivo (`index.html`), sin dependencias ni servidor. Hermano pequeño de
`../danielito-vs-alvarito`.

## De qué va

Los dinosaurios quieren darle un **bocao** a Alvarito. En cada reto sale una
letra y una voz la nombra («¿Dónde está la eme?»). Si Alvarito la encuentra
antes de que llegue el dino, se pone su **disfraz de Hulk** y le hace una
trampa: piel de plátano, pieza de Lego, cubo de agua fría, cosquillas con una
pluma… Si el dino llega, le da un bocao y Alvarito pierde un corazón.

Cinco fases: velociraptor en la selva, triceratops en la playa, estegosaurio en
la pradera, pterodáctilo en las montañas y, al final, el **T-Rex** en el
volcán, que acaba con una pedrada de tirachinas.

## Para jugar sin saber leer

Todo se juega mirando y escuchando; los textos que quedan son para los mayores.

- La voz del navegador dice cada letra con su nombre y, en las vocales, con su
  sonido, junto a una palabra con dibujo: «¿Dónde está la eme? La eme, como
  moto 🏍️». Tocar el recuadro de la letra (🔊) lo repite.
- Al tocar una letra se oye cuál es («Esa es la ene. Busca la eme.»).
- Cada personaje habla con su propio tono: Alvarito agudo, Danielito, la
  abuela, el abuelo más grave y los dinos con un vozarrón lento.
- Las ayudas son solo caras; el tiempo es una barra con un dino.
- Los botones de las ventanas son símbolos (▶ seguir, ↻ otra vez, 🏠 inicio) y
  cada ventana se narra. Después de un bocao el juego sigue solo.
- Las fichas de letras del final se pueden tocar para oírlas.

## La familia ayuda

- **Danielito** (siempre, cada 10 s): da una pista («M de MANZANA 🍎»), quita
  una letra que no es y distrae al dino con un balón, un coche o un osito.
- **La abuela** (una vez por fase): le echa pescaíto frito; el dino se para a
  comer 8 segundos.
- **El abuelo** (una vez por fase): le asusta con la sombrilla y el dino vuelve
  corriendo al principio.

## Para aprender

- Letras grandes en **Andika**, una fuente pensada para niños que empiezan a
  leer (la letra pixelada se queda para los títulos).
- Tres tipos de reto que llegan poco a poco: ver la letra, solo oírla, y
  «¿con qué letra empieza ABEJA?».
- En fases avanzadas se mezclan letras que se parecen (E/F, M/N, P/R, O/Q…).
- Se elige qué letras jugar: **vocales**, **su nombre** (A L V R I T O),
  **poco a poco** (de las vocales a todo el abecedario) o **todas**.
- Al terminar: las letras encontradas y las que conviene repasar.

## Cómo publicarlo

Es un HTML estático: basta con servir `index.html` desde cualquier hosting de
archivos estáticos. En el móvil, «Añadir a pantalla de inicio» lo deja como una
app más. La voz depende del navegador del móvil: hace falta que tenga una voz
en español (en Android, «Síntesis de voz de Google»; en iPhone viene de serie)
y que el móvil no esté en silencio.
