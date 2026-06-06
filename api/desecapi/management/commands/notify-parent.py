from django.core.management import BaseCommand, CommandError
import dns.resolver

from desecapi.models import Domain
from desecapi.utils import gethostbyname_cached


class Command(BaseCommand):
    debug = False
    help = "Notify parent to update the DS RRset."
    report_agent = dns.name.from_text(  # Must be below one parent-side NS
        # TODO Make a Domain property?
        "notify-agent.ns.desec.cz."
    )
    resolver: dns.resolver.Resolver

    def add_arguments(self, parser):
        parser.add_argument(
            "domain-name",
            nargs="*",
            help="Domain name to notify for. If omitted, notify for all domains known locally.",
        )

    def handle(self, *args, **options):
        domains = Domain.objects.all()
        self.debug = options.get("verbosity", 1) > 1

        if options["domain-name"]:
            domains = domains.filter(name__in=options["domain-name"])
            domain_names = domains.values_list("name", flat=True)

            for domain_name in options["domain-name"]:
                if domain_name not in domain_names:
                    raise CommandError("{} is not a known domain".format(domain_name))

        self.resolver = dns.resolver.Resolver(configure=False)
        self.resolver.nameservers = [gethostbyname_cached("resolver")]
        self.resolver.flags = dns.flags.RD | dns.flags.AD

        for domain in domains:
            self.stdout.write("%s ... " % domain.name, ending="")
            domain_name = dns.name.from_text(domain.name)
            try:
                answer = self._get_dsync(domain_name)
            except dns.exception.ValidationFailure as e:
                print(f"failed: {e}")
                continue
            except Exception as e:
                print("failed")
                msg = "Error while processing {}: {}".format(domain.name, e)
                raise CommandError(msg)

            if answer is None:
                print("unsupported")
            else:
                notifies = 0
                targets = 0
                for dsync in answer:
                    result = self._notify_domain(domain_name, dsync)
                    try:
                        result, response = result
                    except TypeError:  # None: DSYNC was not for NOTIFY(SOA)
                        continue
                    targets += 1
                    notifies += result
                    if not result and self.debug:
                        print(response)
                print(
                    f"notified, {notifies}/{targets} NOTIFY(SOA) targets confirmed (from {len(answer)} {answer.qname}/DSYNC total)"
                )

    def _resolve_securely(self, qname, rdtype):
        if self.debug:
            print(f"resolving {qname}/{rdtype} ...")
        try:
            answer = self.resolver.resolve(qname, rdtype)
            response = answer.response
        except dns.resolver.NoAnswer as e:
            answer = None
            response = e.response()
        except dns.resolver.NXDOMAIN as e:
            answer = None
            response = e.response(qname)
        finally:
            if not (response.flags & dns.flags.AD):
                raise dns.exception.ValidationFailure(
                    f"unauthenticated response: {qname}/{rdtype}"
                )
            return answer, response

    def _notify_domain(self, domain_name, dsync):
        # Only process NOTIFY(CDS)
        if dsync.scheme != 1 or dsync.rrtype != dns.rdatatype.CDS:
            return

        notify = dns.message.make_query(domain_name, dns.rdatatype.CDS)
        notify.set_opcode(dns.opcode.NOTIFY)
        notify.flags += dns.flags.AA - dns.flags.RD
        opt = dns.edns.ReportChannelOption(self.report_agent)
        notify.use_edns(edns=True, options=[opt])

        response = dns.query.udp(
            notify, gethostbyname_cached(dsync.target.to_text()), timeout=5
        )

        notify.flags += dns.flags.QR
        # TODO why does this work despite of the EDNS0 option not being in the response?
        return notify == response, response

    def _get_dsync(self, domain_name):
        # This implements the discovery algorithm from RFC 9859 Section 4.1

        # Try child-specific (or wildcard), assuming parent one level up
        qname = dns.name.Name((domain_name[0], "_dsync", *domain_name[1:]))
        answer, response = self._resolve_securely(qname, dns.rdatatype.DSYNC)
        if answer:
            return answer

        # Find parent
        owner_names = [
            rr.name
            for rr in response.authority
            if rr.rdtype == dns.rdatatype.SOA and rr.rdclass == dns.rdataclass.IN
        ]
        if len(owner_names) > 1:
            ValueError("Negative response has several SOA records")
        parent = owner_names[0]

        # Try child-specific (or wildcard), with parent from previous negative response
        infix = dns.name.from_text("_dsync").relativize(dns.name.root)
        parent_qname = domain_name - parent + infix + parent
        if parent_qname != qname:
            answer, _ = self._resolve_securely(parent_qname, dns.rdatatype.DSYNC)
            if answer:
                return answer

        # Try fall-back DSYNC record at _dsync.$parent
        qname = infix + parent
        return self._resolve_securely(qname, dns.rdatatype.DSYNC)[0]
