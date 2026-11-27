from django.test import TestCase

# Create your tests here.


from django.contrib.auth.models import User as _User
from django.test import TestCase as _TC


class AdminDashboardTests(_TC):
    def setUp(self):
        self.admin = _User.objects.create_user("boss", password="x-pass-123", is_staff=True)
        self.user = _User.objects.create_user("normal", password="x-pass-123")

    def test_regular_user_cannot_see_dashboard(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/dashboard/").status_code, 404)
        self.assertNotContains(self.client.get("/"), "Admin dashboard")

    def test_staff_sees_dashboard_and_link(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/"), 'href="/dashboard/"')
        r = self.client.get("/dashboard/")
        self.assertContains(r, "Total users")
        self.assertContains(r, "normal")

    def test_toggle_user(self):
        self.client.force_login(self.admin)
        r = self.client.post(f"/dashboard/users/{self.user.pk}/toggle/")
        self.assertEqual(r.json(), {"active": False})
        self.assertEqual(self.client.post(f"/dashboard/users/{self.admin.pk}/toggle/").status_code, 400)
