import json
import os
import random
import string
import time
from datetime import datetime
from tempfile import TemporaryDirectory

from django.test import testcases
from rest_framework import status

from desecapi.replication import Repository
from desecapi.tests.base import DesecTestCase


class ReplicationTest(DesecTestCase):
    def test_serials(self):
        url = self.reverse('v1:serial')
        zones = [
            {'name': 'test.example.', 'edited_serial': 12345},
            {'name': 'example.org.', 'edited_serial': 54321},
        ]
        serials = {zone['name']: zone['edited_serial'] for zone in zones}
        pdns_requests = [{
            'method': 'GET',
            'uri': self.get_full_pdns_url(r'/zones', ns='MASTER'),
            'status': 200,
            'body': json.dumps(zones),
        }]

        # Run twice to make sure cache output varies on remote address
        for i in range(2):
            response = self.client.get(path=url, REMOTE_ADDR='123.8.0.2')
            self.assertStatus(response, status.HTTP_401_UNAUTHORIZED)

            with self.assertPdnsRequests(pdns_requests):
                response = self.client.get(path=url, REMOTE_ADDR='10.8.0.2')
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertEqual(response.data, serials)

            # Do not expect pdns request in next iteration (result will be cached)
            pdns_requests = []


class RepositoryTest(testcases.TestCase):

    def assertGit(self, path):
        self.assertTrue(
            os.path.exists(os.path.join(path, '.git')),
            f'Expected a git repository at {path} but did not find .git subdirectory.'
        )

    def assertHead(self, repo, message=None, sha=None):
        actual_sha, actual_message = repo.get_head()
        if actual_sha is None:
            self.fail(f'Expected HEAD to have commit message "{message}" and hash "{sha}", but repository has no '
                      f'commits.')
        if sha:
            self.assertEqual(actual_sha, sha, f'Expected HEAD to have hash "{sha}" but had "{actual_sha}".')
        if message:
            self.assertIn(
                message, actual_message,
                f'Expected "{message}" to appear in the last commit message, but only found "{actual_message}".',
            )

    def assertHasCommit(self, repo: Repository, commit_id):
        self.assertIsNotNone(
            repo.get_commit(commit_id)[0], f'Expected repository to have commit {commit_id}, but it had not.'
        )

    def assertHasCommits(self, repo: Repository, commit_id_list):
        for commit in commit_id_list:
            self.assertHasCommit(repo, commit)

    def assertHasNotCommit(self, repo: Repository, commit_id):
        self.assertIsNone(
            repo.get_commit(commit_id)[0], f'Expected repository to not have commit {commit_id}, but it had.'
        )

    def assertHasNotCommits(self, repo: Repository, commit_id_list):
        for commit in commit_id_list:
            self.assertHasNotCommit(repo, commit)

    def assertNoCommits(self, repo: Repository):
        head = repo.get_head()
        self.assertEqual(head, (None, None), f'Expected that repository has no commits, but HEAD was {head}.')

    @staticmethod
    def _random_string(length):
        return ''.join(random.choices(string.ascii_lowercase, k=length))

    def _random_commit(self, repo: Repository, message=''):
        with open(os.path.join(repo.path, self._random_string(16)), 'w') as f:
            f.write(self._random_string(500))
        repo.commit_all(message)
        return repo.get_head()[0]

    def _random_commits(self, num, repo: Repository, message=''):
        return [self._random_commit(repo, message) for _ in range(num)]

    def test_init(self):
        with TemporaryDirectory() as path:
            repo = Repository(path)
            repo.init()
            self.assertGit(path)

    def test_commit(self):
        with TemporaryDirectory() as path:
            repo = Repository(path)
            repo.init()
            repo.commit_all('commit1')
            self.assertNoCommits(repo)

            with open(os.path.join(path, 'test_commit'), 'w') as f:
                f.write('foo')

            repo.commit_all('commit2')
            self.assertHead(repo, message='commit2')

    def test_remove_history(self):
        with TemporaryDirectory() as path:
            repo = Repository(path)
            repo.init()

            remove = self._random_commits(5, repo, 'to be removed')  # we're going to remove these 'old' commits
            keep = self._random_commits(1, repo, 'anchor to be kept')  # as sync anchor, the last 'old' commit is kept
            cutoff = datetime.now()
            time.sleep(1)
            keep += self._random_commits(5, repo, 'to be kept')  # we're going to keep these 'new' commits

            self.assertHasCommits(repo, remove + keep)

            repo.remove_history(before=cutoff)

            self.assertHasCommits(repo, keep)
            self.assertHasNotCommits(repo, remove)
