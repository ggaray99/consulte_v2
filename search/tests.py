from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from claim.models import ServiceOffering
from places.models import Place
from search.intent import extract_intent
from search.models import SearchQuery


@override_settings(ANTHROPIC_API_KEY='')
class IntentExtractionTests(TestCase):
    def test_fallback_extracts_budget_and_ranking(self):
        intent = extract_intent('busco un dentista barato cerca de casa')

        self.assertEqual(intent['category'], Place.Category.DENTIST)
        self.assertEqual(intent['budget'], 'cheap')
        self.assertEqual(intent['ranking'], 'nearby')


FAKE_CLAUDE_INTENT = {
    'category': Place.Category.DENTIST.value,
    'zone': 'belgrano',
    'urgency': 'normal',
    'raw_service': 'limpieza dental',
    'ranking': 'recommended',
    'budget': 'any',
    'engine': 'claude',
}


@override_settings(ANTHROPIC_API_KEY='test-key')
class IntentCacheTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_claude_intent_is_cached_per_normalized_query(self):
        with mock.patch(
            'search.intent._extract_with_claude',
            return_value=dict(FAKE_CLAUDE_INTENT),
        ) as extract:
            first = extract_intent('Limpieza dental en Belgrano')
            second = extract_intent('limpieza dental en belgrano')

        self.assertEqual(extract.call_count, 1)
        self.assertEqual(first, second)
        self.assertEqual(second['engine'], 'claude')

    def test_use_llm_false_skips_claude_but_reads_cache(self):
        with mock.patch(
            'search.intent._extract_with_claude',
            return_value=dict(FAKE_CLAUDE_INTENT),
        ) as extract:
            extract_intent('dentista en belgrano')
            cached = extract_intent('dentista en belgrano', use_llm=False)
            uncached = extract_intent('peluqueria en palermo', use_llm=False)

        self.assertEqual(extract.call_count, 1)
        self.assertEqual(cached['engine'], 'claude')
        self.assertEqual(uncached['engine'], 'fallback')


@override_settings(ANTHROPIC_API_KEY='')
class SearchQueryLoggingTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_search_with_query_is_logged(self):
        response = self.client.get('/', {'q': 'dentista barato en belgrano'})

        self.assertEqual(response.status_code, 200)
        log = SearchQuery.objects.get()
        self.assertEqual(log.query, 'dentista barato en belgrano')
        self.assertEqual(log.engine, 'fallback')
        self.assertEqual(log.category, Place.Category.DENTIST.value)
        self.assertEqual(log.zone, 'belgrano')
        self.assertEqual(log.budget, 'cheap')
        self.assertEqual(log.results_count, 0)
        self.assertFalse(log.has_coords)

    def test_filter_only_search_is_logged(self):
        self.client.get('/', {'category': Place.Category.DENTIST.value})

        log = SearchQuery.objects.get()
        self.assertEqual(log.query, '')
        self.assertEqual(log.engine, '')

    def test_empty_home_is_not_logged(self):
        self.client.get('/')

        self.assertEqual(SearchQuery.objects.count(), 0)


@override_settings(ANTHROPIC_API_KEY='test-key')
class SearchLlmThrottleTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_llm_use_is_throttled_per_ip(self):
        with mock.patch(
            'search.intent._extract_with_claude',
            return_value=dict(FAKE_CLAUDE_INTENT),
        ) as extract, mock.patch('search.views.LLM_THROTTLE_LIMIT', 2):
            # Queries distintas para que el cache de intents no absorba las llamadas.
            self.client.get('/', {'q': 'dentista en belgrano'})
            self.client.get('/', {'q': 'peluqueria en palermo'})
            self.client.get('/', {'q': 'veterinaria en caballito'})

        self.assertEqual(extract.call_count, 2)
        third = SearchQuery.objects.order_by('created_at').last()
        self.assertEqual(third.engine, 'fallback')


@override_settings(ANTHROPIC_API_KEY='')
class SearchRankingTests(TestCase):
    def setUp(self):
        self.client = Client()
        cache.clear()

    def test_matching_service_ranks_above_generic_place(self):
        generic = Place.objects.create(
            google_place_id='generic-dentist',
            name='Centro Odontologico Norte',
            address='Av. Cabildo 2100, Palermo, CABA',
            category=Place.Category.DENTIST,
            rating=4.9,
            reviews_count=400,
            is_active=True,
        )
        matching = Place.objects.create(
            google_place_id='matching-dentist',
            name='Dental Palermo Studio',
            address='Honduras 4100, Palermo, CABA',
            category=Place.Category.DENTIST,
            rating=4.5,
            reviews_count=80,
            source=Place.Source.CLAIMED,
            is_active=True,
        )
        ServiceOffering.objects.create(
            place=matching,
            name='Blanqueamiento dental',
            description='Sesion estetica con control previo.',
            price=25000,
            is_active=True,
        )

        response = self.client.get('/', {'q': 'blanqueamiento dental en palermo'})
        results = response.context['results']

        self.assertEqual(results[0].id, matching.id)
        self.assertEqual(results[1].id, generic.id)
        self.assertEqual(results[0].match_reason, 'Blanqueamiento dental')

    def test_budget_query_prefers_cheaper_matching_service(self):
        cheaper = Place.objects.create(
            google_place_id='cheap-dentist',
            name='Dental Belgrano Base',
            address='Av. Cabildo 1500, Belgrano, CABA',
            category=Place.Category.DENTIST,
            rating=4.4,
            reviews_count=120,
            source=Place.Source.CLAIMED,
            is_active=True,
        )
        expensive = Place.objects.create(
            google_place_id='expensive-dentist',
            name='Dental Belgrano Premium',
            address='Ciudad de la Paz 1800, Belgrano, CABA',
            category=Place.Category.DENTIST,
            rating=4.8,
            reviews_count=220,
            source=Place.Source.CLAIMED,
            is_active=True,
        )
        ServiceOffering.objects.create(
            place=cheaper,
            name='Limpieza dental',
            description='Consulta y limpieza simple.',
            price=15000,
            is_active=True,
        )
        ServiceOffering.objects.create(
            place=expensive,
            name='Limpieza dental',
            description='Consulta y limpieza premium.',
            price=42000,
            is_active=True,
        )

        response = self.client.get('/', {'q': 'limpieza dental barata en belgrano'})
        results = response.context['results']

        self.assertEqual(results[0].id, cheaper.id)
        self.assertEqual(results[1].id, expensive.id)

    def test_query_can_auto_sort_by_distance(self):
        farther = Place.objects.create(
            google_place_id='far-vet',
            name='Vet Lejana',
            address='Av. Libertador 6000, Belgrano, CABA',
            category=Place.Category.VETERINARY_CARE,
            rating=4.9,
            reviews_count=500,
            lat=-34.5600,
            lng=-58.4500,
            is_active=True,
        )
        nearer = Place.objects.create(
            google_place_id='near-vet',
            name='Vet Cerca',
            address='Migueletes 1000, Belgrano, CABA',
            category=Place.Category.VETERINARY_CARE,
            rating=4.2,
            reviews_count=30,
            lat=-34.5622,
            lng=-58.4442,
            is_active=True,
        )

        response = self.client.get('/', {
            'q': 'veterinaria cerca',
            'lat': -34.5620,
            'lng': -58.4440,
        })
        results = response.context['results']

        self.assertEqual(results[0].id, nearer.id)
        self.assertEqual(results[1].id, farther.id)
        self.assertEqual(response.context['sort'], 'nearby')
