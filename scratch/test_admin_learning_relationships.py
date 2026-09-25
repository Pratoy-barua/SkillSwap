import unittest
from decimal import Decimal
from app import create_app
from extensions import db
from models.auth import User, Role, MentorProfile, Skill
from models.connection import LearningRelationship, LearningRequest, Conversation
from models.learning import LearningProgress, LearningPlan

class TestAdminLearningRelationships(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        # Always restore status to Active
        rel = LearningRelationship.query.first()
        if rel and rel.status != "Active":
            rel.status = "Active"
            db.session.commit()
        self.ctx.pop()

    def test_admin_learning_relationships(self):
        print("\n--- Running Admin Active Learning Relationships Tests ---")
        admin = User.query.join(User.role).filter(Role.name == "Admin").first()
        self.assertIsNotNone(admin, "Admin account should exist")
        admin_id = admin.id

        learner = User.query.filter_by(email="pratoy16@gmail.com").first()
        self.assertIsNotNone(learner, "Learner pratoy16@gmail.com should exist")
        learner_id = learner.id
        learner_name = learner.full_name

        mentor = User.query.filter_by(email="ashik@gmail.com").first()
        self.assertIsNotNone(mentor, "Mentor ashik@gmail.com should exist")
        mentor_id = mentor.id
        mentor_name = mentor.full_name

        # Ensure active relationship exists
        rel = LearningRelationship.query.filter_by(learner_id=learner_id, mentor_id=mentor_id).first()
        self.assertIsNotNone(rel, "Active relationship between learner and mentor should exist")
        rel.status = "Active"
        db.session.commit()
        rel_id = rel.id

        # Check progress data
        self.assertIsNotNone(rel.progress)
        self.assertEqual(rel.progress.percentage, 25)

        # Ensure conversation exists
        if not rel.conversation:
            rel.conversation = Conversation(relationship=rel)
            db.session.commit()
        conv_id = rel.conversation.id

        csrf = "test_csrf_token"

        # 1. Admin visits Admin Dashboard
        with self.client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["csrf_token"] = csrf

        dash_resp = self.client.get("/admin/dashboard")
        self.assertEqual(dash_resp.status_code, 200)
        dash_html = dash_resp.get_data(as_text=True)

        self.assertIn("Active Learning Relationships", dash_html)
        self.assertIn("Monitor ongoing mentor-learner learning connections.", dash_html)
        self.assertIn(mentor_name, dash_html)
        self.assertIn(learner_name, dash_html)
        self.assertIn("25%", dash_html)
        self.assertIn("View all →", dash_html)
        self.assertIn("View details →", dash_html)
        print("✓ Test 1: Admin Dashboard contains 'Active Learning Relationships' section with live data")

        # 2. Admin visits All Active Relationships page (/admin/relationships)
        with self.client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["csrf_token"] = csrf

        list_resp = self.client.get("/admin/relationships")
        self.assertEqual(list_resp.status_code, 200)
        list_html = list_resp.get_data(as_text=True)

        self.assertIn("Active Learning Relationships", list_html)
        self.assertIn(mentor_name, list_html)
        self.assertIn(learner_name, list_html)
        self.assertIn("25%", list_html)
        self.assertIn(f"/admin/relationships/{rel_id}", list_html)
        print("✓ Test 2: Admin can view all active relationships page (/admin/relationships)")

        # 3. Search and filtering on /admin/relationships
        with self.client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["csrf_token"] = csrf

        # Search by mentor name
        search_resp = self.client.get(f"/admin/relationships?search={mentor_name[:4]}")
        self.assertEqual(search_resp.status_code, 200)
        self.assertIn(mentor_name, search_resp.get_data(as_text=True))

        # Search for non-existent name
        no_match_resp = self.client.get("/admin/relationships?search=NonExistentPersonName123")
        self.assertEqual(no_match_resp.status_code, 200)
        self.assertIn("No active learning relationships found", no_match_resp.get_data(as_text=True))
        print("✓ Test 3: Search and filtering works correctly on /admin/relationships")

        # 4. Admin visits detailed relationship view (/admin/relationships/<id>)
        with self.client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["csrf_token"] = csrf

        detail_resp = self.client.get(f"/admin/relationships/{rel_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail_html = detail_resp.get_data(as_text=True)

        self.assertIn("Learning Relationship Details", detail_html)
        self.assertIn(mentor_name, detail_html)
        self.assertIn(learner_name, detail_html)
        self.assertIn("25%", detail_html)
        self.assertIn("Current Progress Breakdown", detail_html)
        self.assertIn("Learning Plan", detail_html)
        self.assertIn("Open Conversation", detail_html)
        self.assertIn("View Mentor Profile", detail_html)
        self.assertIn("View Learner Profile", detail_html)
        self.assertIn("Admin Read-Only", detail_html)
        print("✓ Test 4: Relationship details view renders complete mentor, learner, progress, plan, and links")

        # 5. Admin opens conversation in read-only mode
        with self.client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["csrf_token"] = csrf

        chat_resp = self.client.get(f"/chat/{conv_id}")
        self.assertEqual(chat_resp.status_code, 200)
        chat_html = chat_resp.get_data(as_text=True)
        self.assertIn("Admin read-only monitoring mode", chat_html)
        self.assertIn("Back to Relationship Details", chat_html)

        # Admin cannot post messages
        chat_post = self.client.post(f"/chat/{conv_id}", data={"csrf_token": csrf, "body": "Admin message"})
        self.assertEqual(chat_post.status_code, 403)
        print("✓ Test 5: Admin can inspect direct chat conversation in read-only mode and is blocked from sending messages")

        # 6. Unauthorized access: Normal learner cannot access admin relationships
        with self.client.session_transaction() as sess:
            sess["user_id"] = learner_id
            sess["csrf_token"] = csrf

        learner_forbidden = self.client.get("/admin/relationships")
        self.assertEqual(learner_forbidden.status_code, 403)

        learner_detail_forbidden = self.client.get(f"/admin/relationships/{rel_id}")
        self.assertEqual(learner_detail_forbidden.status_code, 403)
        print("✓ Test 6: Normal learner gets 403 Forbidden on admin relationship endpoints")

        # 7. Unauthorized access: Mentor cannot access admin relationships
        with self.client.session_transaction() as sess:
            sess["user_id"] = mentor_id
            sess["csrf_token"] = csrf

        mentor_forbidden = self.client.get("/admin/relationships")
        self.assertEqual(mentor_forbidden.status_code, 403)

        mentor_detail_forbidden = self.client.get(f"/admin/relationships/{rel_id}")
        self.assertEqual(mentor_detail_forbidden.status_code, 403)
        print("✓ Test 7: Mentor gets 403 Forbidden on admin relationship endpoints")

        # 8. Logged out visitor redirected to login
        with self.client.session_transaction() as sess:
            sess.clear()

        logged_out = self.client.get("/admin/relationships")
        self.assertEqual(logged_out.status_code, 302)
        self.assertIn("/auth/login", logged_out.headers["Location"])
        print("✓ Test 8: Logged-out visitor is redirected to login")

        # 9. Test Completed / non-active relationship filtering
        rel_obj = db.session.get(LearningRelationship, rel_id)
        rel_obj.status = "Completed"
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["csrf_token"] = csrf

        dash_comp = self.client.get("/admin/dashboard")
        self.assertEqual(dash_comp.status_code, 200)
        self.assertIn("No active learning relationships.", dash_comp.get_data(as_text=True))
        print("✓ Test 9: Completed relationship is excluded from dashboard Active Learning Relationships card")

        # Restore relationship status back to Active
        rel_obj = db.session.get(LearningRelationship, rel_id)
        rel_obj.status = "Active"
        db.session.commit()

        # Confirm it appears again
        with self.client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["csrf_token"] = csrf

        dash_restored = self.client.get("/admin/dashboard")
        self.assertIn(mentor_name, dash_restored.get_data(as_text=True))
        print("✓ Test 10: Restored active relationship correctly reappears on dashboard")

if __name__ == "__main__":
    unittest.main()
