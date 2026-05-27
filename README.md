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

Abrir http://localhost:8000 — se ve un placeholder. El admin de Django está en `/admin/` (crear superuser con `python manage.py createsuperuser`).

## Estado actual

Scaffold mínimo. Sin apps de negocio todavía. Próximo paso: crear la primera app (`places`) con el modelo `Place` y el management command de ingesta desde Google Places.

Ver `CLAUDE.md` para el contexto completo y el roadmap.
