CREATE TABLE IF NOT EXISTS normalEvents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    time TEXT NOT NULL,
    delay INTEGER NOT NULL,
    tone TEXT NOT NULL,
    active INTEGER NOT NULL CHECK (active IN (0,1)),
    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    frequency TEXT NOT NULL -- JSON string array e.g., '["monday","wednesday"]'
);

CREATE TABLE IF NOT EXISTS specialEvents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL, -- Format 'YYYY-MM-DD'
    time TEXT NOT NULL,
    description TEXT NOT NULL,
    tone TEXT NOT NULL,
    completed INTEGER NOT NULL CHECK (completed IN (0,1)),
    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS esp32 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    time TEXT NOT NULL,
    delay INTEGER NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('normal', 'special'))
);
