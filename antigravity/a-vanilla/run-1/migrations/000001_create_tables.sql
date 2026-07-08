CREATE TABLE IF NOT EXISTS book (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    published_year INTEGER NOT NULL,
    isbn TEXT NOT NULL,
    cover_image TEXT
);

CREATE TABLE IF NOT EXISTS member (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    join_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS loan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    borrow_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    returned INTEGER NOT NULL DEFAULT 0,
    returned_date TEXT,
    FOREIGN KEY (member_id) REFERENCES member (id),
    FOREIGN KEY (book_id) REFERENCES book (id)
);

CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (staff_id) REFERENCES staff (id)
);

INSERT OR IGNORE INTO staff (id, username, password, name) VALUES (1, 'admin', 'pbkdf2_sha256$260000$bbde08e0b11c61edd1ec26ee44fec994$b6f36bebd55c614aa86bb08b84e70940367ef5b4abb1b2b8228c52cfebd05089', 'Library Admin');
