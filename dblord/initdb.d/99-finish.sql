-- Narrow down root logins
DROP USER 'root'@'%';
INSTALL PLUGIN unix_socket SONAME 'auth_socket';
ALTER USER 'root'@'localhost' IDENTIFIED VIA unix_socket;
