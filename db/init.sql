
CREATE DATABASE IF NOT EXISTS appdb
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE appdb;


--  users
--  password  --- хэш (werkzeug, scrypt). Пароль НЕЛЬЗЯ "вытащить"
--                и подставить — он необратим. Поэтому цель атаки —
--                не пароль, а reset_token
--  reset_token --- секретный токен сброса пароля. Лежит в открытом
--                виде. Кто знает токен — может сменить пароль юзеру.
--                Это и есть то, что крадём слепой инъекцией по таймингу
DROP TABLE IF EXISTS users;
CREATE TABLE users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(100) NOT NULL UNIQUE,
    password      VARCHAR(255) NOT NULL,
    reset_token   VARCHAR(64)  DEFAULT NULL,
    reset_expires DATETIME     DEFAULT NULL,
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (username, email, password, reset_token, reset_expires) VALUES
    ('administrator', 'admin@demo.local',
     'scrypt:32768:8:1$JmeKWqXD4LS3gOIc$039ca2b98bdb88b99fdb75f7a146fea73fffe03c9e0dabe1d01e0d68a9bc6436952d0b6a81f25fca8371e5126ff2872815ab71c6392ae2b81c91e0fcb4480630',
     'a1b2c3d4e5', '2030-01-01 00:00:00'),
    ('alice', 'alice@demo.local',
     'scrypt:32768:8:1$DSsMV25wKOIhzJqb$f345f65e95995a9945899c2cd88ca6e870089337720db5dac53b4d2852db066a409858d8b8181db373a391eab2f7f06f15e46193df53fcb26317f7cf20ae8d2c',
     NULL, NULL),
    ('bob', 'bob@demo.local',
     'scrypt:32768:8:1$QwRVp2xv9dbBNklJ$947fa68577e1cb431ae0823f27c20b0f4443e1ec5444bd3ef7faa302673af94f6669bcb213aa6641fe5892fb8cba09864d0e4d1ef5e3779e037986425d56f1df',
     NULL, NULL),
    ('carol', 'carol@demo.local',
     'scrypt:32768:8:1$FIiplJNosuIfyuIr$e0f90ec0b7beae5fe18cd47263ec5db983c416fbe8f98282f874357446ee54c87731484237bf22d70f7b920b0e3d74740773bc56d89fe2e30648326fdaaf14fd',
     NULL, NULL),
    ('cheerep', 'cheerep@demo.local',
     'scrypt:32768:8:1$XsQGfjMZunQEg6mx$a14d6aed60c4928a2f5ac606852bad4132676d71742e80e1fc9bf56b1fdb2f853737f00fc1950170ad0c394dd2726062553b57c4264f24fbfabb21119f548634',
     NULL, NULL);

--  Права приложения (принцип минимальных привилегий — мера защиты).
-- Контейнер уже создаёт appuser; дублируем на случай ручного запуска.
CREATE USER IF NOT EXISTS 'appuser'@'%' IDENTIFIED BY 'apppass';
GRANT SELECT, INSERT, UPDATE, DELETE ON appdb.* TO 'appuser'@'%';
FLUSH PRIVILEGES;
