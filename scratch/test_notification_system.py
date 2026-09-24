import os
import re
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest

from app import create_app
from extensions import db
from models.connection import Notification

class TestNotificationSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            cls.user2_unread_ids = [n.id for n in Notification.query.filter_by(user_id=2, is_read=False).all()]

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            Notification.query.filter(Notification.id.in_(cls.user2_unread_ids)).update({"is_read": False}, synchronize_session=False)
            db.session.commit()

    def setUp(self):
        self.client = self.app.test_client()

    def get_bell_count(self, html):
        m = re.search(r'id=["\']navNotificationCount["\'][^>]*>(\d+)<', html)
        return int(m.group(1)) if m else None

    def get_dashboard_stat_count(self, html):
        m = re.search(r'id=["\']dashboardUnreadCount["\'][^>]*>(\d+)<', html)
        return int(m.group(1)) if m else None

    def test_01_count_consistency_across_pages(self):
        # User 2 (Learner pratoy barua)
        with self.app.app_context():
            initial_user2_unread = Notification.query.filter_by(user_id=2, is_read=False).count()
        expected_bell = initial_user2_unread if initial_user2_unread > 0 else None

        with self.client.session_transaction() as sess:
            sess["user_id"] = 2

        pages_to_test = [
            "/learner/dashboard",
            "/about",
            "/store",
            "/skills",
            "/learning/1/progress",
            "/chat/1",
            "/contact",
            "/privacy",
            "/terms"
        ]

        for page in pages_to_test:
            res = self.client.get(page)
            self.assertEqual(res.status_code, 200, f"Failed on page {page}")
            html = res.get_data(as_text=True)
            bell_count = self.get_bell_count(html)
            self.assertEqual(bell_count, expected_bell, f"Mismatch on {page}: expected {expected_bell}, got {bell_count}")

        # Check dashboard stat card matches exactly
        dash_res = self.client.get("/learner/dashboard")
        dash_html = dash_res.get_data(as_text=True)
        self.assertEqual(self.get_dashboard_stat_count(dash_html), initial_user2_unread)

    def test_02_mentor_count_consistency_and_isolation(self):
        # User 7 (Mentor Ashik Dash)
        with self.app.app_context():
            user7_unread = Notification.query.filter_by(user_id=7, is_read=False).count()
        expected_mentor_bell = user7_unread if user7_unread > 0 else None

        with self.client.session_transaction() as sess:
            sess["user_id"] = 7

        for page in ["/mentor/dashboard", "/about", "/store", "/skills"]:
            res = self.client.get(page)
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            bell_count = self.get_bell_count(html)
            self.assertEqual(bell_count, expected_mentor_bell, f"Mentor mismatch on {page}")

    def test_03_logged_out_has_no_bell(self):
        res = self.client.get("/about")
        html = res.get_data(as_text=True)
        self.assertNotIn("notificationBellBtn", html)
        self.assertNotIn("navNotificationCount", html)

    def test_04_admin_has_bell_with_zero_unread(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1

        res = self.client.get("/about")
        html = res.get_data(as_text=True)
        self.assertIn("notificationBellBtn", html)
        # Admin has 0 unread, so count badge should be hidden
        self.assertIsNone(self.get_bell_count(html))

    def test_05_mark_single_notification_read_ajax_and_form(self):
        with self.app.app_context():
            target_notif = Notification.query.filter_by(user_id=2, is_read=False).first()
            self.assertIsNotNone(target_notif)
            target_id = target_notif.id
            count_before = Notification.query.filter_by(user_id=2, is_read=False).count()

        with self.client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["csrf_token"] = "test-csrf-token"

        # 1. Test AJAX/JSON response
        res = self.client.post(
            f"/notifications/{target_id}/read",
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
            data={"csrf_token": "test-csrf-token"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("unread_count"), count_before - 1)

        # Verify DB updated
        with self.app.app_context():
            updated = db.session.get(Notification, target_id)
            self.assertTrue(updated.is_read)

        # Verify all pages now reflect count_before - 1
        for page in ["/about", "/learner/dashboard", "/store"]:
            p_res = self.client.get(page)
            p_html = p_res.get_data(as_text=True)
            self.assertEqual(self.get_bell_count(p_html), count_before - 1)

        # Restore target notification to unread
        with self.app.app_context():
            updated = db.session.get(Notification, target_id)
            updated.is_read = False
            db.session.commit()

    def test_06_security_ownership_check(self):
        with self.app.app_context():
            user7_notif = Notification.query.filter_by(user_id=7).first()
            self.assertIsNotNone(user7_notif)
            user7_notif_id = user7_notif.id

        # User 2 tries to mark User 7's notification as read
        with self.client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["csrf_token"] = "test-csrf-token"

        res = self.client.post(
            f"/notifications/{user7_notif_id}/read",
            data={"csrf_token": "test-csrf-token"}
        )
        self.assertEqual(res.status_code, 404)

    def test_07_mark_all_read_and_restore(self):
        with self.app.app_context():
            original_unread_ids = [n.id for n in Notification.query.filter_by(user_id=2, is_read=False).all()]
            user7_count_before = Notification.query.filter_by(user_id=7, is_read=False).count()

        with self.client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["csrf_token"] = "test-csrf-token"

        # Mark all read
        res = self.client.post(
            "/notifications/read-all",
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
            data={"csrf_token": "test-csrf-token"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("unread_count"), 0)

        # User 2 now has 0 unread
        with self.app.app_context():
            self.assertEqual(Notification.query.filter_by(user_id=2, is_read=False).count(), 0)
            # User 7 is completely unaffected
            self.assertEqual(Notification.query.filter_by(user_id=7, is_read=False).count(), user7_count_before)

        # Check pages show no badge for User 2
        for page in ["/about", "/learner/dashboard", "/store"]:
            p_res = self.client.get(page)
            p_html = p_res.get_data(as_text=True)
            self.assertIsNone(self.get_bell_count(p_html))

        # Restore original unread notifications for User 2
        with self.app.app_context():
            Notification.query.filter(Notification.id.in_(original_unread_ids)).update({"is_read": False}, synchronize_session=False)
            db.session.commit()
            self.assertEqual(Notification.query.filter_by(user_id=2, is_read=False).count(), len(original_unread_ids))

if __name__ == "__main__":
    unittest.main()
