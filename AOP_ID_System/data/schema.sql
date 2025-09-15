CREATE TABLE admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    sex TEXT,
    dob TEXT,
    blood_group TEXT,
    course TEXT,
    reg_no TEXT UNIQUE NOT NULL,
    level TEXT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    passport TEXT,
    signature TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);