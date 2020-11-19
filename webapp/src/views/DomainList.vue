<script>
import { HTTP, withWorking } from '@/utils';
import CrudList from './CrudList';
import DomainDetailsDialog from '@/views/Console/DomainDetailsDialog';

export default {
  name: 'DomainList',
  extends: CrudList,
  components: {
    DomainDetailsDialog,
  },
  data() {
    const self = this;
    return {
        createable: true,
        updatable: false,
        destroyable: true,
        limit_domains: 0,
        headlines: {
          table: 'Domains',
          create: 'Create New Domain',
          destroy: 'Domain Deletion',
        },
        texts: {
          banner: () => 'To edit your DNS records, click on one of your domains.',
          create: () => `You have ${self.availableCount} of ${self.limit_domains} domains left.`,
          createWarning: () => (self.availableCount <= 0 ? 'You have reached your maximum number of domains. Please contact support to apply for a higher limit.' : ''),
          destroy: d => (`Delete domain ${d.name}?`),
          destroyInfo: () => 'This operation will cause the domain to disappear from the DNS. It will no longer be reachable from the Internet.',
        },
        columns: {
          name: {
            name: 'item.name',
            text: 'Name',
            textCreate: 'Enter Domain Name',
            align: 'left',
            sortable: true,
            value: 'name',
            readonly: true,
            required: true,
            writeOnCreate: true,
            datatype: 'GenericText',
            searchable: true,
          },
          published: {
            name: 'item.published',
            text: 'Published',
            align: 'left',
            sortable: true,
            value: 'published',
            readonly: true,
            datatype: 'TimeAgo',
            searchable: false,
          },
        },
        actions: [
          {
            key: 'info',
            go: d => this.showDomainInfo(d),
            icon: 'mdi-information',
          },
        ],
        paths: {
          list: 'domains/',
          create: 'domains/',
          delete: 'domains/:{name}/',
        },
        itemDefaults: () => ({ name: '' }),
        postcreate: d => {
          this.close();
          this.showDomainInfo(d, true);
        },
        async showDomainInfo(d, isNew = false) {
          const url = this.resourcePath(this.paths.delete, d, ':');
          if (d.keys === undefined) {
            await withWorking(this.error, () => HTTP
                .get(url)
                .then(r => {
                  d.keys = r.data.keys;
                  d.published = r.data.published;
                })
            );
          }
          let ds = d.keys.map(key => key.ds);
          ds = ds.concat.apply([], ds)
          this.extraComponentBind = {'name': d.name, 'ds': ds, 'published': d.published, 'is-new': isNew};
          if (process.env.VUE_APP_LOCAL_PUBLIC_SUFFIXES.split(' ').some((suffix) => d.name.endsWith(`.${suffix}`))) {
            this.extraComponentBind['ips'] = [];
            await withWorking(this.error, async (o) => {
              let urlRRset = `${url}/rrsets/?subname=&type=`;
              for (let type of ['A', 'AAAA']) {
                await HTTP.get(`${urlRRset}${type}`).then(r => r.data.length && o['ips'].push(...r.data[0].records));
              }
            }, this.extraComponentBind);
          }
          this.extraComponentName = 'DomainDetailsDialog';
        },
        handleRowClick: (value) => {
          this.$router.push({name: 'domain', params: {domain: value.name}});
        },
    }
  },
  computed: {
    availableCount: function () {
      return this.limit_domains - this.rows.length;
    },
    createInhibited: function () {
      return this.availableCount <= 0;
    },
  },
  async created() {
    const self = this;
    await withWorking(this.error, () => HTTP
        .get('auth/account/')
        .then(r => self.limit_domains = r.data.limit_domains)
    );
  },
};
</script>
