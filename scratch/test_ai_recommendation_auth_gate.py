"""Automated tests for Login-Gated AI Mentor Recommendation and Interactive Map."""

import os
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest

from app import create_app
from extensions import db
from models.auth import Role, User


class AIMentorRecommendationAuthGateTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        with self.app.app_context():
            learner = User.query.join(User.role).filter(Role.name == "Learner", User.account_status == "Approved", User.email != "pratoy16@gmail.com").first()
            if not learner:
                learner = User.query.join(User.role).filter(Role.name == "Learner", User.account_status == "Approved").first()
            self.learner_id = learner.id
            self.learner_email = learner.email

            mentor = User.query.join(User.role).filter(Role.name == "Mentor", User.account_status == "Approved").first()
            self.mentor_id = mentor.id

    def test_01_logged_out_visitor_sees_locked_ai_and_public_search(self):
        """Logged-out user sees normal mentor search, but AI recommendation & map are locked."""
        res = self.client.get("/mentors")
        self.assertEqual(res.status_code, 200)

        # Normal mentor search elements must remain visible
        self.assertIn(b"Find a mentor near you.", res.data)
        self.assertIn(b"Find your best match", res.data)
        self.assertIn(b"discovery-filters", res.data)
        self.assertIn(b"Popular skills", res.data)
        self.assertIn(b"Search results", res.data)
        self.assertIn(b"mentor-discovery-card", res.data)

        # AI section must show minimal locked card
        self.assertIn(b"AI-Powered Mentor Recommendation", res.data)
        self.assertIn(b"Get personalized mentor recommendations based on your skills and location.", res.data)
        self.assertIn(b"Login required", res.data)
        self.assertIn(b"Log in", res.data)
        self.assertIn(b"Sign up", res.data)

        # Removed verbose lists and cards must NOT be present
        self.assertNotIn(b"Sign in to unlock:", res.data)
        self.assertNotIn(b"AI-powered mentor matching", res.data)
        self.assertNotIn(b"Location-based recommendations", res.data)
        self.assertNotIn(b"Interactive mentor map", res.data)
        self.assertNotIn(b"Personalized mentor ranking", res.data)
        self.assertNotIn(b"AI Best Match", res.data)
        self.assertNotIn(b"Nearest Mentor Distance", res.data)
        self.assertNotIn(b"Recommended Route", res.data)

        # Removed elements (discovery-trust row and premium advanced search) must NOT be present
        self.assertNotIn(b"discovery-trust", res.data)
        self.assertNotIn(b"Location-based search", res.data)
        self.assertNotIn(b"Profile ratings", res.data)
        self.assertNotIn(b"premium-filter", res.data)
        self.assertNotIn(b"Use premium advanced search", res.data)
        self.assertNotIn(b"Premium filters are checked securely after search.", res.data)

        # Gated items must NOT be present
        self.assertNotIn(b'id="ai-map"', res.data)
        self.assertNotIn(b"Use My Current Location", res.data)
        self.assertNotIn(b"Run AI Recommendations", res.data)
        self.assertNotIn(b"leaflet.js", res.data)
        self.assertNotIn(b"leaflet.css", res.data)

    def test_02_logged_out_direct_api_access_is_blocked(self):
        """Logged-out visitor calling /api/ai-recommend cannot receive recommendation data."""
        # 1. Standard browser GET request -> 302 redirect to login with next=/mentors
        res = self.client.get("/api/ai-recommend?latitude=23.7979&longitude=90.4236")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/auth/login", res.headers.get("Location", ""))
        self.assertNotIn(b"ranked_mentors", res.data)
        self.assertNotIn(b"ai_best_match", res.data)

        # 2. Following redirects lands on login page, not recommendation data
        followed = self.client.get("/api/ai-recommend?latitude=23.7979&longitude=90.4236", follow_redirects=True)
        self.assertEqual(followed.status_code, 200)
        self.assertIn(b"Log in to SkillSwap", followed.data)
        self.assertNotIn(b"ranked_mentors", followed.data)
        self.assertNotIn(b"ai_best_match", followed.data)

        # 3. Explicit JSON API request -> 401 JSON error
        json_res = self.client.get(
            "/api/ai-recommend?latitude=23.7979&longitude=90.4236",
            headers={"Accept": "application/json"}
        )
        self.assertEqual(json_res.status_code, 401)
        data = json_res.get_json()
        self.assertIsNotNone(data)
        self.assertIn("error", data)
        self.assertIn("Authentication required", data["error"])
        self.assertNotIn("ranked_mentors", data)

    def test_03_logged_in_user_sees_full_ai_and_map_ui(self):
        """Logged-in user sees the active AI recommendation hub and interactive map."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner_id

        res = self.client.get("/mentors")
        self.assertEqual(res.status_code, 200)

        # Active AI hub & map elements must be present
        self.assertIn(b"AI Mentor Recommendation & Interactive Map", res.data)
        self.assertIn(b"Use My Current Location", res.data)
        self.assertIn(b"Run AI Recommendations", res.data)
        self.assertIn(b'id="ai-map"', res.data)
        self.assertIn(b'id="ai-recommendations-container"', res.data)
        self.assertIn(b"leaflet.js", res.data)
        self.assertIn(b"leaflet.css", res.data)

        # Locked state and removed elements must NOT be present
        self.assertNotIn(b'id="ai-recommendation-locked"', res.data)
        self.assertNotIn(b"Sign in to unlock:", res.data)
        self.assertNotIn(b"discovery-trust", res.data)
        self.assertNotIn(b"premium-filter", res.data)

    def test_04_logged_in_user_can_call_ai_api(self):
        """Authenticated user receives full AI recommendations and preserved algorithms."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner_id

        res = self.client.get("/api/ai-recommend?latitude=23.7979&longitude=90.4236")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsNotNone(data)

        # Verify AI recommendation data structure
        self.assertIn("ranked_mentors", data)
        self.assertIn("telemetry", data)
        self.assertIn("learner_location", data)

        # Verify algorithm preservation
        telemetry = data.get("telemetry", {})
        self.assertIn("astar", telemetry)
        self.assertIn("hill_climbing", telemetry)
        self.assertIn("simulated_annealing", telemetry)

        # Mentors have scores, distance and location
        if data.get("ranked_mentors"):
            top = data["ranked_mentors"][0]
            self.assertIn("distance_km", top)
            self.assertIn("full_name", top)

    def test_05_post_login_redirect_to_mentors(self):
        """Logging in with next=/mentors redirects user back to mentor discovery."""
        with self.app.app_context():
            user = db.session.get(User, self.learner_id)
            orig_hash = user.password_hash
            user.set_password("ValidPass123!")
            db.session.commit()

        try:
            # Fetch CSRF token from login page
            with self.client.session_transaction() as sess:
                sess["csrf_token"] = "auth-csrf-token"

            res = self.client.post(
                "/auth/login?next=/mentors",
                data={
                    "csrf_token": "auth-csrf-token",
                    "email": self.learner_email,
                    "password": "ValidPass123!",
                    "next": "/mentors"
                },
                follow_redirects=False
            )
            self.assertEqual(res.status_code, 302)
            self.assertEqual(res.headers.get("Location"), "/mentors")
        finally:
            with self.app.app_context():
                user = db.session.get(User, self.learner_id)
                user.password_hash = orig_hash
                db.session.commit()

    def test_06_mentor_user_also_has_access_if_authenticated(self):
        """Authenticated mentor can also view and use AI recommendations on discovery page."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.mentor_id

        res = self.client.get("/mentors")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"AI Mentor Recommendation & Interactive Map", res.data)
        self.assertNotIn(b'id="ai-recommendation-locked"', res.data)

        api_res = self.client.get("/api/ai-recommend?latitude=23.7979&longitude=90.4236")
        self.assertEqual(api_res.status_code, 200)
        self.assertIn("ranked_mentors", api_res.get_json())


if __name__ == "__main__":
    unittest.main()
