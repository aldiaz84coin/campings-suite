# Campings Suite

Web y back-office para campings, pensado para **venderse camping a camping**:
cada camping cliente tiene **su propia web en su propio dominio**
(`www.sucamping.com`) y **su propio panel** (`www.sucamping.com/es/panel/`)
desde el que gestiona fotos, instalaciones, alojamientos, precios por
temporada, servicios, políticas y reservas. No hay directorio ni buscador
público: la web de cada camping es independiente y solo muestra ese camping.

Una sola instalación (una app en **Fly.io** y una base de datos **PostgreSQL
gratuita**, con CI/CD en **Buddy**) da servicio a todos los campings que
vendas; cada uno solo ve y gestiona lo suyo. Todo es **multiidioma** (español,
inglés, francés, alemán, neerlandés e italiano).

## Cómo se da de alta un camping vendido

1. **Crea el camping** en *Panel → Plataforma → Nuevo camping*: nombre, correo
   del propietario, idioma principal y, si ya lo sabes, su dominio. El
   propietario recibe un correo con un enlace para elegir su contraseña (el
   enlace también se muestra en pantalla por si prefieres enviarlo tú).
   Si el camping ya tiene web, pon su dirección en **Web actual**: se lee y
   se rellenan automáticamente sus datos (ver [Importar la web actual](#importar-la-web-actual)).
2. **Conecta su dirección web** (ver [Direcciones de los campings](#6-direcciones-de-los-campings)):
   - con **dominio propio**: `fly certs add www.sucamping.com` y el camping (o
     tú) crea el registro DNS que indican los *Ajustes* del camping;
   - mientras tanto, o si no tiene dominio: un **subdominio automático**
     `sucamping.tudominio.com` (si configuras `CAMPING_DOMAIN_SUFFIX`) o la
     dirección de la plataforma `https://tu-app.fly.dev/es/camping/sucamping/`.
3. **El camping completa su web** desde el panel (tiene una lista de pasos) y
   la **publica**. Hasta entonces su dominio muestra una página «Próximamente»
   con su teléfono y correo.
4. En cuanto llega la primera visita por su dominio propio, este pasa a ser su
   dirección oficial: las direcciones anteriores redirigen a él (301), y los
   enlaces del panel y de los correos lo usan.
5. Por camping, como administrador puedes además ocultar el crédito «Powered
   by» (marca blanca) o **suspenderlo** (por ejemplo por impago): su web deja
   de verse pero su panel sigue funcionando.

## Qué incluye

**Web de cada camping** (en la raíz de su dominio: `/es/`, `/en/`, `/fr/`…)

- Portada, galería con visor, alojamientos (capacidad, superficie,
  equipamiento, fotos), instalaciones por categorías, tabla de precios por
  temporada, servicios y extras, políticas de reserva, mapa y contacto, con
  los colores, logotipo y tipografía del camping.
- Formulario de solicitud de reserva con **presupuesto en vivo** (temporadas,
  precio por persona, tasa turística, mascotas, extras opcionales, estancia
  mínima, periodo de apertura y disponibilidad).
- Correos automáticos al camping y al cliente, cada uno en su idioma; los del
  cliente salen **a nombre del camping** y las respuestas le llegan a él.
- SEO propio de cada dominio: `sitemap.xml`, `robots.txt`, `hreflang`,
  `canonical`, Open Graph y datos estructurados schema.org `Campground`.
- **Páginas legales** redactadas con los datos del camping: aviso legal
  (LSSI-CE), política de privacidad (RGPD: responsable, finalidades, bases
  legales, conservación, derechos y AEPD) y política de cookies, enlazadas en
  el pie junto al número de registro de turismo.
- **Google Analytics 4** opcional con **aviso de consentimiento**: no se carga
  nada hasta que el visitante acepta, al rechazar se borran las cookies `_ga`
  y se puede cambiar la elección desde el pie («Configurar cookies»). También
  admite el código de verificación de **Google Search Console**.
- Página «Próximamente» mientras la web no está publicada.

**Panel de cada camping** (`/es/panel/` en su propio dominio; también en el
dominio de la plataforma)

- Inicio con la ocupación de hoy (llegadas, salidas, huéspedes), lista de pasos
  para completar la web y últimas solicitudes.
- Descripción y contacto, ubicación (mapa) y periodo de apertura.
- Fotos: subida múltiple desde el móvil (JPG, PNG, WebP, HEIC), conversión
  automática a WebP, orden arrastrando, foto principal y pies de foto por idioma.
- Apariencia: logotipo, colores (con combinaciones sugeridas) y tipografía,
  con vista previa.
- Instalaciones (catálogo de 46 + personalizadas), tipos de alojamiento (con
  número de unidades), servicios y extras (siempre cobrados, opcionales o
  incluidos) y **tarifas por periodos**: temporadas baja, media y alta, cada
  una con sus precios y con tantos periodos de fechas como haga falta (p. ej.
  alta en verano y en Navidad), más **periodos especiales** (Semana Santa,
  puentes, fiestas…) que tienen prioridad en sus fechas y pueden tener su
  propia estancia mínima. «Copiar fechas al año siguiente» repite los
  periodos (los de Semana Santa siguen a la Pascua) sin tocar los precios.
- **Tabla de precios** por temporada, con el precio base para las fechas que
  no cubre ningún periodo.
- **Importar la web actual** del camping: textos, fotos, instalaciones y
  tarifas (ver más abajo).
- Políticas de reserva: horarios, estancia mínima/máxima, depósito, formas de
  pago, cancelación, mascotas y normas.
- Reservas: solicitudes de la web (confirmar/rechazar con correo al cliente),
  **reservas manuales** (teléfono, mostrador…) con precio pactado opcional,
  varias unidades por reserva, aviso de *overbooking*, **calendario de
  ocupación** mensual, filtros y **exportación a CSV**.
- Equipo: invitar personas (propietario o personal) con enlace para elegir
  contraseña.
- **Datos legales**: titular, NIF/CIF, domicilio social, datos registrales y
  número de registro de turismo, más textos adicionales para el aviso legal y
  la privacidad (son un punto de partida: conviene que los revise su asesor).
- Ajustes: dirección web, idiomas de la página, moneda, avisos de reservas e
  IDs de Google Analytics y Search Console (se puede pegar la etiqueta meta
  entera: se extrae el código).

**Plataforma** (para ti, en el dominio de la plataforma)

- Sección *Plataforma* para superusuarios: todos los campings con su dirección
  y estado, alta de campings con su propietario, suspender/reactivar.
- En los *Ajustes* de cada camping: dominio propio (con su estado y los pasos
  de DNS) y crédito «Powered by».
- Administración completa de Django en `/superadmin/`.
- Registro público de campings desactivado por defecto (`SIGNUP_ENABLED`).

## Importar la web actual

Al crear un camping (campo **Web actual**) o desde *Panel → Importar desde una
web*, la app lee la web que el camping ya tiene y propone:

- **Datos**: nombre, correo, teléfono, WhatsApp, Instagram, Facebook,
  dirección, coordenadas del mapa, categoría (estrellas), horarios de entrada
  y salida y periodo de apertura (de los datos schema.org, las etiquetas meta,
  los enlaces `tel:`/`mailto:`, los mapas incrustados y el texto).
- **Datos legales** del aviso legal de la web: titular, NIF/CIF, datos del
  Registro Mercantil y número de registro de turismo; y el ID de Google
  Analytics y el código de Search Console que ya use, para no perder las
  estadísticas ni la verificación al cambiar de web.
- **Textos** (lema y descripción) en cada idioma que tenga la web (enlaces
  `hreflang`) y el texto de «cómo llegar».
- **Logotipo y fotos**: de la portada, galerías y sliders; en webs WordPress
  descarga el original en lugar de las miniaturas.
- **Instalaciones**, detectadas por palabras clave en seis idiomas.
- **Tarifas**: las tablas de precios (también en filas o columnas invertidas y
  con varias tablas), clasificando cada fila como alojamiento (parcela,
  bungalow, mobil-home…) o servicio (adulto, niño, perro, electricidad,
  tasa turística…) y cada columna como temporada baja, media, alta o periodo
  especial, con sus fechas cuando aparecen en la web («Temporada alta: del 1
  de julio al 31 de agosto», «01/07 - 31/08»…). Si las tarifas están en PDF,
  lo indica para introducirlas a mano.

Nada se guarda hasta revisarlo: una pantalla muestra lo encontrado junto al
valor actual y permite marcar qué importar y cambiar la clasificación de cada
precio. Las fotos se descargan y optimizan después, por tandas, con una barra
de progreso. Solo se leen direcciones públicas de internet (nunca redes
internas) con límites de tamaño y tiempo. Las webs que se construyen solo con
JavaScript o que bloquean robots pueden no dar resultados.

## Tecnología

Django 5.2 LTS · PostgreSQL (SQLite en local) · Gunicorn · WhiteNoise ·
Pillow (WebP) · django-storages (S3 compatible). Sin Node ni compilación de
frontend: plantillas de Django, CSS y JavaScript sin dependencias.

## Puesta en marcha en local

Requisitos: Python 3.11 o superior.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo --owner-password demo12345   # camping de ejemplo
python manage.py createsuperuser
python manage.py runserver
```

- Web del camping de ejemplo: <http://localhost:8000/es/camping/los-pinos-demo/>
- Su panel: <http://localhost:8000/es/panel/> (`demo@example.com` / `demo12345`)
- Superadmin: <http://localhost:8000/superadmin/>

Para probar las direcciones propias en local:

- **Subdominios**: con `CAMPING_DOMAIN_SUFFIX=localhost:8000` en `.env`, el
  camping de ejemplo está en <http://los-pinos-demo.localhost:8000/es/> (los
  navegadores resuelven `*.localhost` solos).
- **Dominio propio**: añade `127.0.0.1 www.micamping.test` a `/etc/hosts`,
  escribe `www.micamping.test` como dominio en los *Ajustes* del camping (con
  un superusuario) y abre <http://www.micamping.test:8000/es/>.

Tests (usan SQLite en memoria):

```bash
python manage.py test tests
```

## Despliegue en Fly.io

### 1. Base de datos PostgreSQL gratuita

Cualquiera de estas opciones sirve; copia su *connection string*:

- **Supabase** (plan gratuito, 500 MB): *Project Settings → Database →
  Connection string*, opción **Session pooler** (puerto 5432, funciona por
  IPv4). Añade `?sslmode=require` al final. El plan gratuito admite 2 proyectos
  activos por organización: si ya los tienes, puedes pausar uno o usar Neon.
- **Neon** (plan gratuito, 0,5 GB): copia la cadena de conexión del panel (ya
  incluye `sslmode=require`).

Si usas el *transaction pooler* de Supabase (puerto 6543) añade también
`DB_TRANSACTION_POOLER=True`.

### 2. Crear la app y desplegar

```bash
fly auth login
fly launch --copy-config --no-deploy --name tu-app-campings   # usa Dockerfile y fly.toml
fly secrets set \
  SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')" \
  DATABASE_URL="postgres://USUARIO:CONTRASEÑA@HOST:5432/postgres?sslmode=require" \
  DJANGO_SUPERUSER_EMAIL="tu@email.com" \
  DJANGO_SUPERUSER_PASSWORD="una-contraseña-larga"
fly deploy
```

En cada despliegue `bin/release.sh` aplica las migraciones y crea el
superusuario si no existe. La app queda en `https://tu-app-campings.fly.dev`.

`fly.toml` usa la región de Madrid (`mad`), una máquina `shared-cpu-1x` de
512 MB que **se apaga sola cuando no hay tráfico** y arranca con la siguiente
visita, para que el coste sea mínimo. Fly factura por uso: consulta sus precios
actuales en <https://fly.io/pricing>.

### 3. Fotos

Elige dónde se guardan con `MEDIA_STORAGE`:

| Opción | Configuración | Cuándo usarla |
| --- | --- | --- |
| `db` (por defecto en producción) | Nada más | Para empezar: las fotos se guardan optimizadas en PostgreSQL (≈150–300 KB cada una) y se sirven con caché de larga duración. |
| `s3` con **Tigris** (almacenamiento de Fly, 5 GB gratis) | `fly storage create --public` (crea `BUCKET_NAME`, `AWS_*`) y `fly secrets set MEDIA_PUBLIC_DOMAIN=<bucket>.fly.storage.tigris.dev` | Recomendado cuando crezcas. |
| `s3` con **Supabase Storage** (1 GB gratis) | Bucket público `media` y claves S3 (*Storage → Settings*); ver ejemplo abajo | Si ya usas Supabase para la base de datos. |
| `local` + volumen de Fly | `fly volumes create data`, `[mounts]` en `fly.toml`, `MEDIA_STORAGE=local`, `MEDIA_ROOT=/data/media` | Alternativa sencilla con coste muy bajo. |

Ejemplo con Supabase Storage:

```bash
fly secrets set MEDIA_STORAGE=s3 AWS_STORAGE_BUCKET_NAME=media \
  AWS_S3_ENDPOINT_URL=https://<ref>.supabase.co/storage/v1/s3 \
  AWS_S3_REGION_NAME=<región-del-proyecto> AWS_S3_ADDRESSING_STYLE=path \
  AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
  MEDIA_PUBLIC_DOMAIN=<ref>.supabase.co/storage/v1/object/public/media
```

Cambiar de almacenamiento más adelante no mueve las fotos ya subidas.

### 4. Correo (opcional)

Sin configurar, los correos se escriben en el log. Para enviarlos de verdad
(avisos de reservas, invitaciones, recuperación de contraseña) usa cualquier
SMTP, por ejemplo Brevo (300 correos/día gratis) o Resend:

```bash
fly secrets set EMAIL_URL="smtp+tls://USUARIO:CLAVE@smtp-relay.brevo.com:587" \
  DEFAULT_FROM_EMAIL="Campings Suite <reservas@tu-dominio.com>"
```

### 5. CI/CD con Buddy

`buddy.yml` define un pipeline que, en cada *push* a `main`, ejecuta los tests
y despliega en Fly.io (`flyctl deploy --remote-only`, el build se hace en Fly):

1. En Buddy (plan gratuito) crea un proyecto conectado a este repositorio de
   GitHub; detecta `buddy.yml` automáticamente.
2. Genera un token con `fly tokens create deploy` y guárdalo en Buddy como
   variable secreta `FLY_API_TOKEN`.
3. Haz *push* a `main`.

### 6. Direcciones de los campings

Todas las direcciones apuntan a la misma app; el middleware
`core.middleware.HostRoutingMiddleware` decide qué camping sirve cada una.

- **Dominio de la plataforma** (tu panel, p. ej. `app.tuempresa.com`):
  `fly certs add app.tuempresa.com`, crea los registros DNS que indica Fly y
  define `ALLOWED_HOSTS` y `PLATFORM_URL`:
  `fly secrets set ALLOWED_HOSTS=app.tuempresa.com,tu-app-campings.fly.dev PLATFORM_URL=https://app.tuempresa.com`.
- **Subdominio automático para cada camping** (opcional, p. ej.
  `sucamping.campings.tuempresa.com`): crea un registro DNS comodín
  `*.campings.tuempresa.com` de tipo CNAME a `tu-app-campings.fly.dev`, pide el
  certificado comodín con `fly certs add "*.campings.tuempresa.com"` (Fly te
  indicará un registro `_acme-challenge` para validarlo) y activa
  `fly secrets set CAMPING_DOMAIN_SUFFIX=campings.tuempresa.com`. El subdominio
  de cada camping es su «dirección web» de *Ajustes* (sin guiones bajos).
- **Dominio propio de un camping** (p. ej. `www.sucamping.com`):
  1. Escríbelo al crear el camping o en sus *Ajustes* (solo superusuarios).
  2. `fly certs add www.sucamping.com` (y `fly certs add sucamping.com` si
     quieres que el dominio sin `www` redirija a `www`).
  3. El camping crea un CNAME de `www` a `tu-app-campings.fly.dev` (para el
     dominio sin `www`, los registros A y AAAA que muestra `fly ips list`).
  4. Cuando `fly certs show www.sucamping.com` indique que el certificado está
     emitido, abre `https://www.sucamping.com` una vez: esa visita lo activa y
     desde entonces es la dirección oficial del camping. Sus *Ajustes* muestran
     en todo momento si está pendiente o funcionando.

Consulta en la documentación de Fly el precio de los certificados si vas a
gestionar muchos dominios.

## Variables de entorno

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `SECRET_KEY` | — (obligatoria en producción) | Clave secreta de Django. |
| `DEBUG` | `False` | Solo en local. |
| `DATABASE_URL` | SQLite `db.sqlite3` | URL de PostgreSQL. |
| `ALLOWED_HOSTS` | `localhost`, `<app>.fly.dev` | Dominios de la plataforma (separados por comas). Los dominios de los campings no hace falta añadirlos: se leen de la base de datos. |
| `PLATFORM_URL` | `https://<app>.fly.dev` | URL pública de la plataforma (enlaces en correos). |
| `PLATFORM_NAME` | `Campings Suite` | Nombre del producto (panel y crédito «Powered by»). |
| `PLATFORM_CREDIT_URL` | `PLATFORM_URL` | Adónde enlaza el crédito «Powered by» de las webs de los campings. |
| `CAMPING_DOMAIN_SUFFIX` | — | Activa los subdominios automáticos `<camping>.<sufijo>`. |
| `LANGUAGE_CODE` / `TIME_ZONE` | `es` / `Europe/Madrid` | Idioma por defecto y zona horaria. |
| `SIGNUP_ENABLED` | `False` | Permitir que los campings se registren solos (por defecto los creas tú). |
| `SIGNUP_REQUIRES_APPROVAL` | `True` | Con el registro activado, los campings nuevos no son públicos hasta que un superusuario los aprueba. |
| `MEDIA_STORAGE` | `db` en producción, `local` con `DEBUG` | `db`, `s3` o `local`. |
| `BUCKET_NAME` / `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3` / `AWS_S3_ENDPOINT_URL`, `AWS_REGION` / `AWS_S3_REGION_NAME` | — | Bucket S3 compatible. |
| `MEDIA_PUBLIC_DOMAIN` | — | Dominio (y ruta) públicos del bucket, sin `https://`. |
| `MEDIA_LOCATION` | `media` | Prefijo de las fotos dentro del bucket. |
| `MAX_PHOTOS_PER_CAMPING` / `MAX_UPLOAD_MB` | `80` / `20` | Límites de fotos. |
| `IMPORTER_TIME_BUDGET` | `25` | Segundos como máximo para leer la web de un camping. |
| `IMPORTER_ALLOW_PRIVATE_HOSTS` | `False` | Solo para pruebas en local: permite importar desde direcciones privadas. |
| `EMAIL_URL`, `DEFAULT_FROM_EMAIL` | consola | Envío de correos. |
| `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD` | — | Superusuario creado en el despliegue. |
| `DB_TRANSACTION_POOLER` | `False` | Para poolers en modo transacción (Supabase 6543, PgBouncer). |
| `SECURE_HSTS_SECONDS` | `0` | Actívalo cuando el dominio sea definitivo. |

## Idiomas

- **Textos de la interfaz**: están en `locale/<idioma>/LC_MESSAGES/django.po`.
  Tras añadir o cambiar textos:

  ```bash
  python manage.py makemessages -l es -l fr -l de -l nl -l it --ignore=.venv --ignore=tests --no-location
  # traduce los msgstr vacíos
  python manage.py compile_translations     # o compilemessages si tienes gettext
  ```

  Para añadir un idioma nuevo, añádelo a `LANGUAGES` en `config/settings.py` y
  repite los pasos anteriores con su código.
- **Contenidos de cada camping**: cada camping elige en *Ajustes* los idiomas de
  su página y escribe sus textos en pestañas por idioma. Si falta una
  traducción, se muestra el texto en su idioma principal.

## Comandos útiles

| Comando | Qué hace |
| --- | --- |
| `python manage.py seed_demo --owner-password …` | Crea el camping de ejemplo completo y su usuario. |
| `python manage.py ensure_superuser` | Crea el superusuario desde las variables de entorno (idempotente). |
| `python manage.py compile_translations` | Compila las traducciones sin necesidad de gettext. |

## Estructura

```
config/     ajustes, URLs (plataforma y direcciones propias de cada camping), WSGI
core/       campos multiidioma, almacenamiento en BD, imágenes, middleware de direcciones
accounts/   usuario con login por correo
campings/   modelos (camping, fotos, instalaciones, alojamientos, temporadas,
            servicios, políticas), catálogos y motor de precios
bookings/   solicitudes de reserva, formularios y correos
public/     web de cada camping, sitemap y robots
panel/      panel de cada camping y sección de plataforma
importer/   lectura de la web actual de un camping (descarga segura, textos,
            fotos, instalaciones, tablas de precios y fechas)
templates/  plantillas HTML y de correo
static/     CSS, JavaScript e iconos (Lucide, Simple Icons)
locale/     traducciones
tests/      tests automáticos
```
