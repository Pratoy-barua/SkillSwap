import os
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest
from app import create_app
from extensions import db
from models.auth import User
from models.connection import LearningRelationship
from models.learning import LearningProgress

class TestLearningProgressRedesign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False

    def setUp(self):
        self.client = self.app.test_client()

    def test_unauthenticated_access(self):
        res = self.client.get("/learning/1/progress")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_unauthorized_user_forbidden(self):
        with self.app.app_context():
            # Find a user who is neither learner (2) nor mentor (7)
            other_user = User.query.filter(~User.id.in_([2, 7])).first()
            other_email = other_user.email

        with self.client.session_transaction() as sess:
            sess["user_id"] = other_user.id

        res = self.client.get("/learning/1/progress")
        self.assertEqual(res.status_code, 403)

    def test_learner_view(self):
        # User 2 is pratoy barua (learner)
        with self.client.session_transaction() as sess:
            sess["user_id"] = 2

        res = self.client.get("/learning/1/progress")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Check real data rendering
        self.assertIn("Learning Progress", html)
        self.assertIn("pratoy barua", html)
        self.assertIn("Ashik Dash", html)
        self.assertIn("cycllist", html)
        self.assertIn("GG", html)
        self.assertIn("200.00", html)
        self.assertIn("Weekly", html)
        self.assertIn("25%", html)
        self.assertIn("Other", html)
        self.assertIn("balance", html)
        self.assertIn("good", html)

        # Check circular progress SVG and roadmap
        self.assertIn("lp-circle-chart", html)
        self.assertIn("lp-milestone-track", html)

        # Verify mentor mode form is NOT in learner view
        self.assertNotIn("Mentor Editing Mode", html)
        self.assertNotIn("name=\"percentage\"", html)

    def test_mentor_view_and_update(self):
        # User 7 is Ashik Dash (mentor)
        with self.client.session_transaction() as sess:
            sess["user_id"] = 7
            sess["csrf_token"] = "test-token"

        res = self.client.get("/mentor/learning/1/progress")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Mentor mode indicators and form
        self.assertIn("Mentor Editing Mode", html)
        self.assertIn("Update Learning Progress", html)
        self.assertIn("name=\"percentage\"", html)
        self.assertIn("name=\"completed_topics\"", html)
        self.assertIn("name=\"remaining_topics\"", html)
        self.assertIn("name=\"current_topic\"", html)
        self.assertIn("name=\"mentor_notes\"", html)

        # Test POST update to 50%
        post_res = self.client.post("/mentor/learning/1/progress", data={
            "csrf_token": "test-token",
            "percentage": "50",
            "current_topic": "Road practice",
            "completed_topics": "balance\ntraffic rules",
            "remaining_topics": "night riding",
            "mentor_notes": "Great improvement on balance! Next step road practice."
        }, follow_redirects=True)
        self.assertEqual(post_res.status_code, 200)
        post_html = post_res.get_data(as_text=True)
        self.assertIn("50%", post_html)
        self.assertIn("Road practice", post_html)
        self.assertIn("night riding", post_html)

        # Restore original progress (25%, Other, balance, None, good)
        restore_res = self.client.post("/mentor/learning/1/progress", data={
            "csrf_token": "test-token",
            "percentage": "25",
            "current_topic": "Other",
            "completed_topics": "balance",
            "remaining_topics": "",
            "mentor_notes": "good"
        }, follow_redirects=True)
        self.assertEqual(restore_res.status_code, 200)

    def test_edge_cases_none_plan_and_progress(self):
        # Test rendering when relationship has no plan or progress
        with self.app.test_request_context():
            from flask import render_template
            relationship = db.session.get(LearningRelationship, 1)
            # Render with plan=None and progress=None
            html = render_template("learning/progress.html", relationship=relationship, progress=None, mentor_mode=False, recent_activities=[])
            self.assertIn("Learning Progress", html)
            self.assertIn("0%", html)
            self.assertIn("Not Started", html)

            # Test mentor mode with progress=None
            html_mentor = render_template("learning/progress.html", relationship=relationship, progress=None, mentor_mode=True, recent_activities=[])
            self.assertIn("Update Learning Progress", html_mentor)

if __name__ == "__main__":
    unittest.main()
