import unittest
from decimal import Decimal
from app import create_app
from extensions import db
from models.auth import User, Role, MentorProfile, Skill
from models.connection import LearningRelationship, LearningRequest
from models.learning import LearningProgress
from models.reviews import Review

class TestReviewsSystem(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_full_reviews_system(self):
        print("\n--- Running Reviews System Comprehensive Verification ---")
        with self.app.app_context():
            learner = User.query.filter_by(email="pratoy16@gmail.com").first()
            self.assertIsNotNone(learner, "Learner pratoy16@gmail.com should exist")
            mentor = User.query.filter_by(email="ashik@gmail.com").first()
            self.assertIsNotNone(mentor, "Mentor ashik@gmail.com should exist")

            learner_id = learner.id
            learner_name = learner.full_name
            mentor_id = mentor.id
            mentor_name = mentor.full_name

            # Clean any existing reviews for this relationship to start fresh
            rel = LearningRelationship.query.filter_by(learner_id=learner_id, mentor_id=mentor_id).first()
            self.assertIsNotNone(rel, "Learning relationship should exist")
            rel_id = rel.id
            Review.query.filter_by(relationship_id=rel_id).delete()
            db.session.commit()

            # Ensure mentor rating is 0 to start
            m_prof = MentorProfile.query.filter_by(user_id=mentor_id).first()
            if m_prof:
                m_prof.rating = Decimal("0.00")
                db.session.commit()

        csrf = "test_token"

        # 1. Learner visits learning progress page
        with self.client.session_transaction() as sess:
            sess["user_id"] = learner_id
            sess["csrf_token"] = csrf
        
        resp = self.client.get(f"/learning/{rel_id}/progress")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Rate & Review this Mentor", html)
        self.assertIn("Submit Review", html)
        print("✓ Test 1: Learner sees 'Rate & Review this Mentor' section on progress page")

        # 2. Learner submits a 5-star review
        with self.client.session_transaction() as sess:
            sess["user_id"] = learner_id
            sess["csrf_token"] = csrf
        post_resp = self.client.post(
            f"/learner/reviews/{rel_id}",
            data={"csrf_token": csrf, "rating": "5", "review_text": "Ashik is a fantastic cycling coach! Very patient."},
            follow_redirects=True
        )
        self.assertEqual(post_resp.status_code, 200)
        progress_html = post_resp.get_data(as_text=True)
        self.assertIn("Your review has been submitted successfully.", progress_html)
        self.assertIn("Ashik is a fantastic cycling coach!", progress_html)
        self.assertIn("Edit Review", progress_html)
        self.assertIn("Delete Review", progress_html)
        print("✓ Test 2: Learner submitted 5-star review, successfully redirected to progress page")

        with self.app.app_context():
            rev = Review.query.filter_by(relationship_id=rel_id).first()
            self.assertIsNotNone(rev)
            self.assertEqual(rev.rating, 5)
            self.assertEqual(rev.status, "Published")
            m = User.query.get(mentor_id)
            self.assertEqual(float(m.mentor_profile.rating), 5.0)
            print("✓ Test 2b: Mentor profile rating updated to 5.0 in DB")

        # 3. Learner edits the review to 4 stars
        with self.client.session_transaction() as sess:
            sess["user_id"] = learner_id
            sess["csrf_token"] = csrf
        edit_resp = self.client.post(
            f"/learner/reviews/{rel_id}",
            data={"csrf_token": csrf, "rating": "4", "review_text": "Updated: Great sessions overall, learned a lot!"},
            follow_redirects=True
        )
        self.assertEqual(edit_resp.status_code, 200)
        edit_html = edit_resp.get_data(as_text=True)
        self.assertIn("Your review has been updated successfully.", edit_html)
        self.assertIn("Updated: Great sessions overall", edit_html)

        with self.app.app_context():
            rev = Review.query.filter_by(relationship_id=rel_id).first()
            self.assertEqual(rev.rating, 4)
            m = User.query.get(mentor_id)
            self.assertEqual(float(m.mentor_profile.rating), 4.0)
            print("✓ Test 3: Learner edited review to 4 stars, mentor rating recalculated to 4.0")

        # 4. Mentor views the progress page
        with self.client.session_transaction() as sess:
            sess["user_id"] = mentor_id
            sess["csrf_token"] = csrf

        m_resp = self.client.get(f"/learning/{rel_id}/progress")
        self.assertEqual(m_resp.status_code, 200)
        m_html = m_resp.get_data(as_text=True)
        self.assertIn("Learner Review & Rating", m_html)
        self.assertIn("4/5 Rating", m_html)
        self.assertNotIn("Submit Review", m_html)
        self.assertNotIn("Delete Review", m_html)
        print("✓ Test 4: Mentor views progress page and sees read-only review without submit/delete controls")

        # 5. Mentor cannot submit a review (role restricted)
        with self.client.session_transaction() as sess:
            sess["user_id"] = mentor_id
            sess["csrf_token"] = csrf
        m_submit = self.client.post(f"/learner/reviews/{rel_id}", data={"csrf_token": csrf, "rating": "5", "review_text": "Self review"})
        self.assertIn(m_submit.status_code, [403, 302])
        print("✓ Test 5: Mentor is forbidden from submitting reviews")

        # 6. Public Mentor Profile shows the review and rating
        with self.client.session_transaction() as sess:
            sess.clear() # Logged out visitor
        profile_resp = self.client.get(f"/mentor/{mentor_id}")
        self.assertEqual(profile_resp.status_code, 200)
        p_html = profile_resp.get_data(as_text=True)
        self.assertIn("Reviews & Ratings", p_html)
        self.assertIn("4.0", p_html)
        self.assertIn("Updated: Great sessions overall", p_html)
        self.assertIn(learner_name, p_html)
        print("✓ Test 6: Public mentor profile renders dynamic review, rating, and reviewer name")

        # 7. Admin moderation
        with self.app.app_context():
            admin = User.query.join(User.role).filter(Role.name == "Admin").first()
            admin_id = admin.id if admin else None
            rev = Review.query.filter_by(relationship_id=rel_id).first()
            rev_id = rev.id

        if admin_id:
            with self.client.session_transaction() as sess:
                sess["user_id"] = admin_id
                sess["csrf_token"] = csrf
            
            # Hide review
            hide_resp = self.client.post(f"/admin/reviews/{rev_id}/hide", data={"csrf_token": csrf}, follow_redirects=True)
            self.assertEqual(hide_resp.status_code, 200)

            with self.app.app_context():
                rev = Review.query.get(rev_id)
                self.assertEqual(rev.status, "Hidden")
                m = User.query.get(mentor_id)
                self.assertEqual(float(m.mentor_profile.rating), 0.0)
                print("✓ Test 7a: Admin hid review, mentor rating dropped to 0.0")

            # Publish review back
            with self.client.session_transaction() as sess:
                sess["user_id"] = admin_id
                sess["csrf_token"] = csrf
            pub_resp = self.client.post(f"/admin/reviews/{rev_id}/publish", data={"csrf_token": csrf}, follow_redirects=True)
            self.assertEqual(pub_resp.status_code, 200)

            with self.app.app_context():
                rev = Review.query.get(rev_id)
                self.assertEqual(rev.status, "Published")
                m = User.query.get(mentor_id)
                self.assertEqual(float(m.mentor_profile.rating), 4.0)
                print("✓ Test 7b: Admin published review back, mentor rating restored to 4.0")

        # 8. Learner deletes the review
        with self.client.session_transaction() as sess:
            sess["user_id"] = learner_id
            sess["csrf_token"] = csrf

        del_resp = self.client.post(f"/learner/reviews/{rel_id}/delete", data={"csrf_token": csrf}, follow_redirects=True)
        self.assertEqual(del_resp.status_code, 200)
        del_html = del_resp.get_data(as_text=True)
        self.assertIn("Your review has been deleted.", del_html)
        self.assertIn("Rate & Review this Mentor", del_html)
        self.assertIn("Submit Review", del_html)

        with self.app.app_context():
            rev = Review.query.filter_by(relationship_id=rel_id).first()
            self.assertIsNone(rev)
            m = User.query.get(mentor_id)
            self.assertEqual(float(m.mentor_profile.rating), 0.0)
            print("✓ Test 8: Learner deleted review, review removed from DB, mentor rating reset to 0.0")

        # 9. Public mentor profile empty state
        with self.client.session_transaction() as sess:
            sess.clear()
        p_empty = self.client.get(f"/mentor/{mentor_id}")
        self.assertEqual(p_empty.status_code, 200)
        pe_html = p_empty.get_data(as_text=True)
        self.assertIn("No reviews yet", pe_html)
        self.assertIn("Reviews from learners will appear here after they share their experience.", pe_html)
        print("✓ Test 9: Public profile shows clean empty state when no reviews exist")

        # 10. Re-create a clean 5-star review so the learner and mentor have active review data
        with self.client.session_transaction() as sess:
            sess["user_id"] = learner_id
            sess["csrf_token"] = csrf
        final_post = self.client.post(
            f"/learner/reviews/{rel_id}",
            data={"csrf_token": csrf, "rating": "5", "review_text": "Ashik is an exceptional cycling instructor. Patient, knowledgeable, and helped me build confidence rapidly!"},
            follow_redirects=True
        )
        self.assertEqual(final_post.status_code, 200)
        with self.app.app_context():
            rev = Review.query.filter_by(relationship_id=rel_id).first()
            self.assertIsNotNone(rev)
            self.assertEqual(rev.rating, 5)
            m = User.query.get(mentor_id)
            self.assertEqual(float(m.mentor_profile.rating), 5.0)
            print("✓ Test 10: Final 5-star review established for learner and mentor.")

if __name__ == "__main__":
    unittest.main()
