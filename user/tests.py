from django.test import TestCase
from django.urls import reverse

from user.models import User


class UserModelTests(TestCase):
    def test_create_user_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="StrongPass123!")

    def test_create_user_sets_hashed_password(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="StrongPass123!",
            name="Tester",
        )
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("StrongPass123!"))

    def test_banned_user_cannot_access_finance_pages(self):
        user = User.objects.create_user(
            email="blocked@example.com",
            password="StrongPass123!",
            name="Blocked",
        )
        self.client.login(username="blocked@example.com", password="StrongPass123!")
        user.is_active = False
        user.save(update_fields=["is_active"])

        response = self.client.get(reverse("finance:transaction_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
