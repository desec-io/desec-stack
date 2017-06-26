-- Narrow down root logins
INSTALL PLUGIN unix_socket SONAME 'auth_socket';
DELETE FROM mysql.user WHERE User = 'root' AND Host != 'localhost';
UPDATE mysql.user SET plugin = 'unix_socket' WHERE User = 'root' AND Host = 'localhost';
FLUSH PRIVILEGES;
