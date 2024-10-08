DROP TABLE IF EXISTS USERS;
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
	user_name varchar(255) NOT NULL UNIQUE,
    user_email TEXT NOT NULL UNIQUE,
	user_role varchar(100),
	user_created date default NOW(),
    hashed_password BYTEA NOT NULL
);
DROP TABLE IF EXISTS DELETED_USERS;
CREATE TABLE deleted_users (
    user_id SERIAL PRIMARY KEY,
    user_name varchar(255) NOT NULL UNIQUE,
    user_email TEXT NOT NULL UNIQUE,
    user_role varchar(100),
    user_created date default NOW(),
    hashed_password BYTEA NOT NULL
)