from django.core.management import BaseCommand, CommandError

from desecapi.models import Domain


class Command(BaseCommand):
    help = 'Import authoritative data from pdns, making the local database consistent with pdns.'

    def add_arguments(self, parser):
        parser.add_argument('domain-name', nargs='*',
                            help='Domain name to import. If omitted, will import all domains that are known locally.')

    def handle(self, *args, **options):
        domains = Domain.objects.all()

        if options['domain-name']:
            domains = domains.filter(name__in=options['domain-name'])
            domain_names = domains.values_list('name', flat=True)

            for domain_name in options['domain-name']:
                if domain_name not in domain_names:
                    raise CommandError('{} is not a known domain'.format(domain_name))

        for domain in domains:
            self.stdout.write('%s ...' % domain.name, ending='')
            try:
                domain.sync_from_pdns()
                self.stdout.write(' synced')
            except Exception as e:
                if str(e).startswith('Could not find domain ') \
                        and domain.owner.locked:
                    self.stdout.write(' skipped')
                else:
                    self.stdout.write(' failed')
                    msg = 'Error while processing {}: {}'.format(domain.name, e)
                    raise CommandError(msg)
