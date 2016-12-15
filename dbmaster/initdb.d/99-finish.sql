-- Narrow down root logins
INSTALL PLUGIN unix_socket SONAME 'auth_socket';
UPDATE mysql.user SET Host = 'localhost', plugin = 'unix_socket' WHERE User = 'root';
FLUSH PRIVILEGES;
