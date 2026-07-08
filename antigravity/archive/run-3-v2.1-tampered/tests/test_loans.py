from tina4_python.test import Test, assert_equal, assert_true, assert_none, assert_not_none
from src.orm.book import Book
from src.orm.member import Member
from src.orm.loan import Loan
from src.orm.staff import Staff
from tina4_python.queue import Queue
import json
import uuid

class LoansTest(Test):
    def set_up(self):
        # Clear tables
        for b in Book.all():
            try: b.delete()
            except Exception: pass
        for m in Member.all():
            try: m.delete()
            except Exception: pass
        for l in Loan.all():
            try: l.delete()
            except Exception: pass
        for s in Staff.all():
            try: s.delete()
            except Exception: pass

        # Create staff, book, member
        self.staff = Staff()
        self.staff.name = "Staff Member"
        self.staff.email = "staff@library.com"
        self.staff.set_password("password123")
        self.staff.save()

        self.book = Book()
        self.book.title = "The Odyssey"
        self.book.author = "Homer"
        self.book.published_year = -800
        self.book.isbn = "9780140268867"
        self.book.save()

        self.member = Member()
        self.member.name = "Odysseus"
        self.member.email = "odysseus@ithaca.gr"
        self.member.join_date = "2026-07-08"
        self.member.save()

        # Login to get token
        resp = self.post("/api/login", json={
            "email": "staff@library.com",
            "password": "password123"
        })
        self.token = json.loads(resp.text())["token"]

    def test_loan_lifecycle_and_queue(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # 1. Book should be available initially
        resp_book = self.get(f"/api/books/{self.book.id}")
        body_book = json.loads(resp_book.text())
        assert_true(body_book["is_available"], "Book should be available initially")

        # 2. Record a loan
        loan_payload = {
            "book_id": self.book.id,
            "member_id": self.member.id,
            "due_date": "2026-07-22"
        }
        
        # Clear email queue topic first
        q = Queue(topic="loans_email")
        q.purge("pending")
        
        resp_loan = self.post("/api/loans", json=loan_payload, headers=headers)
        assert_equal(resp_loan.status, 201, "Loan should be created successfully")
        body_loan = json.loads(resp_loan.text())
        loan_id = body_loan["loan"]["id"]

        # 3. Book should now be unavailable
        resp_book_borrowed = self.get(f"/api/books/{self.book.id}")
        body_book_borrowed = json.loads(resp_book_borrowed.text())
        assert_true(not body_book_borrowed["is_available"], "Book should be unavailable/borrowed")

        # 4. Reject duplicate borrowing attempt
        resp_dup = self.post("/api/loans", json=loan_payload, headers=headers)
        assert_equal(resp_dup.status, 400, "Should reject borrowing a borrowed book")
        assert_true("already out on loan" in json.loads(resp_dup.text())["error"], "Error message should state the book is already out on loan")

        # 5. Verify email receipt job is queued
        assert_true(q.size() > 0, "An email receipt job should be queued in loans_email topic")
        job = q.pop()
        assert_not_none(job, "Queue job should exist")
        assert_equal(job.payload["member_email"], "odysseus@ithaca.gr", "Queue job recipient should match member email")
        job.complete() # Clean up queue

        # 6. Record a return
        resp_return = self.post(f"/api/loans/return/{loan_id}", json={}, headers=headers)
        assert_equal(resp_return.status, 200, "Return should succeed")

        # 7. Book should be available again
        resp_book_returned = self.get(f"/api/books/{self.book.id}")
        body_book_returned = json.loads(resp_book_returned.text())
        assert_true(body_book_returned["is_available"], "Book should be available again after return")
