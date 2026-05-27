"""
Ingest businesses from Google Places into the local Place table.

Idempotent by google_place_id. Respects a 30-day cache per Google's ToS:
places ingested within the window are skipped unless --force.
"""

import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from places.models import Place


CATEGORY_MAP = {
    'dentist': Place.Category.DENTIST,
    'hair_care': Place.Category.HAIR_CARE,
    'beauty_salon': Place.Category.BEAUTY_SALON,
    'doctor': Place.Category.DOCTOR,
    'physiotherapist': Place.Category.PHYSIOTHERAPIST,
    'veterinary_care': Place.Category.VETERINARY_CARE,
    'spa': Place.Category.SPA,
}

CACHE_TTL_DAYS = 30

# Google requires a short delay before next_page_token becomes valid.
NEARBY_PAGE_DELAY_SECONDS = 2

DETAIL_FIELDS = [
    'name',
    'formatted_address',
    'formatted_phone_number',
    'geometry/location',
    'rating',
    'user_ratings_total',
    'opening_hours',
    'business_status',
]


FAKE_SEED = [
    {
        'google_place_id': 'fake_dentist_belgrano_1',
        'name': 'Clínica Dental Belgrano',
        'address': 'Av. Cabildo 2500, Belgrano, CABA',
        'phone': '+54 11 4783-0000',
        'lat': -34.5610, 'lng': -58.4570,
        'category': Place.Category.DENTIST,
        'rating': 4.6, 'reviews_count': 124,
    },
    {
        'google_place_id': 'fake_peluqueria_palermo_1',
        'name': 'Estudio Palermo Hair',
        'address': 'Honduras 5200, Palermo, CABA',
        'phone': '+54 11 4831-0000',
        'lat': -34.5870, 'lng': -58.4290,
        'category': Place.Category.HAIR_CARE,
        'rating': 4.8, 'reviews_count': 312,
    },
    {
        'google_place_id': 'fake_vet_caballito_1',
        'name': 'Veterinaria Caballito 24h',
        'address': 'Av. Rivadavia 5000, Caballito, CABA',
        'phone': '+54 11 4902-0000',
        'lat': -34.6190, 'lng': -58.4400,
        'category': Place.Category.VETERINARY_CARE,
        'rating': 4.4, 'reviews_count': 87,
    },
    {
        'google_place_id': 'fake_kine_recoleta_1',
        'name': 'Centro Kinesiología Recoleta',
        'address': 'Av. Las Heras 2100, Recoleta, CABA',
        'phone': '+54 11 4801-0000',
        'lat': -34.5870, 'lng': -58.3950,
        'category': Place.Category.PHYSIOTHERAPIST,
        'rating': 4.7, 'reviews_count': 56,
    },
    {
        'google_place_id': 'fake_spa_nunez_1',
        'name': 'Spa Núñez Wellness',
        'address': 'Av. del Libertador 7800, Núñez, CABA',
        'phone': '+54 11 4702-0000',
        'lat': -34.5450, 'lng': -58.4620,
        'category': Place.Category.SPA,
        'rating': 4.5, 'reviews_count': 41,
    },
]


class Command(BaseCommand):
    help = 'Ingesta de negocios desde Google Places.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--city', default='Buenos Aires',
            help='Ciudad objetivo (default: Buenos Aires).',
        )
        parser.add_argument(
            '--category', default='dentist',
            choices=list(CATEGORY_MAP.keys()),
            help='Categoría a ingestar.',
        )
        parser.add_argument(
            '--radius', type=int, default=5000,
            help='Radio de búsqueda en metros (default: 5000).',
        )
        parser.add_argument(
            '--max', type=int, default=60, dest='max_results',
            help='Máximo de negocios a procesar (Google limita Nearby a 60).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Imprime el plan sin llamar a Google ni escribir en DB.',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Ignora el caché de 30 días y re-ingesta todo.',
        )
        parser.add_argument(
            '--seed-fake', action='store_true',
            help='Carga negocios de ejemplo (no llama a Google). Útil para UI local.',
        )

    def handle(self, *args, **opts):
        if opts['seed_fake']:
            return self._seed_fake()

        city = opts['city']
        category_key = opts['category']
        radius = opts['radius']
        max_results = opts['max_results']
        dry_run = opts['dry_run']
        force = opts['force']

        api_key = settings.GOOGLE_PLACES_API_KEY
        api_key_display = f'***{api_key[-4:]}' if api_key else '(no configurada)'

        self.stdout.write(self.style.NOTICE(
            f'Plan:\n'
            f'  city     = {city}\n'
            f'  category = {category_key}\n'
            f'  radius   = {radius} m\n'
            f'  max      = {max_results}\n'
            f'  force    = {force}\n'
            f'  api_key  = {api_key_display}'
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '\n[dry-run] No se hicieron llamadas a Google ni cambios en DB.'
            ))
            return

        if not api_key:
            self.stdout.write(self.style.WARNING(
                '\nGOOGLE_PLACES_API_KEY no configurada. Saliendo sin error '
                '(no-op-if-unconfigured). Usá --seed-fake para datos de prueba.'
            ))
            return

        try:
            import googlemaps
        except ImportError as e:
            raise CommandError(f'googlemaps SDK no instalado: {e}')

        client = googlemaps.Client(key=api_key)

        center = self._geocode_city(client, city)
        self.stdout.write(
            f'Centro: {center[0]:.4f}, {center[1]:.4f} ({city})'
        )

        place_ids = self._collect_nearby_place_ids(
            client, center, radius, category_key, max_results
        )
        self.stdout.write(f'Nearby Search devolvió {len(place_ids)} candidatos.\n')

        self._process_place_ids(client, place_ids, category_key, force)

    def _geocode_city(self, client, city):
        query = f'{city}, Argentina'
        try:
            results = client.geocode(query)
        except Exception as e:
            raise CommandError(f'Error geocodificando "{query}": {e}')
        if not results:
            raise CommandError(f'No se encontró la ciudad "{query}".')
        loc = results[0]['geometry']['location']
        return (loc['lat'], loc['lng'])

    def _collect_nearby_place_ids(self, client, center, radius, category_key, max_results):
        ids = []
        next_token = None
        while len(ids) < max_results:
            if next_token:
                time.sleep(NEARBY_PAGE_DELAY_SECONDS)
                kwargs = {'page_token': next_token}
            else:
                kwargs = {
                    'location': center,
                    'radius': radius,
                    'type': category_key,
                }
            try:
                resp = client.places_nearby(**kwargs)
            except Exception as e:
                self.stderr.write(f'Error en Nearby Search: {e}')
                break
            for r in resp.get('results', []):
                ids.append(r['place_id'])
                if len(ids) >= max_results:
                    break
            next_token = resp.get('next_page_token')
            if not next_token:
                break
        return ids

    def _process_place_ids(self, client, place_ids, category_key, force):
        category_value = CATEGORY_MAP[category_key]
        now = timezone.now()
        cached_cutoff = now - timedelta(days=CACHE_TTL_DAYS)

        created = updated = skipped = failed = closed = 0

        for pid in place_ids:
            existing = Place.objects.filter(google_place_id=pid).first()
            if (
                existing
                and not force
                and existing.last_ingested_at
                and existing.last_ingested_at >= cached_cutoff
            ):
                skipped += 1
                continue

            try:
                details = client.place(
                    place_id=pid,
                    fields=DETAIL_FIELDS,
                    language='es',
                ).get('result', {})
            except Exception as e:
                self.stderr.write(f'  Details falló para {pid}: {e}')
                failed += 1
                continue

            if details.get('business_status') == 'CLOSED_PERMANENTLY':
                if existing:
                    existing.is_active = False
                    existing.save(update_fields=['is_active', 'updated_at'])
                closed += 1
                continue

            loc = details.get('geometry', {}).get('location', {})
            opening = details.get('opening_hours') or {}
            hours_json = {
                'weekday_text': opening.get('weekday_text', []),
                'periods': opening.get('periods', []),
            } if opening else {}

            defaults = {
                'name': (details.get('name') or '')[:255],
                'address': (details.get('formatted_address') or '')[:500],
                'phone': (details.get('formatted_phone_number') or '')[:50],
                'lat': loc.get('lat'),
                'lng': loc.get('lng'),
                'category': category_value,
                'rating': details.get('rating'),
                'reviews_count': details.get('user_ratings_total') or 0,
                'hours': hours_json,
                'source': Place.Source.GOOGLE,
                'is_active': True,
                'last_ingested_at': now,
            }

            obj, was_created = Place.objects.update_or_create(
                google_place_id=pid,
                defaults=defaults,
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  + {obj.name}'))
            else:
                updated += 1
                self.stdout.write(f'  ~ {obj.name}')

        self.stdout.write(self.style.SUCCESS(
            f'\nIngesta completa:\n'
            f'  creados        : {created}\n'
            f'  actualizados   : {updated}\n'
            f'  en caché       : {skipped}\n'
            f'  cerrados (off) : {closed}\n'
            f'  fallaron       : {failed}'
        ))

    def _seed_fake(self):
        created, updated = 0, 0
        now = timezone.now()
        for data in FAKE_SEED:
            _, was_created = Place.objects.update_or_create(
                google_place_id=data['google_place_id'],
                defaults={
                    **{k: v for k, v in data.items() if k != 'google_place_id'},
                    'source': Place.Source.GOOGLE,
                    'is_active': True,
                    'last_ingested_at': now,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f'Seed listo: {created} creado(s), {updated} actualizado(s). '
            f'Visitá /places/ para verlos.'
        ))
