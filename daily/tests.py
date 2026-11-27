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
        self.assertContains(r, "Admin control")
        self.assertContains(r, "normal")

    def test_toggle_user(self):
        self.client.force_login(self.admin)
        r = self.client.post(f"/dashboard/users/{self.user.pk}/toggle/")
        self.assertEqual(r.json(), {"active": False})
        self.assertEqual(self.client.post(f"/dashboard/users/{self.admin.pk}/toggle/").status_code, 400)


from django.core.files.uploadedfile import SimpleUploadedFile as _Up


class ProfilePhotoTests(_TC):
    JPG = b"\xff\xd8\xff\xe0" + b"0" * 200

    def setUp(self):
        self.u = _User.objects.create_user("pic", password="x-pass-123")
        self.client.force_login(self.u)

    def test_upload_view_remove(self):
        self.assertEqual(self.client.get("/api/photo/").status_code, 404)
        r = self.client.post("/api/photo/", {"photo": _Up("a.jpg", self.JPG, "image/jpeg")})
        self.assertEqual(r.status_code, 200)
        r = self.client.get("/api/photo/")
        self.assertEqual((r.status_code, r["Content-Type"], r.content), (200, "image/jpeg", self.JPG))
        self.assertEqual(self.client.delete("/api/photo/").status_code, 200)
        self.assertEqual(self.client.get("/api/photo/").status_code, 404)

    def test_rejects_non_images_and_big_files(self):
        r = self.client.post("/api/photo/", {"photo": _Up("a.jpg", b"<script>", "image/jpeg")})
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/photo/", {"photo": _Up("a.jpg", self.JPG + b"0" * 400_000, "image/jpeg")})
        self.assertEqual(r.status_code, 400)

    def test_profile_page_has_picker(self):
        self.assertContains(self.client.get("/"), 'id="phFile"')
