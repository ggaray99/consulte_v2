"""
Extract structured search intent from a natural-language query.

Primary path: Claude Haiku 4.5 with a cacheable system prompt.
Fallback (no API key or API failure): keyword matching against a small
dictionary so the dev server is usable without secrets.
"""

import hashlib
import json
import logging
import re
import unicodedata

from django.conf import settings
from django.core.cache import cache

from places.models import Place

logger = logging.getLogger(__name__)

CLAUDE_MODEL = 'claude-haiku-4-5-20251001'

# Las queries reales se repiten mucho ("dentista en belgrano"); cachear el
# intent extraído por Claude ahorra latencia y costo de API. Solo se cachean
# resultados de Claude — el fallback es gratis y no vale la pena persistirlo.
INTENT_CACHE_TTL = 60 * 60 * 24  # 24 horas

VALID_CATEGORIES = {c.value for c in Place.Category}

SYSTEM_PROMPT = """Sos un asistente que extrae intención de búsqueda para un marketplace de turnos en Argentina llamado consulte.

Dada una consulta del usuario en español, devolvé EXCLUSIVAMENTE un objeto JSON (sin markdown, sin explicación) con esta forma:

{
  "category": "dentist" | "hair_care" | "beauty_salon" | "doctor" | "physiotherapist" | "veterinary_care" | "spa" | "other",
  "zone": "<barrio o zona mencionada en la consulta, en minúsculas y sin tildes, o null si no hay>",
  "urgency": "urgent" | "normal",
  "raw_service": "<descripción corta del servicio en las palabras del usuario, máx 60 chars>",
  "ranking": "recommended" | "nearby" | "best" | "popular",
  "budget": "any" | "cheap" | "premium"
}

Reglas:
- "category" debe ser exactamente uno de los valores listados.
- "urgent" sólo si el usuario menciona urgencia explícita (hoy, ya, urgente, ahora, lo antes posible).
- "zone" en minúsculas y sin acentos (ej: "palermo", "belgrano", "villa crespo").
- "ranking" debe ser "nearby" si el usuario prioriza cercanía ("cerca", "por mi zona", "al lado"), "best" si prioriza calidad ("mejor", "muy bueno", "top"), "popular" si prioriza reputación masiva ("muchas reviews", "popular"), y "recommended" en cualquier otro caso.
- "budget" debe ser "cheap" si busca precio bajo ("barato", "económico"), "premium" si busca gama alta ("premium", "mejor lugar", "alta gama"), y "any" si no hay señal clara de precio.
- Si no entendés algo, usá "other" para category y null para zone.
"""

KEYWORD_CATEGORY_MAP = [
    (Place.Category.DENTIST, [
        'dentista', 'odonto', 'diente', 'dientes', 'muela', 'muelas',
        'caries', 'ortodoncia', 'blanqueamiento',
    ]),
    (Place.Category.HAIR_CARE, [
        'peluqueria', 'peluquero', 'peluquera', 'corte', 'pelo',
        'cabello', 'tinte', 'mechas',
    ]),
    (Place.Category.BEAUTY_SALON, [
        'estetica', 'salon de belleza', 'manicura', 'manicuria', 'pedicura',
        'depilacion', 'maquillaje', 'unas', 'cejas',
    ]),
    (Place.Category.DOCTOR, [
        'doctor', 'medico', 'medica', 'clinica medica', 'consultorio',
        'pediatra', 'ginecologo', 'cardiologo', 'dermatologo',
    ]),
    (Place.Category.PHYSIOTHERAPIST, [
        'kinesio', 'kinesiologo', 'kinesiologa', 'fisio', 'fisioterapia',
        'rehabilitacion',
    ]),
    (Place.Category.VETERINARY_CARE, [
        'veterinaria', 'veterinario', 'vet', 'mascota', 'perro', 'gato',
    ]),
    (Place.Category.SPA, [
        'spa', 'masaje', 'masajes', 'relax', 'termas',
    ]),
]

URGENT_KEYWORDS = {
    'urgente', 'urgencia', 'ya', 'hoy', 'ahora', 'apurado', 'rapido',
    'lo antes posible', 'cuanto antes',
}

RANKING_KEYWORDS = {
    'nearby': {
        'cerca', 'cercano', 'cercana', 'por mi zona', 'al lado', 'a unas cuadras',
        'cerca mio', 'cerca mio', 'cerca de casa',
    },
    'best': {
        'mejor', 'mejores', 'muy bueno', 'muy buena', 'top', 'excelente',
        'recomendado', 'recomendados',
    },
    'popular': {
        'popular', 'muchas reviews', 'muchas resenas', 'muchas opiniones',
        'con muchas reviews', 'famoso',
    },
}

BUDGET_KEYWORDS = {
    'cheap': {
        'barato', 'barata', 'baratos', 'baratas', 'economico', 'economica',
        'accesible', 'precio bajo', 'mas barato', 'mas barata',
    },
    'premium': {
        'premium', 'alta gama', 'caro', 'cara', 'mejor lugar', 'de lujo',
    },
}

# CABA neighborhoods we care to detect in the fallback path.
KNOWN_ZONES = [
    'belgrano', 'palermo', 'recoleta', 'caballito', 'nunez', 'villa crespo',
    'almagro', 'flores', 'colegiales', 'chacarita', 'san telmo', 'barracas',
    'la boca', 'puerto madero', 'retiro', 'balvanera', 'monserrat',
    'villa urquiza', 'devoto', 'saavedra', 'boedo', 'parque chas',
    'villa devoto', 'mataderos', 'liniers',
]


def _strip_accents(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )


def _normalize(s):
    return _strip_accents(s.lower()).strip()


def _parse_json_block(text):
    """Parse a JSON object even if wrapped in markdown fences or prose."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        raise ValueError('no JSON object found in response')
    return json.loads(match.group(0))


def extract_intent(query, *, use_llm=True):
    """Return a dict with category, zone, urgency, raw_service.

    `use_llm=False` saltea Claude (throttle de costo) y usa el fallback,
    pero sigue aprovechando intents ya cacheados.
    """
    query = (query or '').strip()
    if not query:
        return _empty_intent()

    cache_key = _intent_cache_key(query)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    if use_llm and settings.ANTHROPIC_API_KEY:
        intent = _extract_with_claude(query)
        if intent is not None:
            cache.set(cache_key, intent, INTENT_CACHE_TTL)
            return intent

    return _extract_fallback(query)


def _intent_cache_key(query):
    digest = hashlib.md5(_normalize(query).encode('utf-8')).hexdigest()
    return f'search:intent:{digest}'


def _empty_intent():
    return {
        'category': Place.Category.OTHER.value,
        'zone': None,
        'urgency': 'normal',
        'raw_service': '',
        'ranking': 'recommended',
        'budget': 'any',
        'engine': 'empty',
    }


def _extract_with_claude(query):
    try:
        import anthropic
    except ImportError:
        return None

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            system=[
                {
                    'type': 'text',
                    'text': SYSTEM_PROMPT,
                    'cache_control': {'type': 'ephemeral'},
                }
            ],
            messages=[{'role': 'user', 'content': query}],
        )
        text = resp.content[0].text.strip()
        data = _parse_json_block(text)
    except Exception as e:
        logger.warning('Claude intent extraction failed: %s', e)
        return None

    category = data.get('category')
    if category not in VALID_CATEGORIES:
        category = Place.Category.OTHER.value

    zone = data.get('zone')
    if zone:
        zone = _normalize(str(zone))
    else:
        zone = None

    urgency = data.get('urgency') if data.get('urgency') in ('urgent', 'normal') else 'normal'
    raw_service = (data.get('raw_service') or query)[:60]
    ranking = data.get('ranking') if data.get('ranking') in ('recommended', 'nearby', 'best', 'popular') else 'recommended'
    budget = data.get('budget') if data.get('budget') in ('any', 'cheap', 'premium') else 'any'

    return {
        'category': category,
        'zone': zone,
        'urgency': urgency,
        'raw_service': raw_service,
        'ranking': ranking,
        'budget': budget,
        'engine': 'claude',
    }


def _extract_fallback(query):
    norm = _normalize(query)

    category = Place.Category.OTHER.value
    for cat, keywords in KEYWORD_CATEGORY_MAP:
        if any(kw in norm for kw in keywords):
            category = cat.value
            break

    zone = None
    for z in KNOWN_ZONES:
        if re.search(rf'\b{re.escape(z)}\b', norm):
            zone = z
            break

    urgency = 'urgent' if any(kw in norm for kw in URGENT_KEYWORDS) else 'normal'
    ranking = 'recommended'
    for value in ('nearby', 'best', 'popular'):
        if any(kw in norm for kw in RANKING_KEYWORDS[value]):
            ranking = value
            break

    budget = 'any'
    for value in ('cheap', 'premium'):
        if any(kw in norm for kw in BUDGET_KEYWORDS[value]):
            budget = value
            break

    return {
        'category': category,
        'zone': zone,
        'urgency': urgency,
        'raw_service': query[:60],
        'ranking': ranking,
        'budget': budget,
        'engine': 'fallback',
    }
