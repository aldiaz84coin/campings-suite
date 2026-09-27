# Campings Suite

Plataforma para gestionar campings. Cada camping tiene un **área privada** desde
la que personaliza su **web pública**: fotos, instalaciones, alojamientos,
precios por temporada, servicios y políticas de reserva. Los visitantes ven un
presupuesto al instante y envían **solicitudes de reserva** que el camping
confirma o rechaza desde su panel.

Todo es **multiidioma** (español, inglés, francés, alemán, neerlandés e italiano)
y está preparado para desplegarse en **Fly.io** con una **base de datos
PostgreSQL gratuita** (Supabase o Neon) y CI/CD con **Buddy**.

## Qué incluye

**Web pública** (`/es/`, `/en/`, `/fr/`…)

- Directorio de campings con buscador, filtro por región y por instalaciones.
- Página de cada camping: portada, galería con visor, alojamientos (capacidad,
  superficie, equipamiento, fotos), instalaciones por categorías, tabla de
  precios por temporada, servicios y extras, políticas de reserva, mapa y
  contacto.
- Formulario de solicitud de reserva con **presupuesto en vivo** (temporadas,
  precio por persona, tasa turística, mascotas, extras opcionales, estancia
  mínima, periodo de apertura y disponibilidad).
- Correos automáticos al camping y al cliente, cada uno en su idioma.
- SEO: `hreflang`, `sitemap.xml`, `robots.txt`, Open Graph y datos
  estructurados schema.org `Campground`.
- **Dominio propio** opcional por camping (`www.micamping.com`).

**Área de cada camping** (`/es/panel/`)

- Panel con lista de pasos para completar la página y últimas solicitudes.
- Descripción y contacto, ubicación (mapa) y periodo de apertura.
- Fotos: subida múltiple desde el móvil (JPG, PNG, WebP, HEIC), conversión
  automática a WebP, orden arrastrando, foto principal y pies de foto por idioma.
- Apariencia: logotipo, colores (con combinaciones sugeridas) y tipografía,
  con vista previa.
- Instalaciones (catálogo de 46 + personalizadas), tipos de alojamiento,
  servicios y extras (siempre cobrados, opcionales o incluidos), temporadas
  (con copia al año siguiente) y **tabla de precios** por temporada.
- Políticas de reserva: horarios, estancia mínima/máxima, depósito, formas de
  pago, cancelación, mascotas y normas.
- Solicitudes de reserva: filtros, detalle, aviso de disponibilidad,
  confirmar/rechazar con correo al cliente.
- Equipo: invitar personas (propietario o personal) con enlace para elegir
  contraseña.
- Ajustes: dirección web, idiomas de la página, moneda y avisos de reservas.

**Plataforma**

- Registro de campings (opcional, con aprobación previa).
- Sección *Plataforma* para superusuarios: todos los campings, alta de un
  camping con su propietario, aprobar/suspender.
- Administración completa de Django en `/superadmin/`.

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

- Web pública: <http://localhost:8000/es/>
- Camping de ejemplo: <http://localhost:8000/es/camping/los-pinos-demo/>
- Área de campings: <http://localhost:8000/es/panel/> (`demo@example.com` / `demo12345`)
- Superadmin: <http://localhost:8000/superadmin/>

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

### 6. Dominios

- **Dominio de la plataforma** (p. ej. `campings.midominio.com`):
  `fly certs add campings.midominio.com`, crea los registros DNS que indica Fly
  y define `ALLOWED_HOSTS` y `PLATFORM_URL`:
  `fly secrets set ALLOWED_HOSTS=campings.midominio.com,tu-app-campings.fly.dev PLATFORM_URL=https://campings.midominio.com`.
- **Dominio propio de un camping** (p. ej. `www.micamping.com`): un superusuario
  lo escribe en *Ajustes* del camping, ejecuta `fly certs add www.micamping.com`
  y el camping crea el registro DNS (CNAME a `tu-app-campings.fly.dev`). La web
  del camping se sirve entonces en la raíz de su dominio (y
  `micamping.com` redirige a `www`).

## Variables de entorno

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `SECRET_KEY` | — (obligatoria en producción) | Clave secreta de Django. |
| `DEBUG` | `False` | Solo en local. |
| `DATABASE_URL` | SQLite `db.sqlite3` | URL de PostgreSQL. |
| `ALLOWED_HOSTS` | `localhost`, `<app>.fly.dev` | Dominios de la plataforma (separados por comas). |
| `PLATFORM_URL` | `https://<app>.fly.dev` | URL pública de la plataforma (enlaces en correos). |
| `PLATFORM_NAME` | `Campings Suite` | Nombre de la plataforma. |
| `LANGUAGE_CODE` / `TIME_ZONE` | `es` / `Europe/Madrid` | Idioma por defecto y zona horaria. |
| `SIGNUP_ENABLED` | `True` | Permitir que los campings se registren solos. |
| `SIGNUP_REQUIRES_APPROVAL` | `True` | Los campings registrados no son públicos hasta que un superusuario los aprueba. |
| `MEDIA_STORAGE` | `db` en producción, `local` con `DEBUG` | `db`, `s3` o `local`. |
| `BUCKET_NAME` / `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3` / `AWS_S3_ENDPOINT_URL`, `AWS_REGION` / `AWS_S3_REGION_NAME` | — | Bucket S3 compatible. |
| `MEDIA_PUBLIC_DOMAIN` | — | Dominio (y ruta) públicos del bucket, sin `https://`. |
| `MEDIA_LOCATION` | `media` | Prefijo de las fotos dentro del bucket. |
| `MAX_PHOTOS_PER_CAMPING` / `MAX_UPLOAD_MB` | `80` / `20` | Límites de fotos. |
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
config/     ajustes, URLs (plataforma y dominios propios), WSGI
core/       campos multiidioma, almacenamiento en BD, imágenes, middleware de dominios
accounts/   usuario con login por correo
campings/   modelos (camping, fotos, instalaciones, alojamientos, temporadas,
            servicios, políticas), catálogos y motor de precios
bookings/   solicitudes de reserva, formularios y correos
public/     web pública, sitemap y robots
panel/      área privada de cada camping y sección de plataforma
templates/  plantillas HTML y de correo
static/     CSS, JavaScript e iconos (Lucide, Simple Icons)
locale/     traducciones
tests/      tests automáticos
```
