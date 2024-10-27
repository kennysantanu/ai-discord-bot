CREATE TABLE IF NOT EXISTS "user" (
	"user_id"	TEXT NOT NULL,
	"name"	TEXT,
	"nickname"	TEXT,
    "points"    INTEGER NOT NULL DEFAULT 0,
	"generation_token"	INTEGER NOT NULL DEFAULT 4,
	PRIMARY KEY("user_id")
);
