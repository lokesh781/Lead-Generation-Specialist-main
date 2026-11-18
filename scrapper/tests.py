from django.test import TestCase, Client
from django.urls import reverse

# Create your tests here.

class DashboardViewTest(TestCase):
    def test_dashboard_status_code(self):
        client = Client()
        response = client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
