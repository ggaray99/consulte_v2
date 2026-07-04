from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from places.models import Place


class ClaimOfferTests(TestCase):
    def test_offer_page_loads_with_network_counts(self):
        Place.objects.create(
            google_place_id='offer-place-1',
            name='Clinica Norte',
            category=Place.Category.DENTIST,
            is_active=True,
        )

        response = self.client.get('/para-negocios/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Perfil verificado')
        self.assertEqual(response.context['total_places'], 1)
        self.assertEqual(response.context['claimed_places'], 0)

    def test_search_home_has_claim_offer_cta(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/para-negocios/')


class ClaimThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.place = Place.objects.create(
            google_place_id='throttle-place-1',
            name='Clinica Sur',
            category=Place.Category.DENTIST,
            is_active=True,
        )

    def test_claim_email_is_throttled_per_ip(self):
        url = f'/reclamar/{self.place.id}/'

        with mock.patch('claim.views.CLAIM_THROTTLE_LIMIT', 2), \
                mock.patch('claim.views.send_claim_invitation', return_value=True) as send:
            first = self.client.post(url, {'email': 'uno@example.com'})
            second = self.client.post(url, {'email': 'dos@example.com'})
            third = self.client.post(url, {'email': 'tres@example.com'})

        self.assertEqual(send.call_count, 2)
        self.assertTemplateUsed(first, 'claim/sent.html')
        self.assertTemplateUsed(second, 'claim/sent.html')
        self.assertTemplateUsed(third, 'claim/start.html')
        self.assertContains(third, 'Demasiados intentos')
