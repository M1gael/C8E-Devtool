-- DOWN
DROP INDEX IF EXISTS idx_loans_member_id;
DROP INDEX IF EXISTS idx_loans_book_id;
DROP INDEX IF EXISTS idx_loans_returned;
DROP INDEX IF EXISTS idx_books_published_year;
DROP INDEX IF EXISTS idx_books_author;
DROP INDEX IF EXISTS idx_books_title;
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS staff;
DROP TABLE IF EXISTS loans;
DROP TABLE IF EXISTS members;
DROP TABLE IF EXISTS books;
