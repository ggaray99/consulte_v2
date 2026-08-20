# Session Summary — 2026-05-28

## Context

Sesión enfocada en dos frentes:

- mejorar la búsqueda para que use mejor el lenguaje natural del usuario
- construir la landing B2B de `consulte.` para dueños que quieren reclamar su perfil

También se dejó documentada una idea futura de enriquecimiento por scraping de webs.

## Cambios de producto y UX

### 1. Landing B2B para negocios

Se creó la página `/para-negocios/` como recorrido para dueños/profesionales.

Objetivo:

- mostrar la propuesta freemium de `consulte.`
- explicar el modelo de negocio futuro
- conectar el claim del perfil con la visión de operador con IA

Piezas creadas:

- ruta nueva en `claim/urls.py`
- vista nueva `claim_offer` en `claim/views.py`
- template nuevo `claim/templates/claim/offer.html`

La landing comunica:

- capa gratuita: reclamar perfil, cargar servicios, ganar visibilidad
- capa paga futura: operador con IA, WhatsApp, leads, seguimiento, automatización

### 2. CTA desde la home

Se agregó un botón en el header de la home del buscador que lleva a `/para-negocios/`.

Importante:

- se probó una card/promoción extra debajo del buscador
- después se decidió removerla
- quedó solo el botón del header

Estado final:

- home con CTA limpio arriba
- sin card intermedia antes de los filtros

## Cambios en búsqueda

Se mejoró el comportamiento del buscador para que no use la IA solo como parser de categoría.

### 1. Extracción de intención más rica

En `search/intent.py` se agregó extracción de:

- `ranking`
- `budget`

Además de lo que ya existía:

- `category`
- `zone`
- `urgency`
- `raw_service`

La idea fue que frases como:

- `veterinaria cerca`
- `limpieza dental barata en belgrano`
- `mejor dentista en palermo`

influyan en el orden de los resultados.

### 2. Ranking más semántico

En `search/views.py` se ajustó el ranking para considerar:

- match de texto con `raw_service`
- coincidencias contra `ServiceOffering`
- cercanía
- calidad / reputación
- precio cuando la consulta sugiere sensibilidad a presupuesto
- categoría detectada
- bonus por negocio reclamado

### 3. Resultados con señal visible

En `search/templates/search/_results.html` se agregó una pista tipo:

- `Servicio relevante: ...`

para mostrar por qué un negocio apareció alto en el ranking.

## Documentación de idea futura

Se creó:

- `docs/website-service-enrichment.md`

La nota describe una idea futura para:

- scrapear la web pública del negocio
- pasar ese contenido por IA
- inferir servicios
- usarlos primero para ranking interno y luego como sugerencias al owner

Conclusión de esa discusión:

- sirve como enriquecimiento
- no conviene usarlo como fuente de verdad pública inicial
- el owner debe seguir siendo la fuente final de servicios confirmados

También se estimó costo de IA para el lote actual.

## Estimación de costo discutida

Con `Claude Haiku 4.5`, para alrededor de `93` negocios:

- escenario liviano: ~`USD 0.39`
- escenario realista: ~`USD 0.74`
- escenario pesado: ~`USD 1.44`

Conclusión:

- `USD 5` de crédito alcanzan para un primer piloto
- el cuello de botella no parece ser costo de tokens
- el riesgo principal es calidad/operación del extractor

## Validaciones hechas

Durante la sesión se corrieron checks y tests:

- `python manage.py test search`
- `python manage.py test claim`
- `python manage.py check`

Todos quedaron pasando al momento de cerrar los cambios.

## Git / deploy

Se hicieron push a `main` para disparar deploy automático en Railway.

Commits relevantes de la sesión:

- `7a6115e` — `Add business offer landing and improve natural-language search`
- `8efd5c9` — `Remove owner promo card from search home`

## Estado conceptual alcanzado

`consulte.` quedó mejor definido como:

- búsqueda conversacional para usuarios
- claim del perfil como wedge de adquisición de oferta
- visión freemium para negocios
- futura capa paga de operador con IA sobre WhatsApp / leads / seguimiento

## Próximos pasos sugeridos

### Corto plazo

- revisar visualmente `/para-negocios/` ya deployado en Railway
- ajustar copy/comercialidad de la landing si hace falta
- decidir si la landing debe incluir CTA más directo a “buscar mi negocio”

### Producto

- pasar la búsqueda a un modelo donde `ServiceOffering` sea entidad principal de retrieval
- dejar `Place` como contexto/fallback
- luego aprovechar Postgres para full-text search real

### B2B

- definir qué analytics básicas debería ver el dueño cuando reclama
- decidir qué promesa “gratis” se quiere sostener públicamente hoy
- bajar la oferta futura de IA a una propuesta más concreta

### Infra futura

- si avanza la idea de enriquecimiento por web, crear pipeline batch offline
- no correr scraping/LLM en requests web

## Archivos tocados o creados en la sesión

- `claim/templates/claim/offer.html`
- `claim/urls.py`
- `claim/views.py`
- `claim/tests.py`
- `search/intent.py`
- `search/views.py`
- `search/tests.py`
- `search/templates/search/_results.html`
- `search/templates/search/index.html`
- `docs/website-service-enrichment.md`

