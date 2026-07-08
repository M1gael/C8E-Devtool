DROP INDEX IF EXISTS idx_loans_member;
DROP INDEX IF EXISTS idx_loans_book;
DROP INDEX IF EXISTS idx_members_email;
DROP INDEX IF EXISTS idx_books_author;
DROP INDEX IF EXISTS idx_books_title;

DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS staff;
DROP TABLE IF EXISTS loans;
DROP TABLE IF EXISTS members;
DROP TABLE IF EXISTS books;
