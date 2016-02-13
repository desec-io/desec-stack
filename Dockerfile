FROM mysql

COPY *.sql /docker-entrypoint-initdb.d/

