import time
from socket import gethostbyname

from django.conf import settings
from django.core.mail import get_connection, mail_admins
from django.core.management import BaseCommand
from django.utils import timezone
import dns.message, dns.rdatatype, dns.query

from desecapi import models
from desecapi.pdns_change_tracker import NSLordChangeTracker


class Command(BaseCommand):
    @staticmethod
    def delete_expired_captchas():
        models.Captcha.objects.filter(
            created__lt=timezone.now() - settings.CAPTCHA_VALIDITY_PERIOD
        ).delete()

    @staticmethod
    def delete_never_activated_users():
        # delete inactive users whose activation link expired and who never logged in
        # (this will not delete users who have used their account and were later disabled)
        models.User.objects.filter(
            is_active__isnull=True,
            last_login__isnull=True,
            created__lt=timezone.now()
            - settings.VALIDITY_PERIOD_VERIFICATION_SIGNATURE,
        ).delete()

    @staticmethod
    def update_healthcheck_timestamp():
        name = "internal-timestamp.desec.test"
        try:
            domain = models.Domain.objects.get(name=name)
        except models.Domain.DoesNotExist:
            # Fail silently. If external alerting is configured, it will catch the problem; otherwise, we don't need it.
            print(f"{name} zone is not configured; skipping TXT record update")
            return

        content = f'"{int(time.time())}"'
        with NSLordChangeTracker():
            rrset, _ = domain.rrset_set.update_or_create(
                subname="", type="TXT", defaults={"ttl": settings.MINIMUM_TTL_DEFAULT}
            )
            rrset.save_records([content])
        print(f"TXT {name} updated to {content}")

    @staticmethod
    def alerting_healthcheck():
        name = "external-timestamp.desec.test"
        try:
            models.Domain.objects.get(name=name)
        except models.Domain.DoesNotExist:
            print(f"{name} zone is not configured; skipping alerting health check")
            return

        timestamps = []
        qname = dns.name.from_text(name)
        query = dns.message.make_query(qname, dns.rdatatype.TXT)
        query.use_edns(
            payload=4096, options=[dns.edns.GenericOption(dns.edns.NSID, "")]
        )
        server = gethostbyname("ns1.desec.io")
        response = None
        response_opts = None
        try:
            response = dns.query.tcp(query, server, timeout=5)
            for content in response.find_rrset(
                dns.message.ANSWER, qname, dns.rdataclass.IN, dns.rdatatype.TXT
            ):
                timestamps.append(str(content)[1:-1])
            response_opts = [opt.__dict__ for opt in response.options]
        except Exception:
            pass

        now = time.time()
        if any(now - 600 <= int(timestamp) <= now for timestamp in timestamps):
            print(f"TXT {name} up to date.")
            return

        timestamps = ", ".join(timestamps)
        print(f"TXT {name} out of date! Timestamps: {timestamps}")
        subject = "ALERT Alerting system down?"
        message = f"TXT query for {name} on {server} gave the following response:\n"
        message += f"{str(response)}\n\n"
        message += f"{str(response_opts)}\n\n"
        message += f"Extracted timestamps in TXT RRset:\n{timestamps}"
        mail_admins(
            subject,
            message,
            connection=get_connection("django.core.mail.backends.smtp.EmailBackend"),
        )

    def handle(self, *args, **kwargs):
        try:
            self.alerting_healthcheck()
            self.update_healthcheck_timestamp()
            self.delete_expired_captchas()
            self.delete_never_activated_users()
        except Exception as e:
            subject = "chores Exception!"
            message = f"{type(e)}\n\n{str(e)}"
            print(f"Chores exception: {type(e)}, {str(e)}")
            mail_admins(
                subject,
                message,
                connection=get_connection(
                    "django.core.mail.backends.smtp.EmailBackend"
                ),
            )
