import argparse
import MySQLdb
import os
import re
import secrets
import string
import sys
from collections import OrderedDict

from pki_utils import PKI

host = 'dbmaster'
user = 'replication-manager'


def validate_name(value):
    pattern = re.compile("^([a-z0-9._-]+[a-z0-9]+)$")
    if not pattern.match(value):
        raise ValueError(f'Name does not match pattern {pattern}')

    return value

def add_slave(cursor, **kwargs):
    name = validate_name(kwargs['name'])

    alphabet = string.ascii_letters + string.digits
    passwd = ''.join(secrets.choice(alphabet) for i in range(32))

    # Create key and certificate
    with open('certs/ca.pem', 'r') as ca_crt_file, open('certs/ca-key.pem', 'r') as ca_key_file:
        ca_crt_pem = ca_crt_file.read().encode('ascii')
        ca_key_pem = ca_key_file.read().encode('ascii')

    pki = PKI(ca_crt_pem=ca_crt_pem, ca_key_pem=ca_key_pem)
    pki.initialize_key()
    pki.create_certificate(common_name=name, days=365*10)

    subject = ''
    for label, attributes in pki.subject_attributes.items():
        assert len(attributes) == 1
        value = attributes[0]
        subject += f'/{label}={value}'

    # Configure slave in database
    username = name.replace('.', '_')  # allows using username as binlog on the slave
    print(f'Creating slave user {username} with subject {subject} ...')
    cursor.execute("CREATE USER %s@'%%' IDENTIFIED BY %s", (username, passwd,))
    cursor.execute("GRANT RELOAD, REPLICATION CLIENT, REPLICATION SLAVE ON *.* TO %s@'%%' REQUIRE SUBJECT %s", (username, subject,))
    cursor.execute("GRANT SELECT ON pdns.* TO %s@'%%' REQUIRE SUBJECT %s", (username, subject,))
    cursor.execute("FLUSH PRIVILEGES")
    print(f'Password is {passwd}')

    # Write key and certificate
    umask = os.umask(0o077)
    key_filename = f'certs/{name}-key.pem'
    crt_filename = f'certs/{name}-crt.pem'
    with open(key_filename, 'wb') as key_file, open(crt_filename, 'wb') as crt_file:
        key_file.write(pki.key_pem)
        crt_file.write(pki.crt_pem)
    os.umask(umask)

    print(key_filename, '(key)')
    print(crt_filename, '(certificate)')


def list_slaves(cursor):
    cursor.execute("SELECT User, x509_subject FROM mysql.user WHERE x509_subject != ''")
    for row in cursor.fetchall():
        print(row[0], row[1].decode('utf-8'))


def remove_slave(cursor, **kwargs):
    slavename = validate_name(kwargs['name'])

    cursor.execute("DROP USER %s@'%%'", (slavename,))
    cursor.execute("FLUSH PRIVILEGES")


def main():
    parser = argparse.ArgumentParser(description='List, add, and remove pdns database replication slaves.')
    subparsers = parser.add_subparsers(dest='action', required=True)

    actions = {}

    # add
    description = 'Add a slave and generate TLS key/certificate. The slave replication password is read from stdin (first line).'
    subparser = subparsers.add_parser('add', help='Add a slave and generate TLS key/certificate', description=description)
    subparser.add_argument('--name', type=str, help='Slave identifier (usually hostname)', required=True)
    actions['add'] = add_slave

    # list
    subparser = subparsers.add_parser('list', help='List slaves', description='List slaves.')
    actions['list'] = list_slaves

    # remove
    subparser = subparsers.add_parser('remove', help='Remove a slave', description='Remove a slave.')
    subparser.add_argument('--name', type=str, help='Slave identifier (usually hostname)', required=True)
    actions['remove'] = remove_slave

    # Validate and extract arguments (errors out if insufficient arguments are given)
    args = parser.parse_args()
    kwargs = vars(args).copy()

    # Initialize database
    db = MySQLdb.connect(host=host, user=user, passwd=os.environ['DESECSTACK_DBMASTER_PASSWORD_replication_manager'])

    # Action!
    action = kwargs.pop('action')
    action_func = actions[action]
    try:
        action_func(db.cursor(), **kwargs)
    except Exception as e:
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    main()

