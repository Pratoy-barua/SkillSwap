import os
import re
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest

from app import create_app
from extensions import db
from models.connection import LearningRelationship, Notification

class TestActiveLearningCard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()

    def test_active_learning_card_rendering(self):
        # User 2 is pratoy barua (learner)
        with self.client.session_transaction() as sess:
            sess["user_id"] = 2

        res = self.client.get("/learner/dashboard")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # 1. Structure elements
        self.assertIn("active-learning-card", html)
        self.assertIn("alc-circle-wrapper", html)
        self.assertIn("alc-divider", html)
        self.assertIn("alc-content", html)

        # 2. Dynamic content checks for relationship 1
        self.assertIn("25%", html)
        self.assertIn("COMPLETED", html)
        self.assertIn("Ashik Dash", html)
        self.assertIn("cycllist", html)
        self.assertIn("CURRENT MILESTONE PROGRESS", html)
        self.assertIn("25 of 100%", html)
        self.assertIn("In Progress", html)
        self.assertIn("Sep 26, 2026", html)
        self.assertIn("View details", html)
        self.assertIn("/learning/1/progress", html)

        # 3. Heading and subtitle preserved
        self.assertIn("Active learning", html)
        self.assertIn("Stay on track with your current learning plans.", html)
        self.assertIn("View all", html)

        # 4. Other dashboard sections untouched
        self.assertIn("Quick actions", html)
        self.assertIn("Learning requests", html)
        self.assertIn("Recent notifications", html)

        with self.app.app_context():
            expected_count = Notification.query.filter_by(user_id=2, is_read=False).count()
        if expected_count > 0:
            m = re.search(r'id=["\']navNotificationCount["\'][^>]*>(\d+)<', html)
            self.assertIsNotNone(m, f"Notification count badge not found in html")
            self.assertEqual(int(m.group(1)), expected_count)
        else:
            self.assertNotIn('id="navNotificationCount"', html)

    def test_view_details_link_destination(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 2

        # Follow view details link to learning progress page
        res = self.client.get("/learning/1/progress")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Learning Progress", html)
        self.assertIn("Ashik Dash", html)

    def test_empty_state_rendering(self):
        # Find a learner who has 0 active relationships
        with self.app.app_context():
            from models.auth import User
            from models.connection import LearningRelationship
            learners = User.query.filter(User.role.has(name='Learner')).all()
            empty_learner = None
            for l in learners:
                if LearningRelationship.query.filter_by(learner_id=l.id, status='Active').count() == 0:
                    empty_learner = l
                    break

        if empty_learner:
            with self.client.session_transaction() as sess:
                sess["user_id"] = empty_learner.id

            res = self.client.get("/learner/dashboard")
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            self.assertIn("No active learning yet.", html)
            self.assertIn("Find a mentor", html)
            self.assertNotIn("active-learning-card", html)

if __name__ == "__main__":
    unittest.main()
