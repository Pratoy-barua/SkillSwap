-- Initial SkillSwap database bootstrap.
-- Docker creates the database from MYSQL_DATABASE; this file documents UTF-8 settings.
CREATE DATABASE IF NOT EXISTS skillswap
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE skillswap;

CREATE TABLE IF NOT EXISTS schema_migrations (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    version VARCHAR(64) NOT NULL UNIQUE,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
