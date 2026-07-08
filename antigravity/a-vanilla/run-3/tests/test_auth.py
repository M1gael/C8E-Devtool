from tina4_python.test import Test, assert_equal, assert_true, assert_not_none
from src.orm.staff import Staff
import json
import uuid

class AuthTest(Test):
    def set_up(self):
        # Clear staff table
        all_staff = Staff.all()
        for s in all_staff:
            try:
                s.delete()
            except Exception:
                pass
                
        self.staff_email = f"staff-{uuid.uuid4().hex[:8]}@library.com"
        self.staff_password = "securepassword123"
        self.staff_name = "Library Staff"

    def test_register_and_login(self):
        # 1. Register staff
        reg_payload = {
            "name": self.staff_name,
            "email": self.staff_email,
            "password": self.staff_password
        }
        resp = self.post("/api/register", json=reg_payload)
        assert_equal(resp.status, 201, "Registration should return 201")
        
        # Try duplicate email
        resp_dup = self.post("/api/register", json=reg_payload)
        assert_equal(resp_dup.status, 409, "Duplicate registration should conflict with 409")

        # 2. Login
        login_payload = {
            "email": self.staff_email,
            "password": self.staff_password
        }
        resp_login = self.post("/api/login", json=login_payload)
        assert_equal(resp_login.status, 200, "Login should succeed with 200")
        body_login = json.loads(resp_login.text())
        assert_not_none(body_login.get("token"), "Should return JWT token")
        
        # 3. Test protected route without auth token
        resp_protected_fail = self.post("/api/books", json={"title": "Test", "author": "Test", "published_year": 2026, "isbn": "123"})
        assert_equal(resp_protected_fail.status, 401, "Protected API should reject unauthorized requests with 401")
        
        # 4. Test protected route with valid auth token
        token = body_login["token"]
        resp_protected_success = self.post("/api/books", json={
            "title": "A Secret Book",
            "author": "Anonymous",
            "published_year": 2020,
            "isbn": "9781234567890"
        }, headers={"Authorization": f"Bearer {token}"})
        assert_equal(resp_protected_success.status, 201, "Protected API should allow authenticated requests with 201")
