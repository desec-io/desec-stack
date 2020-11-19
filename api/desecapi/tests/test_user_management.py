"""
This module tests deSEC's user management.

The tests are separated into two categories, where
(a) the client has an associated user account and
(b) does not have an associated user account.

This involves testing five separate endpoints:
(1) Registration endpoint,
(2) Reset password endpoint,
(3) Change email address endpoint,
(4) delete user endpoint, and
(5) verify endpoint.

Furthermore, domain renewals and unused domain/account scavenging are tested.
"""
from datetime import timedelta
import random
import re
import time
from unittest import mock
from urllib.parse import urlparse

from django.contrib.auth.hashers import is_password_usable
from django.core import mail
from django.core.management import call_command
from django.urls import resolve
from django.utils import timezone
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api import settings
from desecapi.models import Domain, User, Captcha
from desecapi.serializers import AuthenticatedActionSerializer
from desecapi.tests.base import DesecTestCase, DomainOwnerTestCase, PublicSuffixMockMixin


class UserManagementClient(APIClient):

    def register(self, email, password, captcha_id, captcha_solution, **kwargs):
        return self.post(reverse('v1:register'), {
            'email': email,
            'password': password,
            'captcha': {'id': captcha_id, 'solution': captcha_solution},
            **kwargs
        })

    def login_user(self, email, password):
        return self.post(reverse('v1:login'), {
            'email': email,
            'password': password,
        })

    def logout(self, token):
        return self.post(reverse('v1:logout'), HTTP_AUTHORIZATION=f'Token {token}')

    def reset_password(self, email, captcha_id, captcha_solution):
        return self.post(reverse('v1:account-reset-password'), {
            'email': email,
            'captcha': {'id': captcha_id, 'solution': captcha_solution},
        })

    def change_email(self, email, password, **payload):
        payload['email'] = email
        payload['password'] = password
        return self.post(reverse('v1:account-change-email'), payload)

    def change_email_token_auth(self, token, **payload):
        return self.post(reverse('v1:account-change-email'), payload, HTTP_AUTHORIZATION='Token {}'.format(token))

    def delete_account(self, email, password):
        return self.post(reverse('v1:account-delete'), {
            'email': email,
            'password': password,
        })

    def view_account(self, token):
        return self.get(reverse('v1:account'), HTTP_AUTHORIZATION='Token {}'.format(token))

    def verify(self, url, data=None, **kwargs):
        return self.post(url, data, **kwargs)

    def obtain_captcha(self, **kwargs):
        return self.post(reverse('v1:captcha'))


class UserManagementTestCase(DesecTestCase, PublicSuffixMockMixin):

    client_class = UserManagementClient
    password = None
    token = None

    def get_captcha(self):
        response = self.client.obtain_captcha()
        self.assertStatus(response, status.HTTP_201_CREATED)
        id = response.data['id']
        solution = Captcha.objects.get(id=id).content
        return id, solution

    def register_user(self, email=None, password=None, **kwargs):
        email = email if email is not None else self.random_username()
        captcha_id, captcha_solution = self.get_captcha()
        return email.strip(), password, self.client.register(email, password, captcha_id, captcha_solution, **kwargs)

    def login_user(self, email, password):
        return self.client.login_user(email, password)

    def logout(self, token):
        return self.client.logout(token)

    def reset_password(self, email):
        captcha_id, captcha_solution = self.get_captcha()
        return self.client.reset_password(email, captcha_id, captcha_solution)

    def change_email(self, new_email):
        return self.client.change_email(self.email, self.password, new_email=new_email)

    def delete_account(self, email, password):
        return self.client.delete_account(email, password)

    def assertContains(self, response, text, count=None, status_code=200, msg_prefix='', html=False):
        msg_prefix += '\nResponse: %s' % response.data
        super().assertContains(response, text, count, status_code, msg_prefix, html)

    def assertPassword(self, email, password):
        if password is None:
            self.assertFalse(is_password_usable(User.objects.get(email=email).password))
            return

        password = password.strip()
        self.assertTrue(User.objects.get(email=email).check_password(password),
                        'Expected user password to be "%s" (potentially trimmed), but check failed.' % password)

    def assertUserExists(self, email):
        try:
            User.objects.get(email=email)
        except User.DoesNotExist:
            self.fail('Expected user %s to exist, but did not.' % email)

    def assertUserDoesNotExist(self, email):
        # noinspection PyTypeChecker
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(email=email)

    def assertNoEmailSent(self):
        self.assertFalse(mail.outbox, "Expected no email to be sent, but %i were sent. First subject line is '%s'." %
                         (len(mail.outbox), mail.outbox[0].subject if mail.outbox else '<n/a>'))

    def assertEmailSent(self, subject_contains='', body_contains=None, recipient=None, reset=True, pattern=None):
        total = 1
        self.assertEqual(len(mail.outbox), total, "Expected %i message in the outbox, but found %i." %
                         (total, len(mail.outbox)))
        email = mail.outbox[-1]
        self.assertTrue(subject_contains in email.subject,
                        "Expected '%s' in the email subject, but found '%s'" %
                        (subject_contains, email.subject))
        if type(body_contains) != list: body_contains = [] if body_contains is None else [body_contains]
        for elem in body_contains:
            self.assertTrue(elem in email.body, f"Expected '{elem}' in the email body, but found '{email.body}'")
        if recipient is not None:
            if isinstance(recipient, list):
                self.assertListEqual(recipient, email.recipients())
            else:
                self.assertIn(recipient, email.recipients())
        body = email.body
        self.assertIn('user_id = ', body)
        if reset:
            mail.outbox = []
        return body if not pattern else re.search(pattern, body).group(1)

    def assertConfirmationLinkRedirect(self, confirmation_link):
        response = self.client.get(confirmation_link)
        self.assertResponse(response, status.HTTP_406_NOT_ACCEPTABLE)
        response = self.client.get(confirmation_link, HTTP_ACCEPT='text/html')
        self.assertResponse(response, status.HTTP_302_FOUND)
        self.assertNoEmailSent()

    def assertRegistrationEmail(self, recipient, reset=True):
        return self.assertEmailSent(
            subject_contains='deSEC',
            body_contains='Thank you for registering with deSEC!',
            recipient=[recipient],
            reset=reset,
            pattern=r'following link[^:]*:\s+([^\s]*)',
        )

    def assertResetPasswordEmail(self, recipient, reset=True):
        return self.assertEmailSent(
            subject_contains='Password reset',
            body_contains='We received a request to reset the password for your deSEC account.',
            recipient=[recipient],
            reset=reset,
            pattern=r'following link[^:]*:\s+([^\s]*)',
        )

    def assertChangeEmailVerificationEmail(self, recipient, reset=True):
        return self.assertEmailSent(
            subject_contains='Confirmation required: Email address change',
            body_contains='You requested to change the email address associated',
            recipient=[recipient],
            reset=reset,
            pattern=r'following link[^:]*:\s+([^\s]*)',
        )

    def assertChangeEmailNotificationEmail(self, recipient, reset=True):
        return self.assertEmailSent(
            subject_contains='Account email address changed',
            body_contains='We\'re writing to let you know that the email address associated with',
            recipient=[recipient],
            reset=reset,
        )

    def assertDeleteAccountEmail(self, recipient, reset=True):
        return self.assertEmailSent(
            subject_contains='Confirmation required: Delete account',
            body_contains='confirm once more',
            recipient=[recipient],
            reset=reset,
            pattern=r'following link[^:]*:\s+([^\s]*)',
        )

    def assertRegistrationSuccessResponse(self, response):
        return self.assertContains(
            response=response,
            text="Welcome! Please check your mailbox.",
            status_code=status.HTTP_202_ACCEPTED
        )

    def assertLoginSuccessResponse(self, response):
        return self.assertContains(
            response=response,
            text="token",
            status_code=status.HTTP_200_OK
        )

    def assertLogoutSuccessResponse(self, response):
        return self.assertStatus(response, status.HTTP_204_NO_CONTENT)

    def assertRegistrationFailurePasswordRequiredResponse(self, response):
        self.assertContains(
            response=response,
            text="This field may not be blank",
            status_code=status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(response.data['password'][0].code, 'blank')

    def assertRegistrationFailurePasswordMinLengthResponse(self, response):
        self.assertContains(
            response=response,
            text="This password is too short. It must contain at least 8 characters.",
            status_code=status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(response.data['password'][0].code, 'password_too_short')

    def assertRegistrationFailureDomainUnavailableResponse(self, response, domain):
        self.assertContains(
            response=response,
            text='This domain name conflicts with an existing zone, or is disallowed by policy.',
            status_code=status.HTTP_400_BAD_REQUEST,
            msg_prefix=str(response.data)
        )

    def assertRegistrationFailureDomainInvalidResponse(self, response, domain):
        self.assertContains(
            response=response,
            text="Domain names must be labels separated by dots. Labels",
            status_code=status.HTTP_400_BAD_REQUEST,
            msg_prefix=str(response.data)
        )

    def assertRegistrationFailureCaptchaInvalidResponse(self, response):
        self.assertContains(
            response=response,
            text='CAPTCHA could not be validated. Please obtain a new one and try again.',
            status_code=status.HTTP_400_BAD_REQUEST,
            msg_prefix=str(response.data)
        )

    def assertRegistrationVerificationSuccessResponse(self, response):
        return self.assertContains(
            response=response,
            text="Success!",
            status_code=status.HTTP_200_OK
        )

    def assertRegistrationWithDomainVerificationSuccessResponse(self, response, domain=None, email=None):
        self.assertNoEmailSent()  # do not send email in any case
        text = 'Success! Please check the docs for the next steps'
        if domain:
            has_local_suffix = self.has_local_suffix(domain)
            if has_local_suffix:
                text = 'Success! Here is the password'
            self.assertEqual('keys' in response.data['domain'], not has_local_suffix)
            self.assertEqual(response.data['domain']['name'], domain)
        self.assertContains(response=response, text=text, status_code=status.HTTP_200_OK)

    def assertResetPasswordSuccessResponse(self, response):
        return self.assertContains(
            response=response,
            text="Please check your mailbox for further password reset instructions.",
            status_code=status.HTTP_202_ACCEPTED
        )

    def assertResetPasswordVerificationSuccessResponse(self, response):
        return self.assertContains(
            response=response,
            text="Success! Your password has been changed.",
            status_code=status.HTTP_200_OK
        )

    def assertChangeEmailSuccessResponse(self, response):
        return self.assertContains(
            response=response,
            text="Please check your mailbox to confirm email address change.",
            status_code=status.HTTP_202_ACCEPTED
        )

    def assert401InvalidPasswordResponse(self, response):
        return self.assertContains(
            response=response,
            text="Invalid password.",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    def assertChangeEmailFailureAddressTakenResponse(self, response):
        return self.assertContains(
            response=response,
            text="You already have another account with this email address.",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    def assertChangeEmailFailureSameAddressResponse(self, response):
        return self.assertContains(
            response=response,
            text="Email address unchanged.",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    def assertChangeEmailVerificationSuccessResponse(self, response, new_email):
        return self.assertContains(
            response=response,
            text=f'Success! Your email address has been changed to {new_email}.',
            status_code=status.HTTP_200_OK
        )

    def assertChangeEmailVerificationFailureChangePasswordResponse(self, response):
        return self.assertContains(
            response=response,
            text="This field is not allowed for action ",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    def assertDeleteAccountSuccessResponse(self, response):
        return self.assertContains(
            response=response,
            text="Please check your mailbox for further account deletion instructions.",
            status_code=status.HTTP_202_ACCEPTED
        )

    def assertDeleteAccountFailureStillHasDomainsResponse(self, response):
        return self.assertContains(
            response=response,
            text="To delete your user account, first delete all of your domains.",
            status_code=status.HTTP_409_CONFLICT
        )

    def assertDeleteAccountVerificationSuccessResponse(self, response):
        return self.assertContains(
            response=response,
            text="All your data has been deleted. Bye bye, see you soon! <3",
            status_code=status.HTTP_200_OK
        )

    def assertVerificationFailureInvalidCodeResponse(self, response):
        return self.assertContains(
            response=response,
            text="This action cannot be carried out because another operation has been performed",
            status_code=status.HTTP_409_CONFLICT
        )

    def assertVerificationFailureExpiredCodeResponse(self, response):
        return self.assertContains(
            response=response,
            text="This code is invalid, possibly because it expired (validity: ",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    def assertVerificationFailureUnknownUserResponse(self, response):
        return self.assertContains(
            response=response,
            text="This user does not exist.",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    def _test_registration(self, email=None, password=None, **kwargs):
        email, password, response = self.register_user(email, password, **kwargs)
        self.assertRegistrationSuccessResponse(response)
        self.assertUserExists(email)
        self.assertFalse(User.objects.get(email=email).is_active)
        self.assertPassword(email, password)
        confirmation_link = self.assertRegistrationEmail(email)
        self.assertConfirmationLinkRedirect(confirmation_link)
        self.assertRegistrationVerificationSuccessResponse(self.client.verify(confirmation_link))
        self.assertTrue(User.objects.get(email=email).is_active)
        self.assertPassword(email, password)
        return email, password

    def _test_registration_with_domain(self, email=None, password=None, domain=None, expect_failure_response=None,
                                       tampered_domain=None):
        domain = domain or self.random_domain_name()

        email, password, response = self.register_user(email, password, domain=domain)
        if expect_failure_response:
            expect_failure_response(response, domain)
            self.assertUserDoesNotExist(email)
            return
        self.assertRegistrationSuccessResponse(response)
        self.assertUserExists(email)
        self.assertFalse(User.objects.get(email=email).is_active)
        self.assertPassword(email, password)

        confirmation_link = self.assertRegistrationEmail(email)

        if tampered_domain is not None:
            path = urlparse(confirmation_link).path
            code = resolve(path).kwargs.get('code')
            data = AuthenticatedActionSerializer._unpack_code(code, ttl=None)
            data['domain'] = tampered_domain
            tampered_code = AuthenticatedActionSerializer._pack_code(data)
            confirmation_link = confirmation_link.replace(code, tampered_code)
            response = self.client.verify(confirmation_link)
            self.assertVerificationFailureInvalidCodeResponse(response)
            return

        if self.has_local_suffix(domain):
            cm = self.requests_desec_domain_creation_auto_delegation(domain)
        else:
            cm = self.requests_desec_domain_creation(domain)
        with self.assertPdnsRequests(cm):
            response = self.client.verify(confirmation_link)
        self.assertRegistrationWithDomainVerificationSuccessResponse(response, domain, email)
        self.assertTrue(User.objects.get(email=email).is_active)
        self.assertPassword(email, password)
        self.assertTrue(Domain.objects.filter(name=domain, owner__email=email).exists())
        return email, password, domain

    def _test_login(self):
        response = self.login_user(self.email, self.password)
        self.assertLoginSuccessResponse(response)
        self.assertEqual(response.data['max_age'], '7 00:00:00')
        self.assertEqual(response.data['max_unused_period'], '01:00:00')
        return response.data['token']

    def _test_logout(self):
        response = self.logout(self.token)
        self.assertLogoutSuccessResponse(response)
        return response

    def _test_reset_password(self, email, new_password=None, **kwargs):
        new_password = new_password or self.random_password()
        self.assertResetPasswordSuccessResponse(self.reset_password(email))
        confirmation_link = self.assertResetPasswordEmail(email)
        self.assertConfirmationLinkRedirect(confirmation_link)
        self.assertResetPasswordVerificationSuccessResponse(
            self.client.verify(confirmation_link, data={'new_password': new_password}, **kwargs))
        self.assertPassword(email, new_password)
        return new_password

    def _test_change_email(self):
        old_email = self.email
        new_email = ' {} '.format(self.random_username())  # test trimming
        self.assertChangeEmailSuccessResponse(self.change_email(new_email))
        new_email = new_email.strip()
        confirmation_link = self.assertChangeEmailVerificationEmail(new_email)
        self.assertConfirmationLinkRedirect(confirmation_link)
        self.assertChangeEmailVerificationSuccessResponse(self.client.verify(confirmation_link), new_email)
        self.assertChangeEmailNotificationEmail(old_email)
        self.assertUserExists(new_email)
        self.assertUserDoesNotExist(old_email)
        self.email = new_email
        return self.email

    def _test_delete_account(self, email, password):
        self.assertDeleteAccountSuccessResponse(self.delete_account(email, password))
        confirmation_link = self.assertDeleteAccountEmail(email)
        self.assertConfirmationLinkRedirect(confirmation_link)
        self.assertDeleteAccountVerificationSuccessResponse(self.client.verify(confirmation_link))
        self.assertUserDoesNotExist(email)


class UserLifeCycleTestCase(UserManagementTestCase):

    def test_life_cycle(self):
        self.email, self.password = self._test_registration(self.random_username(), self.random_password())
        self.password = self._test_reset_password(self.email)
        mail.outbox = []
        self.token = self._test_login()
        email = self._test_change_email()
        self._test_logout()
        self._test_delete_account(email, self.password)


class NoUserAccountTestCase(UserLifeCycleTestCase):

    def test_home(self):
        self.assertResponse(self.client.get(reverse('v1:root')), status.HTTP_200_OK)

    def test_registration(self):
        self._test_registration(password=self.random_password())

    def test_registration_trim_email(self):
        user_email = ' {} '.format(self.random_username())
        email, _ = self._test_registration(user_email)
        self.assertEqual(email, user_email.strip())

    def test_registration_with_domain(self):
        PublicSuffixMockMixin.setUpMockPatch(self)
        with self.get_psl_context_manager('.'):
            _, _, domain = self._test_registration_with_domain()
            self._test_registration_with_domain(domain=domain, expect_failure_response=self.assertRegistrationFailureDomainUnavailableResponse)
            self._test_registration_with_domain(domain='töö--', expect_failure_response=self.assertRegistrationFailureDomainInvalidResponse)

        with self.get_psl_context_manager('co.uk'):
            self._test_registration_with_domain(domain='co.uk', expect_failure_response=self.assertRegistrationFailureDomainUnavailableResponse)
        local_public_suffix = random.sample(self.AUTO_DELEGATION_DOMAINS, 1)[0]
        with self.get_psl_context_manager(local_public_suffix):
            self._test_registration_with_domain(domain=self.random_domain_name(suffix=local_public_suffix))

    def test_registration_without_domain_and_password(self):
        email, password = self._test_registration(self.random_username(), None)
        self.assertResetPasswordEmail(email)

    def test_registration_with_tampered_domain(self):
        PublicSuffixMockMixin.setUpMockPatch(self)
        with self.get_psl_context_manager('.'):
            self._test_registration_with_domain(tampered_domain='evil.com')

    def test_registration_known_account(self):
        email, _ = self._test_registration(self.random_username(), self.random_password())
        self.assertRegistrationSuccessResponse(self.register_user(email, self.random_password())[2])
        self.assertNoEmailSent()

    def test_registration_password_required(self):
        email = self.random_username()
        self.assertRegistrationFailurePasswordRequiredResponse(
            response=self.register_user(email=email, password='')[2]
        )
        self.assertNoEmailSent()
        self.assertUserDoesNotExist(email)

    def test_registration_password_min_length(self):
        email = self.random_username()
        self.assertRegistrationFailurePasswordMinLengthResponse(
            response=self.register_user(email=email, password='asdf123')[2]
        )
        self.assertNoEmailSent()
        self.assertUserDoesNotExist(email)

    def test_no_login_with_unusable_password(self):
        email, password = self._test_registration(password=None)
        response = self.client.login_user(email, password)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['password'][0], 'This field may not be null.')

    def test_registration_spam_protection(self):
        email = self.random_username()
        self.assertRegistrationSuccessResponse(
            response=self.register_user(email=email)[2]
        )
        self.assertRegistrationEmail(email)
        for _ in range(5):
            self.assertRegistrationSuccessResponse(
                response=self.register_user(email=email)[2]
            )
            self.assertNoEmailSent()

    def test_registration_wrong_captcha(self):
        email = self.random_username()
        password = self.random_password()
        captcha_id, _ = self.get_captcha()
        self.assertRegistrationFailureCaptchaInvalidResponse(
            self.client.register(email, password, captcha_id, 'this is most definitely not a correct CAPTCHA solution')
        )


class OtherUserAccountTestCase(UserManagementTestCase):

    def setUp(self):
        super().setUp()
        self.other_email, self.other_password = self._test_registration(password=self.random_password())

    def test_reset_password_unknown_user(self):
        self.assertResetPasswordSuccessResponse(
            response=self.reset_password(self.random_username())
        )
        self.assertNoEmailSent()


class HasUserAccountTestCase(UserManagementTestCase):

    def __init__(self, methodName: str = ...) -> None:
        super().__init__(methodName)
        self.email = None
        self.password = None

    def setUp(self):
        super().setUp()
        self.email, self.password = self._test_registration(password=self.random_password())
        self.token = self._test_login()

    def _start_reset_password(self):
        self.assertResetPasswordSuccessResponse(
            response=self.reset_password(self.email)
        )
        return self.assertResetPasswordEmail(self.email)

    def _start_change_email(self):
        new_email = self.random_username()
        self.assertChangeEmailSuccessResponse(
            response=self.change_email(new_email)
        )
        return self.assertChangeEmailVerificationEmail(new_email), new_email

    def _start_delete_account(self):
        self.assertDeleteAccountSuccessResponse(self.delete_account(self.email, self.password))
        return self.assertDeleteAccountEmail(self.email)

    def _finish_reset_password(self, confirmation_link, expect_success=True):
        new_password = self.random_password()
        response = self.client.verify(confirmation_link, data={'new_password': new_password})
        if expect_success:
            self.assertResetPasswordVerificationSuccessResponse(response=response)
        else:
            self.assertVerificationFailureInvalidCodeResponse(response)
        return new_password

    def _finish_change_email(self, confirmation_link, new_email='', expect_success=True):
        response = self.client.verify(confirmation_link)
        if expect_success:
            self.assertChangeEmailVerificationSuccessResponse(response, new_email)
            self.assertChangeEmailNotificationEmail(self.email)
        else:
            self.assertVerificationFailureInvalidCodeResponse(response)

    def _finish_delete_account(self, confirmation_link):
        self.assertDeleteAccountVerificationSuccessResponse(self.client.verify(confirmation_link))
        self.assertUserDoesNotExist(self.email)

    def test_view_account(self):
        response = self.client.view_account(self.token)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('created' in response.data)
        self.assertEqual(response.data['email'], self.email)
        self.assertEqual(response.data['id'], str(User.objects.get(email=self.email).pk))
        self.assertEqual(response.data['limit_domains'], settings.LIMIT_USER_DOMAIN_COUNT_DEFAULT)

    def test_view_account_read_only(self):
        # Should this test ever be removed (to allow writeable fields), make sure to
        # add new tests for each read-only field individually (such as limit_domains)!
        for method in [self.client.patch, self.client.put, self.client.post, self.client.delete]:
            response = method(
                reverse('v1:account'),
                {'limit_domains': 99},
                HTTP_AUTHORIZATION='Token {}'.format(self.token)
            )
            self.assertResponse(response, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_reset_password(self):
        self._test_reset_password(self.email)

    def test_reset_password_inactive_user(self):
        user = User.objects.get(email=self.email)
        user.is_active = False
        user.save()
        self.assertResetPasswordSuccessResponse(self.reset_password(self.email))
        self.assertNoEmailSent()

    def test_reset_password_multiple_times(self):
        for _ in range(3):
            self._test_reset_password(self.email)
            mail.outbox = []

    def test_reset_password_during_change_email_interleaved(self):
        reset_password_verification_code = self._start_reset_password()
        change_email_verification_code, new_email = self._start_change_email()
        new_password = self._finish_reset_password(reset_password_verification_code)
        self._finish_change_email(change_email_verification_code, expect_success=False)

        self.assertUserExists(self.email)
        self.assertUserDoesNotExist(new_email)
        self.assertPassword(self.email, new_password)

    def test_reset_password_during_change_email_nested(self):
        change_email_verification_code, new_email = self._start_change_email()
        reset_password_verification_code = self._start_reset_password()
        new_password = self._finish_reset_password(reset_password_verification_code)
        self._finish_change_email(change_email_verification_code, expect_success=False)

        self.assertUserExists(self.email)
        self.assertUserDoesNotExist(new_email)
        self.assertPassword(self.email, new_password)

    def test_reset_password_without_new_password(self):
        confirmation_link = self._start_reset_password()
        response = self.client.verify(confirmation_link)
        self.assertResponse(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['new_password'][0], 'This field is required.')
        self.assertNoEmailSent()

    def test_reset_password_validation_unknown_user(self):
        confirmation_link = self._start_reset_password()
        self._test_delete_account(self.email, self.password)
        self.assertVerificationFailureUnknownUserResponse(
            response=self.client.verify(confirmation_link, data={'new_password': 'foobar'})
        )
        self.assertNoEmailSent()

    def test_change_email(self):
        self._test_change_email()

    def test_change_email_requires_password(self):
        # Make sure that the account's email address cannot be changed with a token (password required)
        new_email = self.random_username()
        response = self.client.change_email_token_auth(self.token, new_email=new_email)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['email'][0], 'This field is required.')
        self.assertEqual(response.data['password'][0], 'This field is required.')
        self.assertNoEmailSent()

    def test_change_email_multiple_times(self):
        for _ in range(3):
            self._test_change_email()

    def test_change_email_user_exists(self):
        known_email, _ = self._test_registration()
        # We send a verification link to the new email and check account existence only later, upon verification
        self.assertChangeEmailSuccessResponse(
            response=self.change_email(known_email)
        )

    def test_change_email_verification_user_exists(self):
        new_email = self.random_username()
        self.assertChangeEmailSuccessResponse(self.change_email(new_email))
        confirmation_link = self.assertChangeEmailVerificationEmail(new_email)
        new_email, new_password = self._test_registration(new_email)
        self.assertChangeEmailFailureAddressTakenResponse(
            response=self.client.verify(confirmation_link)
        )
        self.assertUserExists(self.email)
        self.assertPassword(self.email, self.password)
        self.assertUserExists(new_email)
        self.assertPassword(new_email, new_password)

    def test_change_email_same_email(self):
        self.assertChangeEmailFailureSameAddressResponse(
            response=self.change_email(self.email)
        )
        self.assertUserExists(self.email)

    def test_change_email_during_reset_password_interleaved(self):
        change_email_verification_code, new_email = self._start_change_email()
        reset_password_verification_code = self._start_reset_password()
        self._finish_change_email(change_email_verification_code, new_email)
        self._finish_reset_password(reset_password_verification_code, expect_success=False)

        self.assertUserExists(new_email)
        self.assertUserDoesNotExist(self.email)
        self.assertPassword(new_email, self.password)

    def test_change_email_during_reset_password_nested(self):
        reset_password_verification_code = self._start_reset_password()
        change_email_verification_code, new_email = self._start_change_email()
        self._finish_change_email(change_email_verification_code, new_email)
        self._finish_reset_password(reset_password_verification_code, expect_success=False)

        self.assertUserExists(new_email)
        self.assertUserDoesNotExist(self.email)
        self.assertPassword(new_email, self.password)

    def test_change_email_nested(self):
        verification_code_1, new_email_1 = self._start_change_email()
        verification_code_2, new_email_2 = self._start_change_email()

        self._finish_change_email(verification_code_2, new_email_2)
        self.assertUserDoesNotExist(self.email)
        self.assertUserDoesNotExist(new_email_1)
        self.assertUserExists(new_email_2)

        self._finish_change_email(verification_code_1, expect_success=False)
        self.assertUserDoesNotExist(self.email)
        self.assertUserDoesNotExist(new_email_1)
        self.assertUserExists(new_email_2)

    def test_change_email_interleaved(self):
        verification_code_1, new_email_1 = self._start_change_email()
        verification_code_2, new_email_2 = self._start_change_email()

        self._finish_change_email(verification_code_1, new_email_1)
        self.assertUserDoesNotExist(self.email)
        self.assertUserExists(new_email_1)
        self.assertUserDoesNotExist(new_email_2)

        self._finish_change_email(verification_code_2, expect_success=False)
        self.assertUserDoesNotExist(self.email)
        self.assertUserExists(new_email_1)
        self.assertUserDoesNotExist(new_email_2)

    def test_change_email_validation_unknown_user(self):
        confirmation_link, new_email = self._start_change_email()
        self._test_delete_account(self.email, self.password)
        self.assertVerificationFailureUnknownUserResponse(
            response=self.client.verify(confirmation_link)
        )
        self.assertNoEmailSent()

    def test_delete_account_validation_unknown_user(self):
        confirmation_link = self._start_delete_account()
        self._test_delete_account(self.email, self.password)
        self.assertVerificationFailureUnknownUserResponse(
            response=self.client.verify(confirmation_link)
        )
        self.assertNoEmailSent()

    def test_delete_account_domains_present(self):
        user = User.objects.get(email=self.email)
        domain = self.create_domain(owner=user)
        self.assertDeleteAccountFailureStillHasDomainsResponse(self.delete_account(self.email, self.password))
        domain.delete()
        confirmation_link = self._start_delete_account()
        domain = self.create_domain(owner=user)
        self.assertDeleteAccountFailureStillHasDomainsResponse(response=self.client.verify(confirmation_link))
        domain.delete()
        self._finish_delete_account(confirmation_link)

    def test_reset_password_password_strip(self):
        password = ' %s ' % self.random_password()
        self._test_reset_password(self.email, password)
        self.assertPassword(self.email, password.strip())
        self.assertPassword(self.email, password)

    def test_reset_password_no_code_override(self):
        password = self.random_password()
        self._test_reset_password(self.email, password, code='foobar')
        self.assertPassword(self.email, password)

    def test_action_code_expired(self):
        self.assertResetPasswordSuccessResponse(self.reset_password(self.email))
        confirmation_link = self.assertResetPasswordEmail(self.email)

        with mock.patch('time.time',
                        return_value=time.time() + settings.VALIDITY_PERIOD_VERIFICATION_SIGNATURE.total_seconds() + 1):
            response = self.client.verify(confirmation_link, data={'new_password': self.random_password()})
        self.assertVerificationFailureExpiredCodeResponse(response)

    def test_action_code_confusion(self):
        # Obtain change password code
        self.assertResetPasswordSuccessResponse(self.reset_password(self.email))
        reset_password_link = self.assertResetPasswordEmail(self.email)
        path = urlparse(reset_password_link).path
        reset_password_code = resolve(path).kwargs.get('code')

        # Obtain deletion code
        self.assertDeleteAccountSuccessResponse(self.delete_account(self.email, self.password))
        delete_link = self.assertDeleteAccountEmail(self.email)
        path = urlparse(delete_link).path
        deletion_code = resolve(path).kwargs.get('code')

        # Swap codes
        self.assertNotEqual(reset_password_code, deletion_code)
        delete_link = delete_link.replace(deletion_code, reset_password_code)
        reset_password_link = reset_password_link.replace(reset_password_code, deletion_code)

        # Make sure links don't work
        self.assertVerificationFailureInvalidCodeResponse(self.client.verify(delete_link))
        self.assertVerificationFailureInvalidCodeResponse(self.client.verify(reset_password_link,
                                                                             data={'new_password': 'dummy'}))


class RenewTestCase(UserManagementTestCase, DomainOwnerTestCase):
    DYN = False

    def setUp(self):
        super().setUp()
        self.email, self.password = self._test_registration(password=self.random_password())

    def assertRenewDomainEmail(self, recipient, body_contains, pattern, reset=True):
        return self.assertEmailSent(
            subject_contains='Upcoming domain deletion',
            body_contains=body_contains,
            recipient=[recipient],
            reset=reset,
            pattern=pattern,
        )

    def assertRenewDomainVerificationSuccessResponse(self, response):
        return self.assertContains(
            response=response,
            text='We recorded that your domain ',
            status_code=status.HTTP_200_OK
        )

    def test_renew_domain_immortal(self):
        domain = self.my_domains[0]
        domain.renewal_state = Domain.RenewalState.IMMORTAL
        domain.save()
        for days in [182, 184]:
            domain.published = timezone.now() - timedelta(days=days)
            domain.renewal_changed = domain.published
            domain.save()

            call_command('scavenge-unused')
            self.assertEqual(len(mail.outbox), 0)
            self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_state, Domain.RenewalState.IMMORTAL)
            self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_changed, domain.renewal_changed)
            self.assertEqual(Domain.objects.get(pk=domain.pk).published, domain.published)

    def test_renew_domain_recently_published(self):
        domain = self.my_domains[0]
        for days in [5, 182, 184]:
            domain.published = timezone.now() - timedelta(days=1)
            domain.renewal_changed = timezone.now() - timedelta(days=days)
            for renewal_state in [Domain.RenewalState.FRESH, Domain.RenewalState.NOTIFIED, Domain.RenewalState.WARNED]:
                domain.renewal_state = renewal_state
                domain.save()

                self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_state, domain.renewal_state)
                call_command('scavenge-unused')
                self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_state, Domain.RenewalState.FRESH)
                self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_changed, domain.published)
                self.assertEqual(Domain.objects.get(pk=domain.pk).published, domain.published)
                self.assertEqual(len(mail.outbox), 0)

    def test_renew_domain_fresh_182_days(self):
        domain = self.my_domains[0]
        domain.published = timezone.now() - timedelta(days=182)
        domain.renewal_changed = domain.published
        domain.renewal_state = Domain.RenewalState.FRESH
        domain.save()

        self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_state, Domain.RenewalState.FRESH)
        call_command('scavenge-unused')
        self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_state, Domain.RenewalState.FRESH)
        self.assertEqual(len(mail.outbox), 0)

    def test_renew_domain_fresh_183_days(self):
        domain = self.my_domains[0]
        domain.published = timezone.now() - timedelta(days=183)
        domain.renewal_changed = domain.published
        domain.renewal_state = Domain.RenewalState.FRESH
        domain.save()

        self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_state, Domain.RenewalState.FRESH)
        call_command('scavenge-unused')
        self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_state, Domain.RenewalState.NOTIFIED)

        deletion_date = timezone.localdate() + timedelta(days=28)
        body_contains = [domain.name, deletion_date.strftime('%B %-d, %Y')]
        pattern = r'following link[^:]*:\s+\* ' + domain.name.replace('.', r'\.') + r'\s+([^\s]*)'
        confirmation_link = self.assertRenewDomainEmail(domain.owner.email, body_contains, pattern)
        self.assertConfirmationLinkRedirect(confirmation_link)

        # Use link after 14 days
        with mock.patch('time.time', return_value=time.time() + 86400*14):
            self.assertRenewDomainVerificationSuccessResponse(self.client.verify(confirmation_link))
            self.assertLess(timezone.now() - Domain.objects.get(pk=domain.pk).renewal_changed, timedelta(seconds=1))
        self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_state, Domain.RenewalState.FRESH)

        # Check that other domains aren't affected
        self.assertGreater(len(self.my_domains), 1)
        for domain in self.my_domains[1:]:
            self.assertLess(Domain.objects.get(pk=domain.pk).renewal_state, Domain.RenewalState.NOTIFIED)
            self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_changed, domain.renewal_changed)

    def test_renew_domain_notified_21_days(self):
        domain = self.my_domains[0]
        domain.published = timezone.now() - timedelta(days=183+21)
        domain.renewal_state = Domain.RenewalState.NOTIFIED
        domain.renewal_changed = timezone.now() - timedelta(days=21)
        domain.save()

        call_command('scavenge-unused')
        self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_state, Domain.RenewalState.WARNED)

        deletion_date = timezone.localdate() + timedelta(days=7)
        body_contains = [domain.name, deletion_date.strftime('%B %-d, %Y')]
        pattern = r'following link[^:]*:\s+\* ' + domain.name.replace('.', r'\.') + r'\s+([^\s]*)'
        confirmation_link = self.assertRenewDomainEmail(domain.owner.email, body_contains, pattern)
        self.assertConfirmationLinkRedirect(confirmation_link)

        # Use link after 6 days
        with mock.patch('time.time', return_value=time.time() + 86400*6):
            self.assertRenewDomainVerificationSuccessResponse(self.client.verify(confirmation_link))
            self.assertLess(timezone.now() - Domain.objects.get(pk=domain.pk).renewal_changed, timedelta(seconds=1))
        self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_state, Domain.RenewalState.FRESH)

        # Check that other domains aren't affected
        self.assertGreater(len(self.my_domains), 1)
        for domain in self.my_domains[1:]:
            self.assertLess(Domain.objects.get(pk=domain.pk).renewal_state, Domain.RenewalState.NOTIFIED)
            self.assertEqual(Domain.objects.get(pk=domain.pk).renewal_changed, domain.renewal_changed)

    def test_renew_domain_warned_7_days(self):
        domains = self.my_domains[:]  # copy list so we can modify it later without side effects
        self.assertGreaterEqual(len(domains), 2)
        while domains:
            domain = domains.pop()
            domain.published = timezone.now() - timedelta(days=183+28)
            domain.renewal_state = Domain.RenewalState.WARNED
            domain.renewal_changed = timezone.now() - timedelta(days=7)
            domain.save()

            with self.assertPdnsRequests(self.requests_desec_domain_deletion(domain=domain)):
                 call_command('scavenge-unused')
            self.assertFalse(Domain.objects.filter(pk=domain.pk).exists())

            # User gets deleted when last domain is purged
            self.assertEqual(User.objects.filter(pk=self.owner.pk).exists(), bool(domains))

            # Check that other domains are not affected
            for domain in domains:
                self.assertLess(Domain.objects.get(pk=domain.pk).renewal_state, Domain.RenewalState.NOTIFIED)

class RenewDynTestCase(RenewTestCase):
    DYN = True
