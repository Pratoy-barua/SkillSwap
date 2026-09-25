"""Automated tests for Paid Mentor Profile Details Unlock feature."""

import os
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest
from decimal import Decimal
from app import create_app
from extensions import db
from models.auth import Role, User
from models.learning import MentorProfileAccess, Payment, PlatformSetting
from models.reviews import RevenueRecord
from services.payments import get_mentor_unlock_fee


class MentorProfileUnlockTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        with self.app.app_context():
            mentor = db.session.get(User, 3)  # Nusrat Jahan
            self.mentor_id = mentor.id
            self.mentor_name = mentor.full_name
            self.assertIsNotNone(mentor.mentor_profile.linkedin_url)

            admin = User.query.join(User.role).filter(Role.name == "Admin").first()
            self.admin_id = admin.id

            # Find two learners
            learners = User.query.join(User.role).filter(Role.name == "Learner", User.account_status == "Approved").limit(2).all()
            self.learner1_id = learners[0].id
            self.learner2_id = learners[1].id

            # Clean up any existing access for learner1 or learner2 to mentor 3
            MentorProfileAccess.query.filter(
                MentorProfileAccess.learner_id.in_([self.learner1_id, self.learner2_id]),
                MentorProfileAccess.mentor_id == self.mentor_id
            ).delete()

            # Ensure unlock fee is set to 50.00
            setting = PlatformSetting.query.filter_by(key="mentor_profile_unlock_fee").first()
            if not setting:
                setting = PlatformSetting(key="mentor_profile_unlock_fee", value="50.00")
                db.session.add(setting)
            else:
                setting.value = "50.00"
            db.session.commit()

    def test_01_anonymous_user_cannot_see_urls(self):
        """Anonymous user sees locked card and NO real URLs in HTML."""
        res = self.client.get(f"/mentor/{self.mentor_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Professional & Contact Details", res.data)
        self.assertIn(b"Locked", res.data)
        self.assertIn(b"Log in as learner to unlock", res.data)

        # Critical privacy requirement: Real URLs must NOT be in the HTML
        self.assertNotIn(b"https://linkedin.com/in/nusrat-jahan-skillswap", res.data)
        self.assertNotIn(b"https://github.com/nusrat-jahan-dev", res.data)
        self.assertNotIn(b"https://nusratjahan.dev", res.data)

    def test_02_unpaid_learner_sees_locked_and_unlock_button(self):
        """Unpaid learner sees locked status and CTA with dynamic fee."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner1_id

        res = self.client.get(f"/mentor/{self.mentor_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Professional & Contact Details", res.data)
        self.assertIn(b"Locked", res.data)
        self.assertIn(b"Unlock Professional Details", res.data)
        self.assertIn(b"50.00", res.data)

        # Privacy check
        self.assertNotIn(b"https://linkedin.com/in/nusrat-jahan-skillswap", res.data)
        self.assertNotIn(b"https://github.com/nusrat-jahan-dev", res.data)
        self.assertNotIn(b"https://nusratjahan.dev", res.data)

    def test_03_checkout_page_renders_correctly(self):
        """Learner can view checkout page with fee breakdown."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner1_id

        res = self.client.get(f"/payments/mentor/{self.mentor_id}/unlock-details")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Unlock Mentor Contact Details", res.data)
        self.assertIn(self.mentor_name.encode("utf-8"), res.data)
        self.assertIn(b"50.00", res.data)

    def test_04_failed_payment_does_not_unlock(self):
        """Simulated failed payment does not unlock profile details."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner1_id
            sess["csrf_token"] = "csrf-token-123"

        res = self.client.post(
            f"/payments/mentor/{self.mentor_id}/unlock-details",
            data={"csrf_token": "csrf-token-123", "demo_outcome": "failure"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Demo payment was marked as failed", res.data)

        with self.app.app_context():
            access = MentorProfileAccess.query.filter_by(
                learner_id=self.learner1_id, mentor_id=self.mentor_id
            ).first()
            self.assertIsNone(access)

    def test_05_successful_payment_unlocks_and_creates_records(self):
        """Successful payment creates Payment, MentorProfileAccess, RevenueRecord, and unlocks details."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner1_id
            sess["csrf_token"] = "csrf-token-123"

        res = self.client.post(
            f"/payments/mentor/{self.mentor_id}/unlock-details",
            data={"csrf_token": "csrf-token-123", "demo_outcome": "success"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Successfully unlocked", res.data)

        with self.app.app_context():
            # Check MentorProfileAccess
            access = MentorProfileAccess.query.filter_by(
                learner_id=self.learner1_id, mentor_id=self.mentor_id
            ).first()
            self.assertIsNotNone(access)
            self.assertIsNotNone(access.payment_id)

            # Check Payment record
            payment = Payment.query.get(access.payment_id)
            self.assertEqual(payment.status, "Successful")
            self.assertEqual(payment.payment_type, "Profile Unlock")
            self.assertEqual(payment.amount, Decimal("50.00"))
            self.assertEqual(payment.platform_commission, Decimal("50.00"))
            self.assertEqual(payment.mentor_earning, Decimal("0.00"))

            # Check RevenueRecord
            rev = RevenueRecord.query.filter_by(
                transaction_key=f"Profile Unlock:{payment.id}"
            ).first()
            self.assertIsNotNone(rev)
            self.assertEqual(rev.gross_amount, Decimal("50.00"))
            self.assertEqual(rev.net_platform_revenue, Decimal("50.00"))

        # Check that learner now sees the unlocked URLs in the mentor profile
        prof_res = self.client.get(f"/mentor/{self.mentor_id}")
        self.assertEqual(prof_res.status_code, 200)
        self.assertIn(b"Details Unlocked", prof_res.data)
        self.assertIn(b"https://linkedin.com/in/nusrat-jahan-skillswap", prof_res.data)
        self.assertIn(b"https://github.com/nusrat-jahan-dev", prof_res.data)
        self.assertIn(b"https://nusratjahan.dev", prof_res.data)

    def test_06_duplicate_payment_prevented(self):
        """Learner who has already unlocked is redirected from checkout."""
        with self.app.app_context():
            access = MentorProfileAccess(learner_id=self.learner1_id, mentor_id=self.mentor_id)
            db.session.add(access)
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner1_id

        res = self.client.get(f"/payments/mentor/{self.mentor_id}/unlock-details", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"already unlocked", res.data)

    def test_07_other_learner_remains_locked(self):
        """Unlocking by learner1 does not unlock for learner2."""
        with self.app.app_context():
            access = MentorProfileAccess(learner_id=self.learner1_id, mentor_id=self.mentor_id)
            db.session.add(access)
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner2_id

        res = self.client.get(f"/mentor/{self.mentor_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Locked", res.data)
        self.assertNotIn(b"https://linkedin.com/in/nusrat-jahan-skillswap", res.data)

    def test_08_mentor_views_own_details_without_paying(self):
        """Mentor sees their own links without payment."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.mentor_id

        res = self.client.get(f"/mentor/{self.mentor_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Your Profile (Owner View)", res.data)
        self.assertIn(b"https://linkedin.com/in/nusrat-jahan-skillswap", res.data)
        self.assertIn(b"https://github.com/nusrat-jahan-dev", res.data)

    def test_09_admin_views_details_without_paying(self):
        """Admin can view any mentor's details directly."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin_id

        res = self.client.get(f"/mentor/{self.mentor_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Admin Access", res.data)
        self.assertIn(b"https://linkedin.com/in/nusrat-jahan-skillswap", res.data)

    def test_10_admin_updates_fee_and_new_price_reflects(self):
        """Admin changes unlock fee and new price is used in checkout and UI."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin_id
            sess["csrf_token"] = "admin-csrf"

        res = self.client.post(
            "/admin/settings/mentor-unlock-fee",
            data={"csrf_token": "admin-csrf", "unlock_fee": "80.00"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Mentor profile unlock fee updated to", res.data)

        with self.app.app_context():
            self.assertEqual(get_mentor_unlock_fee(), Decimal("80.00"))

        # Verify learner now sees 80.00
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner2_id

        prof_res = self.client.get(f"/mentor/{self.mentor_id}")
        self.assertIn(b"80.00", prof_res.data)

        # Reset fee back
        with self.app.app_context():
            setting = PlatformSetting.query.filter_by(key="mentor_profile_unlock_fee").first()
            setting.value = "50.00"
            db.session.commit()

    def test_11_payment_history_and_invoice_rendering(self):
        """Learner can view profile unlock in payment history and download/view invoice."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner1_id
            sess["csrf_token"] = "csrf-token-123"

        # Complete payment
        self.client.post(
            f"/payments/mentor/{self.mentor_id}/unlock-details",
            data={"csrf_token": "csrf-token-123", "demo_outcome": "success"},
            follow_redirects=True,
        )

        with self.app.app_context():
            access = MentorProfileAccess.query.filter_by(learner_id=self.learner1_id, mentor_id=self.mentor_id).first()
            self.assertIsNotNone(access)
            payment_id = access.payment_id

        # Check Learner payment history
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner1_id

        hist_res = self.client.get("/learner/payments")
        self.assertEqual(hist_res.status_code, 200)
        self.assertIn(b"Mentor Profile Unlock", hist_res.data)
        self.assertIn(b"50.00", hist_res.data)

        # Check Invoice page
        inv_res = self.client.get(f"/payments/invoice/{payment_id}")
        self.assertEqual(inv_res.status_code, 200)
        self.assertIn(b"Mentor Profile Access Unlock", inv_res.data)
        self.assertIn(b"Platform Access Fee:", inv_res.data)
        self.assertIn(b"50.00", inv_res.data)

        # Another learner cannot see learner1's invoice
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner2_id

        inv_res2 = self.client.get(f"/payments/invoice/{payment_id}")
        self.assertEqual(inv_res2.status_code, 403)

        # Admin can view the invoice
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin_id

        inv_res3 = self.client.get(f"/payments/invoice/{payment_id}")
        self.assertEqual(inv_res3.status_code, 200)
        self.assertIn(b"Mentor Profile Access Unlock", inv_res3.data)

    def test_12_admin_dashboard_shows_settings_panel(self):
        """Admin dashboard displays the Mentor Profile Access Settings panel."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin_id

        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Mentor profile access settings", res.data)
        self.assertIn(b"Global unlock fee:", res.data)
        self.assertIn(b"50.00", res.data)


    def test_13_mentor_with_all_three_details_shows_unlock_option(self):
        """Case 1: Mentor with LinkedIn + GitHub + Website shows unlock option and all 3 locked badges."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner2_id

        res = self.client.get("/mentor/4")  # Tanvir Rahman has all 3
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Professional & Contact Details", res.data)
        self.assertIn(b"Unlock Professional Details", res.data)
        self.assertIn(b"LinkedIn Profile \xc2\xb7 Locked", res.data)
        self.assertIn(b"GitHub Profile \xc2\xb7 Locked", res.data)
        self.assertIn(b"Website \xc2\xb7 Locked", res.data)

    def test_14_mentor_with_only_linkedin_shows_unlock_option(self):
        """Case 2: Mentor with only LinkedIn shows unlock option and ONLY LinkedIn locked badge."""
        with self.app.app_context():
            user = db.session.get(User, 5)
            user.mentor_profile.linkedin_url = "https://linkedin.com/in/sadia-test"
            user.mentor_profile.github_url = None
            user.mentor_profile.website_url = None
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner2_id

        res = self.client.get("/mentor/5")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Professional & Contact Details", res.data)
        self.assertIn(b"Unlock Professional Details", res.data)
        self.assertIn(b"LinkedIn Profile \xc2\xb7 Locked", res.data)
        self.assertNotIn(b"GitHub Profile \xc2\xb7 Locked", res.data)
        self.assertNotIn(b"Website \xc2\xb7 Locked", res.data)

    def test_15_mentor_with_only_github_shows_unlock_option(self):
        """Case 3: Mentor with only GitHub shows unlock option and ONLY GitHub locked badge."""
        with self.app.app_context():
            user = db.session.get(User, 5)
            user.mentor_profile.linkedin_url = None
            user.mentor_profile.github_url = "https://github.com/sadia-test"
            user.mentor_profile.website_url = None
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner2_id

        res = self.client.get("/mentor/5")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Professional & Contact Details", res.data)
        self.assertIn(b"Unlock Professional Details", res.data)
        self.assertNotIn(b"LinkedIn Profile \xc2\xb7 Locked", res.data)
        self.assertIn(b"GitHub Profile \xc2\xb7 Locked", res.data)
        self.assertNotIn(b"Website \xc2\xb7 Locked", res.data)

    def test_16_mentor_with_only_website_shows_unlock_option(self):
        """Case 4: Mentor with only Website shows unlock option and ONLY Website locked badge."""
        with self.app.app_context():
            user = db.session.get(User, 5)
            user.mentor_profile.linkedin_url = None
            user.mentor_profile.github_url = None
            user.mentor_profile.website_url = "https://sadia-test.dev"
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner2_id

        res = self.client.get("/mentor/5")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Professional & Contact Details", res.data)
        self.assertIn(b"Unlock Professional Details", res.data)
        self.assertNotIn(b"LinkedIn Profile \xc2\xb7 Locked", res.data)
        self.assertNotIn(b"GitHub Profile \xc2\xb7 Locked", res.data)
        self.assertIn(b"Website \xc2\xb7 Locked", res.data)

    def test_17_mentor_with_linkedin_and_github_shows_unlock_option(self):
        """Case 5: Mentor with LinkedIn + GitHub shows unlock option and only those 2 badges."""
        with self.app.app_context():
            user = db.session.get(User, 5)
            user.mentor_profile.linkedin_url = "https://linkedin.com/in/sadia-test"
            user.mentor_profile.github_url = "https://github.com/sadia-test"
            user.mentor_profile.website_url = None
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner2_id

        res = self.client.get("/mentor/5")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Professional & Contact Details", res.data)
        self.assertIn(b"Unlock Professional Details", res.data)
        self.assertIn(b"LinkedIn Profile \xc2\xb7 Locked", res.data)
        self.assertIn(b"GitHub Profile \xc2\xb7 Locked", res.data)
        self.assertNotIn(b"Website \xc2\xb7 Locked", res.data)

    def test_18_mentor_with_no_details_completely_hides_unlock_section(self):
        """Case 6: Mentor with NO details has the entire professional details unlock section hidden."""
        with self.app.app_context():
            user = db.session.get(User, 5)
            user.mentor_profile.linkedin_url = None
            user.mentor_profile.github_url = None
            user.mentor_profile.website_url = None
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner2_id

        res = self.client.get("/mentor/5")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"Professional & Contact Details", res.data)
        self.assertNotIn(b"Unlock Professional Details", res.data)
        self.assertNotIn(b"Unlock to view", res.data)
        self.assertNotIn(b"LinkedIn Profile \xc2\xb7 Locked", res.data)
        self.assertNotIn(b"GitHub Profile \xc2\xb7 Locked", res.data)
        self.assertNotIn(b"Website \xc2\xb7 Locked", res.data)

    def test_19_direct_access_to_unlock_checkout_rejected_if_no_details(self):
        """Case 7: Learner attempting direct access to unlock empty mentor details is rejected safely."""
        with self.app.app_context():
            user = db.session.get(User, 5)
            user.mentor_profile.linkedin_url = None
            user.mentor_profile.github_url = None
            user.mentor_profile.website_url = None
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner2_id
            sess["csrf_token"] = "csrf-token-test-19"

        # 1. GET request should redirect back to mentor profile with warning
        res = self.client.get("/payments/mentor/5/unlock-details", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"does not have any professional contact details to unlock", res.data)

        # 2. POST request should also reject safely without creating payment or entitlement
        post_res = self.client.post(
            "/payments/mentor/5/unlock-details",
            data={"csrf_token": "csrf-token-test-19", "demo_outcome": "success"},
            follow_redirects=True
        )
        self.assertEqual(post_res.status_code, 200)
        self.assertIn(b"does not have any professional contact details to unlock", post_res.data)

        with self.app.app_context():
            access = MentorProfileAccess.query.filter_by(learner_id=self.learner2_id, mentor_id=5).first()
            self.assertIsNone(access)

    def test_20_mentor_later_adds_linkedin_and_unlock_becomes_available(self):
        """Case 8: When mentor later adds a LinkedIn URL, the unlock option appears automatically."""
        with self.app.app_context():
            user = db.session.get(User, 5)
            user.mentor_profile.linkedin_url = None
            user.mentor_profile.github_url = None
            user.mentor_profile.website_url = None
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner2_id

        # Initially hidden
        res1 = self.client.get("/mentor/5")
        self.assertNotIn(b"Unlock Professional Details", res1.data)

        # Mentor adds LinkedIn
        with self.app.app_context():
            user = db.session.get(User, 5)
            user.mentor_profile.linkedin_url = "https://linkedin.com/in/sadia-new"
            db.session.commit()

        # Now automatically visible
        res2 = self.client.get("/mentor/5")
        self.assertIn(b"Unlock Professional Details", res2.data)
        self.assertIn(b"LinkedIn Profile \xc2\xb7 Locked", res2.data)

    def test_21_mentor_removes_last_detail_and_unlock_disappears(self):
        """Case 9: When mentor removes their last professional detail, the unlock option disappears."""
        with self.app.app_context():
            user = db.session.get(User, 5)
            user.mentor_profile.linkedin_url = "https://linkedin.com/in/sadia-new"
            user.mentor_profile.github_url = None
            user.mentor_profile.website_url = None
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.learner2_id

        # Visible
        res1 = self.client.get("/mentor/5")
        self.assertIn(b"Unlock Professional Details", res1.data)

        # Mentor removes detail
        with self.app.app_context():
            user = db.session.get(User, 5)
            user.mentor_profile.linkedin_url = None
            db.session.commit()

        # Disappears
        res2 = self.client.get("/mentor/5")
        self.assertNotIn(b"Unlock Professional Details", res2.data)
        self.assertNotIn(b"Professional & Contact Details", res2.data)


if __name__ == "__main__":
    unittest.main()

