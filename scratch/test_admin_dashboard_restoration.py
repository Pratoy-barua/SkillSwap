import os
import re
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest

from app import create_app
from extensions import db
from models.auth import User
from models.connection import Notification

class TestAdminDashboardRestoration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()

    def test_admin_dashboard_access_control(self):
        # 1. Anonymous user redirected
        res = self.client.get("/admin/dashboard")
        self.assertIn(res.status_code, [302, 401, 403])

        # 2. Learner (User 2) forbidden/redirected
        with self.client.session_transaction() as sess:
            sess["user_id"] = 2
        res = self.client.get("/admin/dashboard")
        self.assertIn(res.status_code, [302, 403])

        # 3. Admin (User 1) allowed
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 200)

    def test_admin_dashboard_restored_layout(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1

        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # 1. Header & Kicker
        self.assertIn("dashboard-page", html)
        self.assertIn("dashboard-container", html)
        self.assertIn("dashboard-header", html)
        self.assertIn("Platform control", html)
        self.assertIn("Admin dashboard", html)
        self.assertIn("Monitor and manage the SkillSwap platform from one place.", html)
        self.assertIn("Manage users", html)
        self.assertIn("Manage skills", html)

        # 2. Metric Section - Platform Overview (four-up grid)
        self.assertIn("dashboard-metric-section", html)
        self.assertIn("Platform overview", html)
        self.assertIn("dashboard-stat-grid four-up", html)
        self.assertIn("Learners", html)
        self.assertIn("Mentors", html)
        self.assertIn("Active users", html)
        self.assertIn("Pending users", html)

        # 3. Learning & Business mini-metric grids
        self.assertIn("Learning", html)
        self.assertIn("Active skills", html)
        self.assertIn("Active relationships", html)
        self.assertIn("Reviews", html)
        self.assertIn("Suspended users", html)

        self.assertIn("Business", html)
        self.assertIn("Successful payments", html)
        self.assertIn("Net revenue", html)
        self.assertIn("Store products", html)
        self.assertIn("Store orders", html)

        # 4. Pending applications & Quick actions
        self.assertIn("Pending applications", html)
        self.assertIn("Admin quick actions", html)
        self.assertIn("quick-action-list", html)

        # 5. Business Overview graph remains removed
        self.assertNotIn("Business Overview", html)
        self.assertNotIn("business-overview", html)
        self.assertNotIn("business_overview", html)

        # 6. Redesign elements are NOT present
        self.assertNotIn("ad-dashboard-page", html)
        self.assertNotIn("ad-header-card", html)
        self.assertNotIn("ad-kpi-grid", html)
        self.assertNotIn("ad-nav-bar", html)

    def test_store_and_admin_links_work(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1

        routes_to_test = [
            "/admin/users",
            "/admin/skills",
            "/admin/store/products",
            "/admin/store/orders",
            "/admin/payments",
            "/admin/revenue",
            "/admin/reviews",
            "/admin/premium/plans",
        ]

        for route in routes_to_test:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} failed with status {res.status_code}")

    def test_notification_bell_intact(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1

        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("notification-trigger", html)
        self.assertIn("notificationBellBtn", html)
        self.assertIn("notification-dropdown", html)

if __name__ == "__main__":
    unittest.main()
