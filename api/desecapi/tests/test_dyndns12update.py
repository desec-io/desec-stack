import random

from rest_framework import status

from desecapi.models import BlockedSubnet
from desecapi.tests.base import DynDomainOwnerTestCase


class DynDNS12UpdateTest(DynDomainOwnerTestCase):
    def assertIP(self, ipv4=None, ipv6=None, name=None, subname=""):
        name = name or self.my_domain.name.lower()
        for type_, value in [("A", ipv4), ("AAAA", ipv6)]:
            url = self.reverse("v1:rrset", name=name, subname=subname, type=type_)
            response = self.client_token_authorized.get(url)
            if value:
                if not isinstance(value, set):
                    value = {value}
                self.assertStatus(response, status.HTTP_200_OK)
                self.assertEqual(set(response.data["records"]), value)
                self.assertEqual(response.data["ttl"], 60)
            else:
                self.assertStatus(response, status.HTTP_404_NOT_FOUND)

    def test_identification_by_domain_name(self):
        self.client.set_credentials_basic_auth(
            self.my_domain.name + ".invalid", self.token.plain
        )
        response = self.assertDynDNS12NoUpdate(mock_remote_addr="10.5.5.6")
        self.assertStatus(response, status.HTTP_401_UNAUTHORIZED)

    def test_identification_by_query_params(self):
        # /update?username=foobar.dedyn.io&password=secret
        self.client.set_credentials_basic_auth(None, None)
        response = self.assertDynDNS12Update(
            username=self.my_domain.name, password=self.token.plain
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")
        self.assertEqual(response.content_type, "text/plain")
        self.assertIP(ipv4="127.0.0.1")

    def test_identification_by_query_params_with_subdomain(self):
        # /update?username=baz.foobar.dedyn.io&password=secret
        self.client.set_credentials_basic_auth(None, None)
        response = self.assertDynDNS12NoUpdate(
            username="baz", password=self.token.plain
        )
        self.assertStatus(response, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.content, b"badauth")

        for subname in ["baz", "*.baz"]:
            response = self.assertDynDNS12Update(
                username=f"{subname}.{self.my_domain.name}", password=self.token.plain
            )
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertEqual(response.data, "good")
            self.assertIP(ipv4="127.0.0.1", subname=subname)

    def test_deviant_ttl(self):
        """
        The dynamic update will try to set the TTL to 60. Here, we create
        a record with a different TTL beforehand and then make sure that
        updates still work properly.
        """
        with self.assertRequests(
            self.request_pdns_zone_update(self.my_domain.name),
            self.request_pdns_zone_axfr(self.my_domain.name),
        ):
            response = self.client_token_authorized.patch_rr_set(
                self.my_domain.name.lower(), "", "A", {"ttl": 3600}
            )
            self.assertStatus(response, status.HTTP_200_OK)

        response = self.assertDynDNS12Update(self.my_domain.name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")
        self.assertIP(ipv4="127.0.0.1")

    def test_ddclient_dyndns1_v4_success(self):
        # /nic/dyndns?action=edit&started=1&hostname=YES&host_id=foobar.dedyn.io&myip=10.1.2.3
        with self.assertRequests(
            self.request_pdns_zone_update(self.my_domain.name),
            self.request_pdns_zone_axfr(self.my_domain.name),
        ):
            response = self.client.get(
                self.reverse("v1:dyndns12update"),
                {
                    "action": "edit",
                    "started": 1,
                    "hostname": "YES",
                    "host_id": self.my_domain.name,
                    "myip": "10.1.2.3",
                },
            )
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertEqual(response.data, "good")
            self.assertIP(ipv4="10.1.2.3")

        # Repeat and make sure that no pdns request is made (not even for the empty AAAA record)
        response = self.client.get(
            self.reverse("v1:dyndns12update"),
            {
                "action": "edit",
                "started": 1,
                "hostname": "YES",
                "host_id": self.my_domain.name,
                "myip": "10.1.2.3",
            },
        )
        self.assertStatus(response, status.HTTP_200_OK)

    def test_ddclient_dyndns1_v6_success(self):
        # /nic/dyndns?action=edit&started=1&hostname=YES&host_id=foobar.dedyn.io&myipv6=::1337
        response = self.assertDynDNS12Update(
            domain_name=self.my_domain.name,
            action="edit",
            started=1,
            hostname="YES",
            host_id=self.my_domain.name,
            myipv6="::1337",
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")
        self.assertIP(ipv4="127.0.0.1", ipv6="::1337")

        # Repeat and make sure that no pdns request is made (not even for the empty A record)
        response = self.client.get(
            self.reverse("v1:dyndns12update"),
            {
                "domain_name": self.my_domain.name,
                "action": "edit",
                "started": 1,
                "hostname": "YES",
                "host_id": self.my_domain.name,
                "myipv6": "::1337",
            },
        )
        self.assertStatus(response, status.HTTP_200_OK)

    def test_ddclient_dyndns2_v4_success(self):
        # /nic/update?system=dyndns&hostname=foobar.dedyn.io&myip=10.2.3.4
        response = self.assertDynDNS12Update(
            domain_name=self.my_domain.name,
            system="dyndns",
            hostname=self.my_domain.name,
            myip="10.2.3.4",
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")
        self.assertIP(ipv4="10.2.3.4")

    def test_ddclient_dyndns2_v4_invalid(self):
        # /nic/update?system=dyndns&hostname=foobar.dedyn.io&myip=10.2.3.4asdf
        params = {
            "domain_name": self.my_domain.name,
            "system": "dyndns",
            "hostname": self.my_domain.name,
            "myip": "10.2.3.4asdf",
        }
        response = self.client.get(self.reverse("v1:dyndns12update"), params)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertIn("malformed", str(response.data))

    def test_ddclient_dyndns2_v4_invalid_or_foreign_domain(self):
        # /nic/update?system=dyndns&hostname=<...>&myip=10.2.3.4
        for name in [
            self.owner.email,
            self.other_domain.name,
            self.my_domain.parent_domain_name,
        ]:
            response = self.assertDynDNS12NoUpdate(
                system="dyndns",
                hostname=name,
                myip="10.2.3.4",
            )
            self.assertStatus(response, status.HTTP_404_NOT_FOUND)
            self.assertEqual(response.content, b"nohost")

    def test_ddclient_dyndns2_v4_blocked(self):
        # /nic/update?system=dyndns&hostname=foobar.dedyn.io&myip=3.2.2.3
        BlockedSubnet.from_ip("3.2.2.3").save()
        params = {
            "domain_name": self.my_domain.name,
            "system": "dyndns",
            "hostname": self.my_domain.name,
            "myip": "3.2.2.5",
        }
        response = self.client.get(self.reverse("v1:dyndns12update"), params)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertIn("IP address 3.2.2.5 not allowed.", str(response.data))

    def test_ddclient_dyndns2_v6_success(self):
        # /nic/update?system=dyndns&hostname=foobar.dedyn.io&myipv6=::1338
        response = self.assertDynDNS12Update(
            domain_name=self.my_domain.name,
            system="dyndns",
            hostname=self.my_domain.name,
            myipv6="::666",
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")
        self.assertIP(ipv4="127.0.0.1", ipv6="::666")

    def test_ddclient_dyndns2_mixed_success(self):
        response = self.assertDynDNS12Update(
            domain_name=self.my_domain.name,
            system="dyndns",
            hostname=self.my_domain.name,
            myip="10.2.3.4, ::2 , 10.6.5.4 ,::4",
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")
        self.assertIP(ipv4={"10.2.3.4", "10.6.5.4"}, ipv6={"::2", "::4"})

    def test_ddclient_dyndns2_mixed_invalid(self):
        for myip in ["10.2.3.4, ", "preserve,::2"]:
            response = self.assertDynDNS12NoUpdate(
                domain_name=self.my_domain.name,
                system="dyndns",
                hostname=self.my_domain.name,
                myip=myip,
            )
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data["code"], "inconsistent-parameter")

    def test_fritz_box(self):
        # /
        response = self.assertDynDNS12Update(self.my_domain.name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")
        self.assertIP(ipv4="127.0.0.1")

    def test_unset_ip(self):
        for v4, v6 in [
            ("127.0.0.1", "::1"),
            ("127.0.0.1", ""),
            ("", "::1"),
            ("", ""),
        ]:
            response = self.assertDynDNS12Update(self.my_domain.name, ip=v4, ipv6=v6)
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertEqual(response.data, "good")
            self.assertIP(ipv4=v4, ipv6=v6)

    def test_preserve_ip(self):
        current_v4 = "127.0.0.1"
        current_v6 = "::1"
        self.assertDynDNS12Update(self.my_domain.name, ip=current_v4, ipv6=current_v6)
        for v4, v6 in [
            ("preserve", "::3"),
            ("1.2.3.4", "preserve"),
            ("preserve", "preserve"),
        ]:
            self.assertDynDNS12Update(
                self.my_domain.name, ip=v4, ipv6=v6, expect_update=v4 != v6
            )
            current_v4 = current_v4 if v4 == "preserve" else v4
            current_v6 = current_v6 if v6 == "preserve" else v6
            self.assertIP(ipv4=current_v4, ipv6=current_v6)


class SingleDomainDynDNS12UpdateTest(DynDNS12UpdateTest):
    NUM_OWNED_DOMAINS = 1

    def test_identification_by_token(self):
        self.client.set_credentials_basic_auth("", self.token.plain)
        response = self.assertDynDNS12Update(
            self.my_domain.name, mock_remote_addr="10.5.5.6"
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")
        self.assertIP(ipv4="10.5.5.6")

    def test_identification_by_email(self):
        self.client.set_credentials_basic_auth(self.owner.email, self.token.plain)
        response = self.assertDynDNS12Update(
            self.my_domain.name, mock_remote_addr="10.5.5.6"
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")
        self.assertIP(ipv4="10.5.5.6")


class MultipleDomainDynDNS12UpdateTest(DynDNS12UpdateTest):
    NUM_OWNED_DOMAINS = 4

    def test_ignore_minimum_ttl(self):
        self.my_domain.minimum_ttl = 61
        self.my_domain.save()

        # Test that dynDNS updates work both under a local public suffix (self.my_domain) and for a custom domains
        for domain in [self.my_domain, self.create_domain(owner=self.owner)]:
            self.assertGreater(domain.minimum_ttl, 60)
            self.client.set_credentials_basic_auth(
                domain.name.lower(), self.token.plain
            )
            response = self.assertDynDNS12Update(domain.name)
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertEqual(domain.rrset_set.get(subname="", type="A").ttl, 60)

    def test_identification_by_token(self):
        """
        Test if the conflict of having multiple domains, but not specifying which to update is correctly recognized.
        """
        self.client.set_credentials_basic_auth("", self.token.plain)
        response = self.client.get(
            self.reverse("v1:dyndns12update"), REMOTE_ADDR="10.5.5.7"
        )
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)


class MixedCaseDynDNS12UpdateTestCase(DynDNS12UpdateTest):
    @staticmethod
    def random_casing(s):
        return "".join(
            [c.lower() if random.choice([True, False]) else c.upper() for c in s]
        )

    def setUp(self):
        super().setUp()
        self.my_domain.name = self.random_casing(self.my_domain.name)


class UppercaseDynDNS12UpdateTestCase(DynDNS12UpdateTest):
    def setUp(self):
        super().setUp()
        self.my_domain.name = self.my_domain.name.upper()
