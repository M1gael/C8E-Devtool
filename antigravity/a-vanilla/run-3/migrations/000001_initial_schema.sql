-- Migration: 000001_initial_schema
-- Created: 2026-07-09

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    published_year INTEGER NOT NULL,
    isbn TEXT NOT NULL,
    cover_image TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    join_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    borrow_date DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date DATE NOT NULL,
    returned INTEGER DEFAULT 0,
    returned_date DATE,
    staff_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Seed initial staff user
INSERT INTO users (name, email, password) VALUES (
    'Library Staff',
    'staff@library.com',
    'pbkdf2_sha256$260000$c2af468ce45ea058160657636a55cec7$390ee44919862333edd726d078509c8e3d23226ad10ba6ebffd0f2ecd8d92c29'
);
