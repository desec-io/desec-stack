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

    def test_ddclient_dyndns2_v4_valid_priority(self):
        params = {
            "domain_name": self.my_domain.name,
            "system": "dyndns",
            "hostname": self.my_domain.name,
            "myip": "invalid",
            "ip": "10.4.2.1",
        }
        response = self.client.get(self.reverse("v1:dyndns12update"), params)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")
        self.assertIP(ipv4="10.4.2.1")

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
            self.assertEqual(response.data[0].code, "inconsistent-parameter")

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

    def test_subnet(self):
        subnet_v4 = "6.7.3.4/16"
        subnet_v6 = "2a01::3303:72dc:f412:7233/64"

        # Can't provide other addresses during subnet update
        response = self.assertDynDNS12Update(
            myip=f"{subnet_v4},127.0.0.1", expect_update=False
        )
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data[0].code, "multiple-subnet")

        # Only allow syntactically valid subnets
        response = self.assertDynDNS12Update(myip=f"127.0.0.1//", expect_update=False)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data[0].code, "invalid-subnet")

        # Update all IPv4 addresses and all (none) IPv6 addresses
        response = self.assertDynDNS12Update(
            hostname=self.my_domain.name, myip=subnet_v4, myipv6=subnet_v6
        )
        self.assertEqual(response.data, "good")
        self.assertIP(ipv4={"6.7.0.1", "6.7.2.3"}, ipv6=set())

        # Try for IPv6
        self.create_rr_set(
            self.my_domain,
            ["2a02:8109:9283:8800::f12:7233"],
            type="AAAA",
            subname="foo",
            ttl=123,
        )

        response = self.assertDynDNS12Update(
            hostname=f"foo.{self.my_domain.name}", myipv4="", myipv6=subnet_v6
        )
        self.assertEqual(response.data, "good")
        self.assertIP(ipv6="2a01::f12:7233", subname="foo")

    def test_update_multiple_v4(self):
        # /nic/update?hostname=a.io,sub.a.io&myip=1.2.3.4
        new_ip = "1.2.3.4"
        domain1 = self.my_domain.name
        domain2 = "sub." + self.my_domain.name

        with self.assertRequests(
            self.request_pdns_zone_update(domain1),
            self.request_pdns_zone_axfr(domain1),
        ):
            response = self.client.get(
                self.reverse("v1:dyndns12update"),
                {"hostname": f"{domain1},{domain2}", "myip": new_ip},
            )

        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")

        self.assertIP(ipv4=new_ip)
        self.assertIP(subname="sub", ipv4=new_ip)

    def test_update_multiple_with_overwrite(self):
        # /nic/update?hostname=sub1.a.io,sub2.a.io,sub3.a.io&myip=1.2.3.4&ipv6=::1&sub2.a.io.ipv6=::2
        new_ip4 = "1.2.3.4"
        new_ip6 = "::1"
        new_ip6_overwrite = "::2"
        domain1 = "sub1." + self.my_domain.name
        domain2 = "sub2." + self.my_domain.name
        domain3 = "sub3." + self.my_domain.name

        with self.assertRequests(
            self.request_pdns_zone_update(self.my_domain.name),
            self.request_pdns_zone_axfr(self.my_domain.name),
        ):
            response = self.client.get(
                self.reverse("v1:dyndns12update"),
                {
                    "hostname": f"{domain1},{domain2},{domain3}",
                    "myip": new_ip4,
                    "ipv6": new_ip6,
                    f"myipv6:{domain2}": new_ip6_overwrite,
                },
            )

        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")

        self.assertIP(subname="sub1", ipv4=new_ip4, ipv6=new_ip6)
        self.assertIP(subname="sub2", ipv4=new_ip4, ipv6=new_ip6_overwrite)
        self.assertIP(subname="sub3", ipv4=new_ip4, ipv6=new_ip6)

    def test_update_multiple_with_extra(self):
        # /nic/update?hostname=sub1.a.io,sub3.a.io&myip=1.2.3.4&ipv6=::1&sub2.a.io.ipv6=::2
        old_ip4 = "10.0.0.2"
        new_ip4 = "1.2.3.4"
        new_ip6 = "::1"
        new_ip6_extra = "::2"
        domain1 = "sub1." + self.my_domain.name
        domain2 = "sub2." + self.my_domain.name
        domain3 = "sub3." + self.my_domain.name
        self.create_rr_set(self.my_domain, [old_ip4], subname="sub2", type="A", ttl=60)

        with self.assertRequests(
            self.request_pdns_zone_update(self.my_domain.name),
            self.request_pdns_zone_axfr(self.my_domain.name),
        ):
            response = self.client.get(
                self.reverse("v1:dyndns12update"),
                {
                    "hostname": f"{domain1},{domain3}",
                    "myip": new_ip4,
                    "ipv6": new_ip6,
                    f"myipv6:{domain2}": new_ip6_extra,
                },
            )

        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")

        self.assertIP(subname="sub1", ipv4=new_ip4, ipv6=new_ip6)
        self.assertIP(subname="sub2", ipv4=old_ip4, ipv6=new_ip6_extra)
        self.assertIP(subname="sub3", ipv4=new_ip4, ipv6=new_ip6)

    def test_update_multiple_username_param(self):
        # /nic/update?username=a.io,sub.a.io&myip=1.2.3.4
        new_ip = "1.2.3.4"
        domain1 = self.my_domain.name
        domain2 = "sub." + self.my_domain.name

        with self.assertRequests(
            self.request_pdns_zone_update(domain1),
            self.request_pdns_zone_axfr(domain1),
        ):
            response = self.client_token_authorized.get(
                self.reverse("v1:dyndns12update"),
                {"username": f"{domain1},{domain2}", "myip": new_ip},
            )

        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")

        self.assertIP(ipv4=new_ip)
        self.assertIP(subname="sub", ipv4=new_ip)

    def test_update_multiple_v4v6(self):
        # /nic/update?hostname=a.io,sub.a.io&myip=1.2.3.4&myipv6=1::1
        new_ip4 = "1.2.3.4"
        new_ip6 = "1::1"
        domain1 = self.my_domain.name
        domain2 = "sub." + domain1

        with self.assertRequests(
            self.request_pdns_zone_update(domain1),
            self.request_pdns_zone_axfr(domain1),
        ):
            response = self.client.get(
                self.reverse("v1:dyndns12update"),
                {
                    "hostname": f"{domain1},{domain2}",
                    "myip": new_ip4,
                    "myipv6": new_ip6,
                },
            )

        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")

        self.assertIP(ipv4=new_ip4, ipv6=new_ip6)
        self.assertIP(subname="sub", ipv4=new_ip4, ipv6=new_ip6)

    def test_update_multiple_with_subnet(self):
        # /nic/update?hostname=sub1.a.io,sub2.a.io&myip=10.1.0.0/16
        domain1 = "sub1." + self.my_domain.name
        domain2 = "sub2." + self.my_domain.name
        self.create_rr_set(
            self.my_domain, ["10.0.0.1"], subname="sub1", type="A", ttl=60
        )
        self.create_rr_set(
            self.my_domain, ["10.0.0.2"], subname="sub2", type="A", ttl=60
        )

        with self.assertRequests(
            self.request_pdns_zone_update(self.my_domain.name),
            self.request_pdns_zone_axfr(self.my_domain.name),
        ):
            response = self.client.get(
                self.reverse("v1:dyndns12update"),
                {"hostname": f"{domain1},{domain2}", "myip": "10.1.0.0/16"},
            )

        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")

        self.assertIP(subname="sub1", ipv4="10.1.0.1")
        self.assertIP(subname="sub2", ipv4="10.1.0.2")

    def test_update_multiple_with_subnet_and_ip_override(self):
        # /nic/update?hostname=a.io,b.io&myip=10.1.0.0/16&a.io=192.168.1.1
        domain1 = "sub1." + self.my_domain.name
        domain2 = "sub2." + self.my_domain.name
        self.create_rr_set(
            self.my_domain, ["10.0.0.1"], subname="sub1", type="A", ttl=60
        )
        self.create_rr_set(
            self.my_domain, ["10.0.0.2"], subname="sub2", type="A", ttl=60
        )

        with self.assertRequests(
            self.request_pdns_zone_update(self.my_domain.name),
            self.request_pdns_zone_axfr(self.my_domain.name),
        ):
            response = self.client.get(
                self.reverse("v1:dyndns12update"),
                {
                    "hostname": f"{domain1},{domain2}",
                    "myip": "10.1.0.0/16",
                    f"myipv4:{domain1}": "192.168.1.1",
                },
            )

        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")

        self.assertIP(subname="sub1", ipv4="192.168.1.1")
        self.assertIP(subname="sub2", ipv4="10.1.0.2")

    def test_update_multiple_with_one_being_already_up_to_date(self):
        # /nic/update?hostname=a.io,sub.a.io&myip=1.2.3.4
        new_ip = "1.2.3.4"
        domain1 = self.my_domain.name
        domain2 = "sub." + domain1
        self.create_rr_set(self.my_domain, [new_ip], subname="sub", type="A", ttl=60)

        with self.assertRequests(
            self.request_pdns_zone_update(domain1),
            self.request_pdns_zone_axfr(domain1),
        ):
            response = self.client.get(
                self.reverse("v1:dyndns12update"),
                {"hostname": f"{domain1},{domain2}", "myip": new_ip},
            )

        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")

        self.assertIP(ipv4=new_ip)
        self.assertIP(subname="sub", ipv4=new_ip)

    def test_update_same_domain_twice(self):
        # /nic/update?hostname=foobar.dedyn.io,foobar.dedyn.io&myip=1.2.3.4
        new_ip = "1.2.3.4"

        with self.assertRequests(
            self.request_pdns_zone_update(self.my_domain.name),
            self.request_pdns_zone_axfr(self.my_domain.name),
        ):
            response = self.client.get(
                self.reverse("v1:dyndns12update"),
                {
                    "hostname": f"{self.my_domain.name},{self.my_domain.name}",
                    "myip": new_ip,
                },
            )

        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")

        self.assertIP(ipv4=new_ip)

    def test_update_overwrite_with_invalid_subnet(self):
        # /nic/update?hostname=a.io&a.io.myip=1.2.3.4/64
        domain1 = self.create_domain(owner=self.owner).name

        with self.assertRequests():
            response = self.client.get(
                self.reverse("v1:dyndns12update"),
                {"hostname": f"{domain1}", f"myipv4:{domain1}": "1.2.3.4/64"},
            )

        self.assertContains(
            response, "invalid subnet", status_code=status.HTTP_400_BAD_REQUEST
        )

    def test_update_multiple_with_invalid_subnet(self):
        # /nic/update?hostname=sub1.a.io,sub2.a.io&myip=1.2.3.4/64
        domain1 = "sub1." + self.my_domain.name
        domain2 = "sub2." + self.my_domain.name

        with self.assertRequests():
            response = self.client.get(
                self.reverse("v1:dyndns12update"),
                {"hostname": f"{domain1},{domain2}", "myip": "1.2.3.4/64"},
            )

        self.assertContains(
            response, "invalid subnet", status_code=status.HTTP_400_BAD_REQUEST
        )

    def test_update_multiple_with_subdomains_of_different_domains(self):
        # /nic/update?hostname=a.io,b.io&myip=1.2.3.4
        domain1 = "sub1." + self.my_domain.name
        domain2 = "sub2." + self.create_domain(owner=self.owner).name

        with self.assertRequests():
            response = self.client.get(
                self.reverse("v1:dyndns12update"),
                {"hostname": f"{domain1},{domain2}", "myip": "1.2.3.4"},
            )

        self.assertContains(
            response,
            "Cannot update subdomains from more than one domain.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    def test_update_with_trailing_comma(self):
        response = self.client_token_authorized.get(
            self.reverse("v1:dyndns12update"),
            {"host_id": f"{self.my_domain.name},", "myip": "1.2.3.4"},
        )

        self.assertStatus(response, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.content, b"nohost")

    def test_update_with_partial_ownership(self):
        with self.assertRequests():
            response = self.client.get(
                self.reverse("v1:dyndns12update"),
                {
                    "hostname": f"{self.my_domain.name},{self.other_domain.name}",
                    "myip": "1.2.3.4",
                },
            )

        self.assertStatus(response, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.content, b"nohost")


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

    def test_empty_hostname(self):
        # Test that dynDNS updates work when &hostname= is given with username in basic auth
        self.client.set_credentials_basic_auth(
            self.my_domain.name.lower(), self.token.plain
        )
        response = self.assertDynDNS12Update(self.my_domain.name, hostname="")
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, "good")
        self.assertIP(ipv4="127.0.0.1")

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
