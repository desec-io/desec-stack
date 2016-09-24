-- deSEC user and domain database
CREATE DATABASE desec;
CREATE USER desec IDENTIFIED BY 'test123';
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES, INDEX, CREATE, ALTER, DROP ON desec.* TO desec;

-- nslord database, including devadmin access
CREATE DATABASE pdnslord;
CREATE USER pdnslord IDENTIFIED BY '123test';
GRANT SELECT, INSERT, UPDATE, DELETE ON pdnslord.* TO pdnslord;

CREATE USER poweradmin IDENTIFIED BY '123passphrase';
GRANT SELECT, INSERT, UPDATE, DELETE ON pdnslord.* TO poweradmin;

-- nsmaster database
CREATE DATABASE pdnsmaster;
CREATE USER pdnsmaster IDENTIFIED BY '456test';
GRANT SELECT, INSERT, UPDATE, DELETE ON pdnsmaster.* TO pdnsmaster;

-- replication
CREATE USER ns1@'%' IDENTIFIED BY "test234";
GRANT REPLICATION SLAVE ON *.* TO ns1@'%' REQUIRE SUBJECT '/CN=ns1.desec.io';

CREATE USER ns2@'%' IDENTIFIED BY "test345";
GRANT REPLICATION SLAVE ON *.* TO ns2@'%' REQUIRE SUBJECT '/CN=ns2.desec.io';
