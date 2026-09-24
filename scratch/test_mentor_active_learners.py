import os
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest

from app import create_app
from extensions import db
from models.connection import LearningRelationship

class TestMentorActiveLearners(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()

    def test_mentor_active_learners_card_rendering(self):
        # User 7 is Ashik Dash (mentor)
        with self.client.session_transaction() as sess:
            sess["user_id"] = 7

        res = self.client.get("/mentor/dashboard")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # 1. Structure elements
        self.assertIn("active-learning-card", html)
        self.assertIn("alc-circle-wrapper", html)
        self.assertIn("alc-circle-chart", html)
        self.assertIn("alc-divider", html)
        self.assertIn("alc-content", html)

        # 2. Dynamic content checks for relationship 1
        self.assertIn("25%", html)
        self.assertIn("COMPLETED", html)
        self.assertIn("pratoy barua", html)
        self.assertIn("/learner/2", html)
        self.assertIn("cycllist", html)
        self.assertIn("CURRENT MILESTONE PROGRESS", html)
        self.assertIn("25 of 100%", html)
        self.assertIn("width: 25%;", html)
        self.assertIn("Status", html)
        self.assertIn("In Progress", html)
        self.assertIn("Expected Finish", html)
        self.assertIn("Sep 26, 2026", html)
        self.assertIn("Update progress", html)
        self.assertIn("/mentor/learning/1/progress", html)

        # 3. Heading and subtitle preserved
        self.assertIn("Active learners", html)
        self.assertIn("Update plans and progress for ongoing learning.", html)
        self.assertIn("View all", html)

        # 4. Other mentor dashboard sections untouched
        self.assertIn("Mentor skills", html)
        self.assertIn("Pending learning requests", html)
        self.assertIn("Recent reviews", html)
        self.assertIn("Purchase history", html)

    def test_update_progress_link_destination(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 7

        # Follow "Update progress" button link
        res = self.client.get("/mentor/learning/1/progress")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        # Should show the mentor's progress page for this relationship
        self.assertIn("cycllist", html)
        self.assertIn("pratoy barua", html)

    def test_empty_state_rendering(self):
        # Find a mentor who has 0 active relationships
        with self.app.app_context():
            from models.auth import User
            mentors = User.query.filter(User.role.has(name='Mentor')).all()
            empty_mentor = None
            for m in mentors:
                if LearningRelationship.query.filter_by(mentor_id=m.id, status='Active').count() == 0:
                    empty_mentor = m
                    break

        if empty_mentor:
            with self.client.session_transaction() as sess:
                sess["user_id"] = empty_mentor.id

            res = self.client.get("/mentor/dashboard")
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            self.assertIn("No active learners yet.", html)
            self.assertIn("Accepted requests will appear here.", html)
            self.assertNotIn("active-learning-card", html)

if __name__ == "__main__":
    unittest.main()
