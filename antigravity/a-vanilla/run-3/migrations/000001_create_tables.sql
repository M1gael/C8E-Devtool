-- UP
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    published_year INTEGER NOT NULL,
    isbn TEXT NOT NULL,
    cover_image TEXT DEFAULT ''
);

CREATE TABLE members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    join_date TEXT NOT NULL
);

CREATE TABLE loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    borrow_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    returned INTEGER NOT NULL DEFAULT 0,
    returned_date TEXT,
    FOREIGN KEY(book_id) REFERENCES books(id),
    FOREIGN KEY(member_id) REFERENCES members(id)
);

CREATE TABLE staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER,
    action TEXT NOT NULL,
    target_id INTEGER,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(staff_id) REFERENCES staff(id)
);

CREATE INDEX idx_books_title ON books(title);
CREATE INDEX idx_books_author ON books(author);
CREATE INDEX idx_books_published_year ON books(published_year);
CREATE INDEX idx_loans_returned ON loans(returned);
CREATE INDEX idx_loans_book_id ON loans(book_id);
CREATE INDEX idx_loans_member_id ON loans(member_id);
