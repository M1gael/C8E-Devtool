-- Migration: create_library_tables
-- Created: 2026-07-08 12:00:00

CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    published_year INTEGER NOT NULL,
    isbn TEXT NOT NULL UNIQUE,
    cover_image TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_books_title ON books(title);
CREATE INDEX idx_books_author ON books(author);
CREATE INDEX idx_books_published_year ON books(published_year);

CREATE TABLE members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    join_date TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_members_email ON members(email);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    borrow_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    returned_date TEXT DEFAULT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE INDEX idx_loans_book_id ON loans(book_id);
CREATE INDEX idx_loans_member_id ON loans(member_id);
CREATE INDEX idx_loans_returned_date ON loans(returned_date);

CREATE TABLE activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Seed Data

-- 1. Seeding Library Staff (password: password123)
INSERT INTO users (name, email, password_hash)
VALUES ('Library Staff', 'staff@library.com', '$2y$12$SpdPqp.QB2A3lf.gIaUB3.CqVJ7.wpTFttkA4v2LsbY/A3g7BLFmy');

-- 2. Seeding Sample Members
INSERT INTO members (name, email, join_date) VALUES 
('Alice Johnson', 'alice@demo.com', '2026-01-15'),
('Bob Smith', 'bob@demo.com', '2026-02-20'),
('Charlie Brown', 'charlie@demo.com', '2026-03-10');

-- 3. Seeding Sample Books
INSERT INTO books (title, author, published_year, isbn, cover_image) VALUES 
('The Hobbit', 'J.R.R. Tolkien', 1937, '9780048231888', '/images/default_cover.jpg'),
('1984', 'George Orwell', 1949, '9780451524935', '/images/default_cover.jpg'),
('To Kill a Mockingbird', 'Harper Lee', 1960, '9780061120084', '/images/default_cover.jpg'),
('The Great Gatsby', 'F. Scott Fitzgerald', 1925, '9780743273565', '/images/default_cover.jpg'),
('Pride and Prejudice', 'Jane Austen', 1813, '9780141439518', '/images/default_cover.jpg');
