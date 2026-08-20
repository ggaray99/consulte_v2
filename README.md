# consulte.

Marketplace conversacional de turnos para Argentina. Búsqueda en lenguaje natural sobre negocios indexados desde Google Places + flujo de claim para que el dueño reclame y monetice su perfil.

> v1 (SaaS vertical) vive en el repo hermano `ProyectoClyra/` y quedó archivado en el tag `v1-saas-vertical`. Este es v2.

## Setup (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env  # luego completar valores
python manage.py migrate
python manage.py runserver
```

Abrir http://localhost:8000 — buscador conversacional de turnos. El admin de Django está en `/admin/` (crear superuser con `python manage.py createsuperuser`).

## Estado actual

MVP de las semanas 1-3 completo y con features adicionales encima:

- `places/` — modelo `Place`, ingesta desde Google Places (`python manage.py places_ingest`), detalle con fotos y mapa.
- `search/` — buscador conversacional (HTMX) con extracción de intención vía Claude, caché de intención, rate limiting por IP, ranking multi-señal y logging de búsquedas (`SearchQuery`) para analytics.
- `claim/` — flujo de reclamo por link firmado + email, panel del owner para cargar `ServiceOffering`, y landing B2B en `/para-negocios/`.

Pendiente del plan original: app `accounts/` (hoy el claim usa `django.contrib.auth.User` directo) y adopción de Tailwind (por ahora CSS propio con los tokens de marca).

Ver `CLAUDE.md` para el contexto completo y el roadmap.
