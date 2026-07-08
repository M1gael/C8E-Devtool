from tina4_python.test import Test, assert_equal, assert_true, assert_not_none
from src.orm.book import Book
import json

class CatalogTest(Test):
    def set_up(self):
        # Clear books table
        all_books = Book.all()
        for b in all_books:
            try:
                b.delete()
            except Exception:
                pass
            
        b1 = Book()
        b1.title = "The Hobbit"
        b1.author = "J.R.R. Tolkien"
        b1.published_year = 1937
        b1.isbn = "9780007487289"
        b1.save()
        
        b2 = Book()
        b2.title = "Neuromancer"
        b2.author = "William Gibson"
        b2.published_year = 1984
        b2.isbn = "9780441569953"
        b2.save()

    def test_catalog_list_and_search(self):
        # Test basic list
        resp = self.get("/api/books")
        assert_equal(resp.status, 200, "Catalog API should return 200")
        body = json.loads(resp.text())
        assert_equal(body["total"], 2, "Should return 2 seeded books")

        # Test search title
        resp = self.get("/api/books?search=Hobbit")
        body = json.loads(resp.text())
        assert_equal(len(body["books"]), 1, "Should filter to 1 book")
        assert_equal(body["books"][0]["title"], "The Hobbit", "Title should match search")

        # Test search year
        resp = self.get("/api/books?search=1984")
        body = json.loads(resp.text())
        assert_equal(len(body["books"]), 1, "Should filter by year")
        assert_equal(body["books"][0]["title"], "Neuromancer", "Title should match search by year")

    def test_catalog_detail(self):
        book = Book.where("title = ?", ["The Hobbit"])[0]
        resp = self.get(f"/api/books/{book.id}")
        assert_equal(resp.status, 200, "Details API should return 200")
        body = json.loads(resp.text())
        assert_equal(body["book"]["title"], "The Hobbit", "Detail title should match")
        assert_true(body["is_available"], "New book should be available")
