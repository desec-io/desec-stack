import os
import subprocess
from datetime import datetime, timedelta
from typing import List

import dns.query
import dns.zone
from celery import shared_task
from django.utils import timezone

from desecapi import models


class ReplicationException(Exception):

    def __init__(self, message, **kwargs):
        super().__init__(message)
        for k, v in kwargs.items():
            self.__setattr__(k, v)


class GitRepositoryException(ReplicationException):
    pass


class UnsupportedZoneNameException(ReplicationException):
    pass


class Repository:
    # TODO replication performance could potentially(*) be further improved by allowing to run multiple AXFR in
    #  parallel, and then use a file lock to synchronize git file system actions
    #  (*) but only if the signing server can sign multiple requests in parallel

    _config = {
        'user.email': 'api@desec.internal',
        'user.name': 'deSEC API',
    }

    def __init__(self, path):
        self.path = path

    def _git(self, *args):
        cmd = ['/usr/bin/git'] + list(args)
        print('>>> ' + str(cmd))

        with subprocess.Popen(
                cmd,
                bufsize=0,
                cwd=self.path,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                env={'HOME': '/'},  # Celery does not adjust $HOME when dropping privileges
        ) as p:
            try:
                stdout, stderr = p.communicate(input=None, timeout=60)
                rcode = p.returncode
                stderr, stdout = stderr.decode(), stdout.decode()
            except subprocess.TimeoutExpired:
                p.kill()
                raise
            except UnicodeDecodeError:
                GitRepositoryException('git stdout or stderr was not valid unicode!',
                                       cmd=cmd, rcode=rcode, stderr=stderr, stdout=stdout)

        print('\n'.join('<<< ' + s for s in stdout.split('\n')))
        return cmd, rcode, stdout, stderr

    def _git_do(self, *args):
        cmd, rcode, stdout, stderr = self._git(*args)

        if rcode != 0:
            raise GitRepositoryException(f'{cmd} returned nonzero error code',
                                         cmd=cmd, rcode=rcode, stdout=stdout, stderr=stderr)

        if stderr.strip():
            raise GitRepositoryException(f'{cmd} returned non-empty error output',
                                         cmd=cmd, rcode=rcode, stdout=stdout, stderr=stderr)

        return stdout

    def _git_check(self, *args):
        _, rcode, _, _ = self._git(*args)
        return rcode

    def commit_all(self, msg=None):
        self._git_do('add', '.')
        if self._git_check('diff', '--exit-code', '--numstat', '--staged'):
            self._git_do('commit', '-m', msg or 'update')

    def init(self):
        self._git_do('init', '-b', 'main')
        for k, v in self._config.items():
            self._git_do('config', k, v)

    def get_head(self):
        return self.get_commit('HEAD')

    def get_commit(self, rev):
        try:
            commit_hash, commit_msg = self._git_do('show', rev, '--format=%H%n%s', '-s').split('\n', 1)
            return commit_hash, commit_msg[:-1]
        except GitRepositoryException:
            return None, None

    def remove_history(self, before: datetime):
        rev = self._git_do('log', f'--before={before.isoformat()}Z', '-1', '--format=%H')
        with open(os.path.join(self.path, '.git', 'shallow'), 'w') as f:
            f.writelines([rev])
        self._git_do('reflog', 'expire', '--expire=now', '--all')
        self._git_do('gc', '--prune=now')  # prune only
        self._git_do('gc')  # remaining garbage collection (e.g. compressing file revisions)


class ZoneRepository(Repository):
    AXFR_SOURCE = '172.16.1.11'

    def __init__(self, path):
        super().__init__(path)
        self._config['gc.auto'] = '0'
        if not os.path.exists(os.path.join(self.path, '.git')):
            self.init()
            self.commit_all(msg='Inception or Recovery')
            update_all.delay()

    def refresh(self, name):
        if '/' in name or '\x00' in name:
            raise UnsupportedZoneNameException

        # obtain AXFR
        timeout = 60  # if AXFR take longer, the timeout must be increased (see also settings.py)
        try:
            xfr = list(dns.query.xfr(self.AXFR_SOURCE, name, timeout=timeout))
        except dns.query.TransferError as e:
            if e.rcode == dns.rcode.Rcode.NOTAUTH:
                self._delete_zone(name)
            else:
                raise
        else:
            self._update_zone(name, xfr)

    def _update_zone(self, name: str, xfr: List[dns.message.QueryMessage]):
        z = dns.zone.from_xfr(xfr, check_origin=False)
        try:
            print(f'New SOA for {name}: '
                  f'{z.get_rrset(name="", rdtype=dns.rdatatype.SOA).to_text()}')
            print(f'         Signature: '
                  f'{z.get_rrset(name="", rdtype=dns.rdatatype.RRSIG, covers=dns.rdatatype.SOA).to_text()}')
        except AttributeError:
            print(f'WARNING {name} has no SOA record?!')

        # TODO sort AXFR? (but take care with SOA)
        #  stable output can be achieved with
        #  output = '\n'.join(sorted('\n'.split(z.to_text())))
        #  but we need to see first if the frontend can handle this messed up zone file

        # write zone file
        filename = os.path.join(self.path, name + '.zone')
        with open(filename + '~', 'w') as f:
            f.write(f'; Generated by deSEC at {datetime.utcnow()}Z\n')  # TODO if sorting, remove this to avoid overhead
            z.to_file(f)
        os.rename(filename + '~', filename)

    def _delete_zone(self, name: str):
        os.remove(os.path.join(self.path, name + '.zone'))


ZONE_REPOSITORY_PATH = '/zones'


@shared_task(queue='replication')
def update(name: str):
    # TODO this task runs through following steps:
    #  (1) retrieve AXFR  (dedyn.io 01/2021: 8.5s)
    #  (2) parse AXFR     (dedyn.io 01/2021: 1.8s)
    #  (3) write AXFR into zone file (dedyn.io 01/2021: 2.3s)
    #  (4) commit into git repository  (dedyn.io 01/2021: 0.5s)
    #  To enhance performance, steps 1-3 can be executed in parallel for multiple zones with multiprocessing.
    #  Step 4, which takes 0.5s even for very large zones, can only be executed by a single worker, as
    #  two parallel git commits will fail
    print(f'updating {name}')
    t = timezone.now()
    zones = ZoneRepository(ZONE_REPOSITORY_PATH)
    zones.refresh(name)
    zones.commit_all(f'Update for {name}')
    models.Domain.objects.filter(name=name).update(replicated=timezone.now(), replication_duration=timezone.now() - t)


@shared_task(queue='replication', priority=9)
def update_all():
    names = models.Domain.objects.all().values_list('name', flat=True)
    print(f'Queuing replication for all {len(names)} zones.')
    for name in names:
        update.s(name).apply_async(priority=1)


@shared_task(queue='replication')
def remove_history():
    before = datetime.now() - timedelta(days=2)
    print(f'Cleaning repo data from before {before}')
    zones = ZoneRepository(ZONE_REPOSITORY_PATH)
    zones.remove_history(before=before)
