import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import app as portfolio_app


class PortfolioAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database = portfolio_app.DATABASE
        portfolio_app.DATABASE = Path(self.temp_dir.name) / "test.db"
        portfolio_app.init_db()
        portfolio_app.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, ADMIN_PASSWORD=None)
        self.client = portfolio_app.app.test_client()

    def tearDown(self):
        portfolio_app.DATABASE = self.original_database
        self.temp_dir.cleanup()

    def test_home_renders_seeded_portfolio(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your work,", response.data)
        self.assertIn(b"Forma", response.data)
        self.assertIn(b"data-copy-link=\"http://localhost/p/alex-morgan\"", response.data)
        self.assertIn(b"Copy link", response.data)

    def test_editor_updates_profile_and_public_page(self):
        response = self.client.post("/edit", data={
            "name": "Taylor Reed", "title": "Illustrator", "bio": "Drawing useful things.",
            "email": "taylor@example.com", "location": "Portland", "website": "",
            "skills": "Illustration, Editorial", "slug": "taylor-reed", "theme": "lavender",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your profile is up to date", response.data)
        public = self.client.get("/p/taylor-reed")
        self.assertEqual(public.status_code, 200)
        self.assertIn(b"Taylor Reed", public.data)

    def test_invalid_profile_is_not_saved(self):
        response = self.client.post("/edit", data={
            "name": "Bad", "title": "Designer", "bio": "Bio", "email": "not-an-email",
            "location": "", "website": "", "skills": "", "slug": "bad", "theme": "mint",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Enter a valid email address", response.data)
        self.assertEqual(self.client.get("/p/alex-morgan").status_code, 200)

    def test_project_can_be_added_and_removed(self):
        response = self.client.post("/projects", data={
            "title": "Field Notes", "description": "A small design project.",
            "year": "2026", "category": "Editorial", "url": "",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with closing(portfolio_app.get_db()) as db:
            project = db.execute("SELECT id FROM projects WHERE title = ?", ("Field Notes",)).fetchone()
        self.assertIsNotNone(project)
        self.client.post(f"/projects/{project['id']}/delete")
        with closing(portfolio_app.get_db()) as db:
            removed = db.execute("SELECT id FROM projects WHERE title = ?", ("Field Notes",)).fetchone()
        self.assertIsNone(removed)

    def test_unknown_public_portfolio_returns_404(self):
        self.assertEqual(self.client.get("/p/no-such-person").status_code, 404)

    def test_editor_requires_password_when_configured(self):
        portfolio_app.app.config["ADMIN_PASSWORD"] = "test-editor-password"
        self.assertEqual(self.client.get("/edit").status_code, 401)
        response = self.client.get("/edit", headers={"Authorization": "Basic Zm9ybWE6dGVzdC1lZGl0b3ItcGFzc3dvcmQ="})
        self.assertEqual(response.status_code, 200)

    def test_hosted_editor_fails_closed_without_password(self):
        with patch.dict("os.environ", {"RENDER_EXTERNAL_HOSTNAME": "example.onrender.com"}):
            self.assertEqual(self.client.get("/edit").status_code, 503)


if __name__ == "__main__":
    unittest.main()
