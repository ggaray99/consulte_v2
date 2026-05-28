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
