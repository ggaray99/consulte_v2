# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project identity

Product is **consulte.** (lowercase + trailing dot, cobalt `#0047AB`). Domain: `consulte.app`.

**Marketplace conversacional de turnos para Argentina.** Cualquier persona entra a consulte.app, escribe en lenguaje natural lo que necesita ("turno con dentista en Belgrano este viernes"), y el sistema extrae intención (servicio + zona + urgencia) usando Claude API y devuelve negocios reales con disponibilidad. Modelo de negocio: la plataforma se auto-puebla desde Google Places, los negocios reclaman su perfil cuando se cansan de gestionar por WhatsApp, y la monetización viene del lado del negocio (no del cliente final).

Inspiración directa: Roomix (búsqueda con IA de propiedades en Argentina) — mismo modelo, mercado de turnos en vez de inmobiliario.

## Relación con v1

Este es **v2**. El repo hermano `C:\Users\ggaray\Desktop\ProyectoClyra` contiene **v1 (SaaS vertical)** — un producto distinto donde cada profesional tenía su propia landing y agenda en `consulte.app/p/<slug>/`. v1 está archivado en el tag `v1-saas-vertical` y la branch `archive/saas-vertical` de ese repo. No se borra: sirve como referencia para reutilizar tres piezas cuando llegue el momento:

- `core/billing.py` (Mercado Pago preapproval wrapper)
- `core/emails.py` (Resend con patrón no-op-if-unconfigured)
- `core/og.py` (OG images server-side con Pillow + fuentes bundleadas)

La identidad visual (cobalt, Manrope + JetBrains Mono, logo lowercase con `.` separado) se hereda intacta — los assets están en `brand/`. Ver `brand/README.md` para el sistema completo.

## Common commands

PowerShell (Windows es el entorno de desarrollo):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

- Crear superuser: `python manage.py createsuperuser`
- Make migrations: `python manage.py makemigrations <app> && python manage.py migrate`

No hay lint/format tooling configurado. No hay frontend build — la idea inicial es Django templates + HTMX (Tailwind via CDN al principio, build local cuando duela).

## Arquitectura objetivo (lo que viene)

**Actualizado 2026-08-19**: `places/`, `search/` y `claim/` ya están implementadas y en producción (ver Roadmap MVP más abajo para el estado real vs. lo planeado). Esta sección queda como referencia de la arquitectura originalmente objetivo.

### Apps planeadas

- **`places/`** — modelo `Place` (mapea 1:1 a Google `place_id`). Management command `places_ingest` que llama Nearby Search + Place Details y guarda. Caché de 30 días según TdS de Google.
- **`search/`** — endpoint conversacional. Recibe texto, llama a Claude API con prompt de extracción (servicio + zona + urgencia), arma query a Postgres con filtro geográfico (radio) y ranking por rating, devuelve cards.
- **`claim/`** — flujo donde el dueño reclama su `Place`. Verificación (email + eventualmente SMS). Una vez reclamado, puede cargar servicios, fotos propias, horarios.
- **`accounts/`** — usuarios (owners de negocios reclamados). **No implementada** — el claim usa `django.contrib.auth.User` directo, sin modelo de usuario custom.

### Stack

- **Django 5** — config en `consulte/`, apps en raíz.
- **PostgreSQL** — para geo queries usamos `earthdistance` (extensión nativa) o PostGIS si hace falta más potencia. SQLite solo para bootstrap inicial (todavía es lo que corre en local; Postgres vía `DATABASE_URL` solo en Railway).
- **HTMX** — interactividad del buscador conversacional sin SPA. Implementado en `search/index.html`; `claim/` usa forms tradicionales.
- **Tailwind** — ~~vía CDN al principio~~. **No se adoptó**: los templates usan CSS propio con los tokens de marca (`brand/`), inline por template.
- **Claude API** (`anthropic` SDK) — NLP para extracción de intención. Modelo `claude-haiku-4-5-20251001` para velocidad/costo en queries de usuario.
- **Google Places API** (`googlemaps` SDK) — ingesta inicial. ~$25–30 USD para indexar una ciudad mediana; Google da $200/mes free tier.
- **Resend** — email transaccional (claim invitations).
- **WhatsApp** — diferido al MVP completo (semanas 5-6 del roadmap). Probablemente Twilio o YCloud.
- **Cache** — `DatabaseCache` (tabla `consulte_cache`, creada por `manage.py createcachetable` en el release step). Necesario porque el throttle por IP (`consulte/throttle.py`) y la caché de intención (`search/intent.py`) deben compartir estado entre workers de gunicorn; `LocMemCache` (el default de Django) es por-proceso y no sirve ahí.

### Esquema de datos inicial (referencia, no implementado aún)

```
Place
  google_place_id    unique
  name, address, phone, lat, lng
  category           (dentist | hair_care | beauty_salon | ...)
  rating, reviews_count
  hours              JSON
  source             (google | claimed)
  owner              FK User (null hasta que se reclame)
  is_active          (false para soft-delete en re-ingestas)

ServiceOffering      (lo carga el owner tras reclamar)
  place              FK
  name, description, price
  duration_minutes

Booking              (post-MVP — semanas 5-6)
  place              FK
  service            FK ServiceOffering (nullable)
  customer_name, customer_phone
  scheduled_at
  status             (confirmed | cancelled | completed)
```

## Roadmap MVP (semanas 1-3 del brief)

Alcance acordado para v2 inicial. Booking + WhatsApp quedan **fuera** de este MVP.

- **Semana 1** — ✅ App `places/` + management command de ingesta + negocios reales cargados.
- **Semana 2** — ✅ App `search/` + frontend del buscador conversacional con HTMX + integración Claude API + cards de resultado.
- **Semana 3** — ✅ App `claim/` + flujo de email para reclamo + panel mínimo del owner para cargar servicios.

Al final de semana 3: producto deployable en Railway con números reales (visitas, búsquedas, claims) que se pueden mostrar a inversores o usar para outreach.

### Estado real (2026-08-19) — más allá del roadmap escrito

El proyecto avanzó en iteración ad hoc más allá de lo que este documento describía. Además de lo de arriba, ya están en producción:

- **Analytics de búsqueda** — cada búsqueda se loguea en `SearchQuery` (`search/models.py`).
- **Caché de intención** — resultado de Claude cacheado 24h por query normalizada (`search/intent.py`).
- **Rate limiting por IP** — 20/min para el llamado a Claude, 5/hora para el envío de email de claim (`consulte/throttle.py`).
- **Landing B2B** (`/para-negocios/`) — pitch freemium para dueños de negocio, con visión futura de operador con IA sobre WhatsApp (no implementada).
- **Ranking multi-señal** — combina match de texto/servicio, distancia, rating, presupuesto, categoría y bonus por negocio reclamado (`search/views.py`).

Ver `docs/session-2026-05-28-summary.md` para el detalle de la sesión donde se agregaron la landing B2B y el ranking semántico, y `docs/website-service-enrichment.md` para una idea futura (no implementada) de enriquecimiento de servicios por scraping + LLM, pensada como pipeline batch offline.

Pendiente frente al plan original: app `accounts/` y adopción de Tailwind (ver arriba).

## Convenciones

- **Lenguaje**: todo el copy es en español (`LANGUAGE_CODE = 'es-ar'`, `TIME_ZONE = 'America/Argentina/Buenos_Aires'`). Verbose names de modelos en español.
- **No-op-on-missing-env** (heredado de v1): integraciones externas (Anthropic, Google Places, Resend) **no deben crashear** si falta su API key. Devolver fallback amistoso. Esto mantiene el dev server runnable sin secrets.
- **Brand authority**: `brand/README.md` es la fuente de verdad de identidad visual. No reinventes paleta, no metas sombras dramáticas, mantené lowercase + dot del wordmark.
- **Money formatting** (cuando aparezca): ARS estilo argentino (`$ 15.000`, `$ 1.500,50`); USD estilo anglo (`USD 1,200`).

## Deploy

Pensado para Railway, igual que v1. `Procfile` ya está armado: release corre migrate + collectstatic, web corre migrate + gunicorn. Postgres via `DATABASE_URL`. Static files servidos por WhiteNoise. Media uploads requieren Volume montado en `MEDIA_ROOT` cuando aparezcan (fotos propias del owner).

Production env vars necesarias eventualmente: `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, `MEDIA_ROOT`, `ANTHROPIC_API_KEY`, `GOOGLE_PLACES_API_KEY`, `RESEND_API_KEY`, `SITE_BASE_URL`.
