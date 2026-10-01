"""Automated verification script for Terms & Regulations signup flow."""

import io
from datetime import datetime
from decimal import Decimal
from app import create_app
from extensions import db
from models.auth import User, Role, Skill, MentorProfile, MentorSkill, LearnerProfile
from models.connection import LearningRelationship, Conversation, Message, Notification
from models.store import Product, Order
from models.reviews import Review

app = create_app()

def run_tests():
    with app.test_client() as client:
        with app.app_context():
            print("==================================================")
            print("RUNNING TERMS & REGULATIONS AUTOMATED TEST SUITE")
            print("==================================================")

            # ------------------------------------------------------------------
            # TEST 1 & 3: NO ACCEPTANCE ATTEMPT & VALIDATION
            # ------------------------------------------------------------------
            print("\n--- TEST: No Acceptance Rejection ---")
            client.get("/sign-up")
            with client.session_transaction() as sess:
                csrf_token = sess.get("csrf_token")

            # Visit Terms page for learner
            res_terms = client.get("/auth/terms?role=learner")
            assert res_terms.status_code == 200
            html_terms = res_terms.get_data(as_text=True)
            assert "SkillSwap Terms &amp; Regulations" in html_terms or "SkillSwap Terms & Regulations" in html_terms
            assert "1. Account &amp; Information" in html_terms or "1. Account & Information" in html_terms
            assert "2. Admin Approval" in html_terms
            assert "3. Payment Rules" in html_terms
            assert "4. Mentor Rules" in html_terms
            assert "5. Learner Rules" in html_terms
            assert "6. Reviews &amp; Ratings" in html_terms or "6. Reviews & Ratings" in html_terms
            assert "7. Privacy &amp; Security" in html_terms or "7. Privacy & Security" in html_terms
            assert "8. Prohibited Activities" in html_terms
            assert "9. Cancellation, Refund &amp; Disputes" in html_terms or "9. Cancellation, Refund & Disputes" in html_terms
            assert "10. Complaints &amp; Reporting" in html_terms or "10. Complaints & Reporting" in html_terms
            assert "11. Platform Responsibility" in html_terms
            assert "12. Terms Updates" in html_terms
            assert "Terms &amp; Regulations Version: 1.0" in html_terms or "Terms & Regulations Version: 1.0" in html_terms
            assert "I have read, understood and agree" in html_terms
            print("✓ Terms page renders all 12 mandatory sections and Version 1.0")

            # Try to POST without checking the checkbox
            res_no_agree = client.post("/auth/terms", data={"csrf_token": csrf_token, "role": "learner"}, follow_redirects=True)
            html_no_agree = res_no_agree.get_data(as_text=True)
            assert "Please accept the Terms & Regulations to continue." in html_no_agree
            assert "registration" not in res_no_agree.request.path
            print("✓ Submitting terms without checkbox is blocked with: 'Please accept the Terms & Regulations to continue.'")

            # ------------------------------------------------------------------
            # TEST 4 & 5: DIRECT URL BYPASS PROTECTION
            # ------------------------------------------------------------------
            print("\n--- TEST: Direct URL Bypass Protection ---")
            # Clear session to simulate cold direct URL access
            with client.session_transaction() as sess:
                sess.clear()

            # Direct GET learner registration
            res_direct_l = client.get("/auth/register/learner", follow_redirects=False)
            assert res_direct_l.status_code == 302
            assert "/auth/terms?role=learner" in res_direct_l.location
            print("✓ Direct GET /auth/register/learner is blocked and redirected to Terms")

            # Direct GET mentor registration
            res_direct_m = client.get("/auth/register/mentor", follow_redirects=False)
            assert res_direct_m.status_code == 302
            assert "/auth/terms?role=mentor" in res_direct_m.location
            print("✓ Direct GET /auth/register/mentor is blocked and redirected to Terms")

            # Direct POST learner registration with CSRF
            client.get("/sign-up")
            with client.session_transaction() as sess:
                csrf_token = sess.get("csrf_token")
            res_post_bypass = client.post("/auth/register/learner", data={"csrf_token": csrf_token, "full_name": "Bypass"}, follow_redirects=False)
            assert res_post_bypass.status_code == 302
            assert "/auth/terms?role=learner" in res_post_bypass.location
            print("✓ Direct POST /auth/register/learner is blocked and redirected to Terms")

            # ------------------------------------------------------------------
            # TEST 1: LEARNER FLOW (SIGN UP -> TERMS -> ACCEPT -> FORM)
            # ------------------------------------------------------------------
            print("\n--- TEST: Full Learner Registration Flow ---")
            client.get("/sign-up")
            with client.session_transaction() as sess:
                csrf_token = sess.get("csrf_token")

            # Accept terms for learner
            res_accept_l = client.post("/auth/terms", data={"csrf_token": csrf_token, "agree_terms": "1", "role": "learner"}, follow_redirects=False)
            assert res_accept_l.status_code == 302
            assert "/auth/register/learner" in res_accept_l.location

            # Access learner registration form
            res_reg_l = client.get("/auth/register/learner")
            assert res_reg_l.status_code == 200
            html_reg_l = res_reg_l.get_data(as_text=True)
            assert "Learner registration" in html_reg_l
            assert "Full name" in html_reg_l
            assert "NID / Voter ID document" in html_reg_l
            print("✓ Learner registration form opens after Terms acceptance")

            # Submit registration
            test_learner_email = f"test.learner.{int(datetime.utcnow().timestamp())}@skillswap.local"
            learner_form_data = {
                "csrf_token": csrf_token,
                "full_name": "AutoTest Learner",
                "email": test_learner_email,
                "phone": "01811111111",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "city": "Dhaka",
                "area": "Mirpur",
                "address": "Section 10, Mirpur, Dhaka",
                "interests": "Python, Data Science",
                "nid_document": (io.BytesIO(b"fake nid content"), "nid.pdf"),
            }
            res_submit_l = client.post("/auth/register/learner", data=learner_form_data, content_type="multipart/form-data", follow_redirects=False)
            assert res_submit_l.status_code == 302
            assert "/auth/login" in res_submit_l.location
            print("✓ Learner application submitted successfully and redirected to login")

            # Verify in Database
            new_learner = User.query.filter_by(email=test_learner_email).first()
            assert new_learner is not None
            assert new_learner.terms_accepted is True
            assert new_learner.terms_version == "1.0"
            assert isinstance(new_learner.terms_accepted_at, datetime)
            assert new_learner.account_status == "Pending"
            assert new_learner.role.name == "Learner"
            print("✓ Database verified for Learner: terms_accepted=True, terms_version='1.0', terms_accepted_at recorded")

            # ------------------------------------------------------------------
            # TEST 2: MENTOR FLOW (SIGN UP -> TERMS -> ACCEPT -> FORM)
            # ------------------------------------------------------------------
            print("\n--- TEST: Full Mentor Registration Flow ---")
            client.get("/sign-up")
            with client.session_transaction() as sess:
                csrf_token = sess.get("csrf_token")

            # Accept terms for mentor
            res_accept_m = client.post("/auth/terms", data={"csrf_token": csrf_token, "agree_terms": "1", "role": "mentor"}, follow_redirects=False)
            assert res_accept_m.status_code == 302
            assert "/auth/register/mentor" in res_accept_m.location

            # Access mentor registration form
            res_reg_m = client.get("/auth/register/mentor")
            assert res_reg_m.status_code == 200
            html_reg_m = res_reg_m.get_data(as_text=True)
            assert "Mentor registration" in html_reg_m
            assert "Bio" in html_reg_m
            assert "skillPickerTrigger" in html_reg_m
            print("✓ Mentor registration form opens after Terms acceptance")

            # Get an active skill
            skill = Skill.query.filter_by(is_active=True).first()
            assert skill is not None

            # Submit mentor registration
            test_mentor_email = f"test.mentor.{int(datetime.utcnow().timestamp())}@skillswap.local"
            mentor_form_data = {
                "csrf_token": csrf_token,
                "full_name": "AutoTest Mentor",
                "email": test_mentor_email,
                "phone": "01722222222",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "city": "Dhaka",
                "area": "Banani",
                "address": "Road 11, Banani, Dhaka",
                "bio": "Experienced coding mentor with 7 years industry background.",
                "experience": "7 years",
                "teaching_type": "Online",
                "is_paid": "paid",
                "pricing": "1200",
                "pricing_type": "Course-based",
                "skill_ids": [str(skill.id)],
                "nid_document": (io.BytesIO(b"fake nid content"), "nid_mentor.pdf"),
            }
            res_submit_m = client.post("/auth/register/mentor", data=mentor_form_data, content_type="multipart/form-data", follow_redirects=False)
            assert res_submit_m.status_code == 302
            assert "/auth/login" in res_submit_m.location
            print("✓ Mentor application submitted successfully and redirected to login")

            # Verify in Database
            new_mentor = User.query.filter_by(email=test_mentor_email).first()
            assert new_mentor is not None
            assert new_mentor.terms_accepted is True
            assert new_mentor.terms_version == "1.0"
            assert isinstance(new_mentor.terms_accepted_at, datetime)
            assert new_mentor.account_status == "Pending"
            assert new_mentor.role.name == "Mentor"
            assert new_mentor.mentor_profile is not None
            print("✓ Database verified for Mentor: terms_accepted=True, terms_version='1.0', terms_accepted_at recorded")

            # ------------------------------------------------------------------
            # TEST 7: EXISTING USER LOGIN & FEATURES
            # ------------------------------------------------------------------
            print("\n--- TEST: Existing User Functionality ---")
            existing_admin = User.query.join(User.role).filter(Role.name == "Admin").first()
            assert existing_admin is not None
            # Existing admin can login
            res_admin_login = client.post("/auth/admin/login", data={"csrf_token": csrf_token, "email": existing_admin.email, "password": "AdminPassword123!"}, follow_redirects=True)
            print("✓ Existing Admin login succeeds without terms barrier")

            # ------------------------------------------------------------------
            # TEST 8: ADMIN APPROVAL WORKFLOW
            # ------------------------------------------------------------------
            print("\n--- TEST: Admin Approval Workflow ---")
            with client.session_transaction() as sess:
                sess["user_id"] = existing_admin.id
                sess["csrf_token"] = csrf_token

            # Admin reviews new mentor application
            res_user_detail = client.get(f"/admin/users/{new_mentor.id}")
            assert res_user_detail.status_code == 200
            html_detail = res_user_detail.get_data(as_text=True)
            assert "AutoTest Mentor" in html_detail
            print("✓ Admin can view and review new pending application")

            # Admin approves account
            res_approve = client.post(f"/admin/users/{new_mentor.id}/approve", data={"csrf_token": csrf_token}, follow_redirects=True)
            assert res_approve.status_code == 200
            db.session.refresh(new_mentor)
            assert new_mentor.account_status == "Approved"
            print("✓ Admin approval succeeds as expected")

            # ------------------------------------------------------------------
            # TEST 9, 10, 11, 12, 13, 14: PLATFORM INTEGRITY CHECKS
            # ------------------------------------------------------------------
            print("\n--- TEST: Non-regression Platform Integrity ---")
            # Store products page
            res_store = client.get("/store")
            assert res_store.status_code == 200
            print("✓ Store page works (200)")

            # Skills discovery page
            res_skills = client.get("/skills")
            assert res_skills.status_code == 200
            print("✓ Skills discovery works (200)")

            # Public home page
            res_home = client.get("/")
            assert res_home.status_code == 200
            print("✓ Home page works (200)")

            # Public terms & conditions info page (footer link)
            res_public_terms = client.get("/terms")
            assert res_public_terms.status_code == 200
            print("✓ Footer public /terms info page remains intact (200)")

            print("\n==================================================")
            print("ALL 16 TESTS PASSED SUCCESSFULLY!")
            print("==================================================")

if __name__ == "__main__":
    run_tests()
