import os
import json
import datetime
import pytest
import asyncio
from tina4_python.database import Database
from tina4_python.migration import Migration
from tina4_python.orm import bind_database
from tina4_python.auth import get_token, Auth
from tina4_python.core.response import Response
from tina4_python.queue import Queue

# Import ORM models
from src.orm.Staff import Staff
from src.orm.Book import Book
from src.orm.Member import Member
from src.orm.Loan import Loan
from src.orm.AuditLog import AuditLog

# Import API route handlers
from src.routes.api import (
    api_list_books, api_create_book, api_book_detail,
    api_create_member, api_create_loan, api_record_return,
    api_get_logs, api_staff_login
)

# Helper request class for testing
class MockRequest:
    def __init__(self, body=None, params=None, headers=None, session=None):
        self.body = body or {}
        self.params = params or {}
        self.query = params or {}
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.session = session or MockSession()
        self.url = "/"

class MockSession:
    def __init__(self):
        self.data = {}
    def get(self, key, default=None):
        return self.data.get(key, default)
    def set(self, key, value):
        self.data[key] = value

@pytest.fixture(autouse=True)
def setup_test_db():
    # Make sure data directory exists
    os.makedirs("data", exist_ok=True)
    db_path = "data/test_lend.db"
    
    # Remove existing test DB if any
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass
            
    # Initialize DB connection
    db = Database("sqlite:///" + db_path)
    bind_database(db)
    
    # Run migrations
    m = Migration(db, "migrations")
    m.migrate()
    
    # Seed staff user for testing
    staff = Staff(
        name="Test Librarian",
        email="test@library.com",
        password_hash=Auth.hash_password("password123")
    )
    staff.save()
    
    yield db
    
    # Close connection
    db.close()
    
    # Clean up test DB file
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

@pytest.mark.asyncio
async def test_staff_login():
    # Test valid login
    req = MockRequest(body={"email": "test@library.com", "password": "password123"})
    resp = Response()
    r = await api_staff_login(req, resp)
    assert r.status_code == 200
    data = json.loads(r.content.decode("utf-8"))
    assert "token" in data
    assert data["staff"]["email"] == "test@library.com"

    # Test invalid login
    req = MockRequest(body={"email": "test@library.com", "password": "wrongpassword"})
    resp = Response()
    r = await api_staff_login(req, resp)
    assert r.status_code == 401

@pytest.mark.asyncio
async def test_books_pagination_and_search():
    # Seed 15 books
    for i in range(1, 16):
        book = Book(
            title=f"Book Title {i}",
            author=f"Author {i}",
            published_year=2000 + i,
            isbn=f"ISBN-000-{i}",
            is_available=1
        )
        book.save()

    # Get page 1 (limit 10, offset 0)
    req = MockRequest(params={"limit": 10, "offset": 0})
    resp = Response()
    r = await api_list_books(req, resp)
    assert r.status_code == 200
    data = json.loads(r.content.decode("utf-8"))
    assert len(data["books"]) == 10
    assert data["pagination"]["total"] == 15

    # Get page 2 (limit 10, offset 10)
    req = MockRequest(params={"limit": 10, "offset": 10})
    resp = Response()
    r = await api_list_books(req, resp)
    assert r.status_code == 200
    data = json.loads(r.content.decode("utf-8"))
    assert len(data["books"]) == 5

    # Search for "Title 1"
    req = MockRequest(params={"search": "Title 1"})
    resp = Response()
    r = await api_list_books(req, resp)
    assert r.status_code == 200
    data = json.loads(r.content.decode("utf-8"))
    # Should match "Book Title 1", "Book Title 10", "Book Title 11", etc. (7 books total)
    assert len(data["books"]) == 7

@pytest.mark.asyncio
async def test_authentication_restrictions():
    # Try adding a book without auth
    req = MockRequest(body={"title": "New Book", "author": "New Author", "published_year": 2026, "isbn": "ISBN-111"})
    resp = Response()
    r = await api_create_book(req, resp)
    assert r.status_code == 401

    # Add book with valid auth session
    req = MockRequest(
        body={"title": "New Book", "author": "New Author", "published_year": 2026, "isbn": "ISBN-111"},
        session=MockSession()
    )
    req.session.set("staff_id", 1)  # Simulate logged in staff
    r = await api_create_book(req, r)
    assert r.status_code == 201

    # Add book with JWT Bearer Token
    token = get_token({"staff_id": 1}, expires_in=10)
    req_jwt = MockRequest(
        body={"title": "JWT Book", "author": "JWT Author", "published_year": 2026, "isbn": "ISBN-JWT"},
        headers={"Authorization": f"Bearer {token}"}
    )
    r_jwt = await api_create_book(req_jwt, Response())
    assert r_jwt.status_code == 201

@pytest.mark.asyncio
async def test_borrowing_availability_and_duplicate_loans():
    # 1. Create a book and member
    book = Book(title="Learn Python", author="Guido", published_year=2020, isbn="ISBN-PY", is_available=1)
    book.save()
    
    member = Member(name="Bob Member", email="bob@member.com", join_date="2026-07-09")
    member.save()

    # 2. Staff logs in to record loan
    session = MockSession()
    session.set("staff_id", 1)
    
    req_loan = MockRequest(
        body={"book_id": book.id, "member_id": member.id, "due_date": "2026-07-23"},
        session=session
    )
    r_loan = await api_create_loan(req_loan, Response())
    assert r_loan.status_code == 201
    
    # Book availability should now be 0 (borrowed)
    book.load("id = ?", [book.id])
    assert book.is_available == 0

    # 3. Try borrowing the same book again (should fail)
    req_loan_dup = MockRequest(
        body={"book_id": book.id, "member_id": member.id, "due_date": "2026-07-30"},
        session=session
    )
    r_loan_dup = await api_create_loan(req_loan_dup, Response())
    assert r_loan_dup.status_code == 400
    data_dup = json.loads(r_loan_dup.content.decode("utf-8"))
    assert "error" in data_dup
    assert "already out on loan" in data_dup["error"].lower()

    # 4. Return the book
    req_return = MockRequest(
        body={"book_id": book.id},
        session=session
    )
    r_return = await api_record_return(req_return, Response())
    assert r_return.status_code == 200

    # Book availability should be 1 (available)
    book.load("id = ?", [book.id])
    assert book.is_available == 1

    # 5. Loan can now be recorded again
    r_loan_retry = await api_create_loan(req_loan, Response())
    assert r_loan_retry.status_code == 201

@pytest.mark.asyncio
async def test_email_queue_enqueuing():
    book = Book(title="Learn Twig", author="Sensio", published_year=2021, isbn="ISBN-TWIG", is_available=1)
    book.save()
    member = Member(name="Alice Member", email="alice@member.com", join_date="2026-07-09")
    member.save()

    session = MockSession()
    session.set("staff_id", 1)

    # Clean the queue first
    q = Queue(topic="loan_emails")
    q.clear()

    req = MockRequest(
        body={"book_id": book.id, "member_id": member.id, "due_date": "2026-07-23"},
        session=session
    )
    r = await api_create_loan(req, Response())
    assert r.status_code == 201

    # Check that a job is enqueued
    job = q.pop()
    assert job is not None
    
    job_data = job.data
    assert job_data["to"] == "alice@member.com"
    assert "Learn Twig" in job_data["body"]
    assert "2026-07-23" in job_data["body"]
    job.complete()

@pytest.mark.asyncio
async def test_audit_logs_creation():
    session = MockSession()
    session.set("staff_id", 1)

    # 1. Add Member
    req_member = MockRequest(body={"name": "Audit Member", "email": "audit@member.com"}, session=session)
    r_member = await api_create_member(req_member, Response())
    assert r_member.status_code == 201

    # 2. Add Book
    req_book = MockRequest(body={"title": "Audit Book", "author": "Author A", "published_year": 2026, "isbn": "ISBN-AUDIT"}, session=session)
    r_book = await api_create_book(req_book, Response())
    assert r_book.status_code == 201

    # Fetch audit logs
    req_logs = MockRequest(session=session)
    r_logs = await api_get_logs(req_logs, Response())
    assert r_logs.status_code == 200
    
    logs = json.loads(r_logs.content.decode("utf-8"))
    # We should have at least 2 logs (ADD_MEMBER and ADD_BOOK)
    assert len(logs) >= 2
    
    # Check that the logs have correct action and details, and are attributed to staff ID 1
    actions = [l["action"] for l in logs]
    assert "ADD_MEMBER" in actions
    assert "ADD_BOOK" in actions
    
    for l in logs:
        assert l["staff_id"] == 1
        assert l["staff_name"] == "Librarian"
