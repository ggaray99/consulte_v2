# Website Service Enrichment

Idea a futuro, no implementada todavía.

## Objetivo

Enriquecer negocios ya cargados en `Place` usando la `website` pública del negocio para inferir posibles `ServiceOffering`, mejorar ranking de búsqueda y acelerar onboarding cuando el dueño reclame el perfil.

Esto no reemplaza la carga manual del owner. La fuente de verdad sigue siendo el owner cuando confirma o edita sus servicios.

## Principio de producto

- `Google Places` sigue siendo la fuente de `Place`.
- La web del negocio puede servir para inferir servicios.
- El owner sigue siendo la fuente de verdad final.

Triángulo propuesto:

- `Google -> Place`
- `Website scraping + IA -> inferred services`
- `Owner claim -> confirmed services`

## Uso esperado

Los servicios inferidos se usarían primero para:

- mejorar el ranking de búsqueda
- cubrir negocios no reclamados
- sugerirle al owner servicios detectados cuando reclama

Al inicio no conviene mostrarlos públicamente como si fueran datos confirmados.

## Diseño de datos

Extender `ServiceOffering` con procedencia:

- `source`: `owner`, `website_inferred`, `category_seed`
- `source_url`: URL exacta donde se detectó el servicio
- `confidence`: score de confianza
- `is_verified`: si fue confirmado por owner
- `is_public`: si puede mostrarse públicamente
- `extracted_at`: timestamp de extracción
- `raw_evidence`: JSON con snippet o metadata útil

Reglas:

- `owner` -> `is_verified=True`, `is_public=True`
- `website_inferred` -> `is_verified=False`, `is_public=False` al principio
- `category_seed` -> `is_verified=False`, `is_public=False`

Tabla adicional sugerida:

`WebsiteExtractionJob`

- `place`
- `status`: `pending`, `fetching`, `parsed`, `extracted`, `failed`
- `started_at`, `finished_at`
- `homepage_url`
- `pages_scanned`
- `error`
- `llm_model`
- `token_usage_input`
- `token_usage_output`

## Pipeline propuesto

### 1. Selección

Tomar `Place` con `website` no vacío.

Prioridades:

- primero negocios no reclamados
- evitar reprocesar si ya se extrajo hace poco

### 2. Fetch

Bajar solo:

- homepage
- hasta 2 o 3 links candidatos

Links típicos:

- `servicios`
- `tratamientos`
- `prestaciones`
- `especialidades`
- `menu`
- `precios`
- `cartilla`

### 3. Limpieza

Antes de mandar a IA:

- remover scripts
- remover nav/footer repetido
- convertir HTML a texto limpio
- truncar longitud por página

### 4. Extracción con IA

Usar `Claude Haiku 4.5` para devolver JSON estricto:

- `services[]`
- `name`
- `description`
- `price_text`
- `duration_text`
- `confidence`
- `evidence_snippet`

El prompt debe pedir explícitamente:

- no inventar
- no inferir si no aparece
- devolver baja confianza cuando haya ambigüedad

### 5. Normalización

Normalizar:

- `price_text -> price`
- `duration_text -> duration_minutes`
- deduplicación de servicios similares

### 6. Persistencia

Guardar como `website_inferred`.

Nunca pisar servicios `owner`.

Si el owner reclama luego, su versión debe prevalecer.

## Búsqueda y ranking

Los servicios inferidos pueden entrar al ranking con menos peso que los confirmados por owner.

Pesos sugeridos:

- `owner`: `1.0`
- `website_inferred`: `0.55`
- `category_seed`: `0.25`

## UX para el owner

Cuando un negocio reclama el perfil:

- mostrar “Detectamos estos servicios en tu web”
- permitir `Confirmar`, `Editar` o `Descartar`

Esto convierte el scraping en acelerador de onboarding.

## Infra

No correr esto durante requests web.

Implementación sugerida:

- management command, por ejemplo `extract_website_services`
- ejecución batch/offline
- luego cron/scheduler en Railway

Límites recomendados:

- máximo 3 páginas por dominio
- timeout corto por sitio
- retries limitados
- backoff

## Riesgos

- webs vacías o desactualizadas
- sitios con contenido cargado por JS
- servicios ambiguos
- falsos positivos
- mantenimiento del extractor

Conclusión: usar esto como enriquecimiento, no como verdad pública inicial.

## Estimación de costo IA

Referencia validada el 27 de mayo de 2026:

- Claude Haiku 4.5: `USD 1 / 1M input tokens`
- Claude Haiku 4.5: `USD 5 / 1M output tokens`

Fuentes:

- https://www.anthropic.com/claude/haiku
- https://docs.claude.com/en/docs/about-claude/pricing?selectAccount=true

Estimación para el lote actual de `93` negocios:

### Escenario liviano

- `3k input + 250 output` por negocio
- total: `279k input + 23k output`
- costo estimado: `~USD 0.39`

### Escenario realista

- `6k input + 400 output` por negocio
- total: `558k input + 37k output`
- costo estimado: `~USD 0.74`

### Escenario pesado

- `12k input + 700 output` por negocio
- total: `1.1M input + 65k output`
- costo estimado: `~USD 1.44`

Conclusión práctica:

- con `USD 5` de crédito alcanza para una primera pasada del lote actual
- el costo no parece el cuello de botella principal
- el problema real es calidad de datos y operación del extractor

## Recomendación

Hacerlo en fases:

### Fase 1

- homepage solamente
- extracción batch
- uso interno para ranking

### Fase 2

- seguir 1 o 2 páginas candidatas
- sugerencias al owner en el dashboard

### Fase 3

- refresh periódico
- mostrar algunos inferidos públicamente si la calidad lo justifica
