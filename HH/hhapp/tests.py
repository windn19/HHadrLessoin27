from django.test import TestCase, Client
from django.urls import reverse
from mixer.backend.django import mixer

from .models import Area
from userapp.models import Applicant


class TestViews(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        # self.area_queryset = mixer.cycle(10).blend(Area)
        # self.area_test = Area(name='Екатеринбург', ind_hh=3, ind_zarp=3, ind_super=33)

    # def test_index(self):
    #     res = self.client.get(reverse('hh:index'))
    #     self.assertEqual(res.status_code, 200)
    #
    # def test_area(self):
    #     res = self.client.get(reverse('hh:area_list'))
    #     self.assertEqual(res.status_code, 200)

    # def test_area_create(self):
    #     area = Area(name='Екатеринбург', ind_hh=3, ind_zarp=3, ind_super=33)
    #     self.assertEqual(self.area_test, area)

    def test_area_cr(self):
        # res = self.client.post(reverse('hh:area_create'), {'name': 'Екатеринбург'})
        # self.assertNotEqual(res.status_code, 200)

        Applicant.objects.create_user(username='test_user', email='test@test.ru', password='test11111')
        print(self.client.login(username='test_user', password='test11111'))

        # res = self.client.post(reverse('hh:area_create'), {'name': 'Екатеринбург'})
        # ar = Area.objects.get(name='Екатеринбург')
        ar = self.client.get(reverse('hh:area_create'))
        print(ar.status_code)
        self.assertEqual(ar.status_code, 200)
        # self.assertEqual(self.area_test, ar)

