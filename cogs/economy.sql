CREATE TABLE IF NOT EXISTS "user" (
	"user_id"	INTEGER NOT NULL,
	"guild_id"	INTEGER NOT NULL,
	"name"	TEXT,
	"points"    INTEGER NOT NULL DEFAULT 0,
	"stocks"	INTEGER NOT NULL DEFAULT 0,
	PRIMARY KEY("user_id", "guild_id")
);

CREATE TABLE IF NOT EXISTS "activity" (
	"timestamp"	TEXT NOT NULL,
	"user_id"	INTEGER NOT NULL,
	"guild_id"	INTEGER,
	"type"	TEXT NOT NULL,
	"amount"	INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS "stock" (
	"timestamp"	TEXT NOT NULL,
	"price"	INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS "event" (
	"start"	TEXT NOT NULL,
	"end"	TEXT NOT NULL,
	"value"	INTEGER NOT NULL,
	"name"	TEXT NOT NULL
);