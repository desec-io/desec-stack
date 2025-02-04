<script>
import { HTTP, withWorking } from '@/utils';
import CrudList from './CrudList.vue';
import DomainSetupDialog from '@/views/Console/DomainSetupDialog.vue';
import {mdiDownload, mdiInformation} from "@mdi/js";
import GenericText from "@/components/Field/GenericText.vue";
import GenericTextarea from "@/components/Field/GenericTextarea.vue";
import TimeAgo from "@/components/Field/TimeAgo.vue";

export default {
  name: 'CrudListDomain',
  extends: CrudList,
  components: {
    DomainSetupDialog,
  },
  data() {
    const self = this;
    return {
        creatable: true,
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
          create: () => self.limit_domains != null ? `You have ${self.availableCount} of ${self.limit_domains} domains left.<br /><small>Contact support to apply for a higher limit.</small>` : '',
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
            datatype: GenericText.name,
            searchable: true,
          },
          published: {
            name: 'item.published',
            text: 'Published',
            align: 'left',
            sortable: true,
            value: 'published',
            readonly: true,
            datatype: TimeAgo.name,
            searchable: false,
          },
          zonefile: {
            name: 'item.zonefile',
            text: 'Zonefile',
            textCreate: 'Zonefile for import (paste here)',
            align: 'left',
            value: 'zonefile',
            writeOnCreate: true,
            datatype: GenericTextarea.name,
            searchable: false,
            fieldProps: () => ({ hint: 'Note: automatically managed records will be ignored!' }),
            hideFromTable: true,
            advanced: true,
          }
        },
        paths: {
          list: 'domains/',
          create: 'domains/',
          delete: 'domains/:{name}/',
          export: 'domains/:{name}/zonefile/',
        },
        itemDefaults: () => ({ name: '' }),
        postcreate: d => {
          this.close();
          this.showDomainInfo(d, true);
        },
        async exportDomain(domain) {
          const url = this.resourcePath(this.paths.export, domain, ':');
          await withWorking(this.error, () => HTTP
              .get(url, {responseType: 'blob'})
              .then(r => new Blob([r.data], {type: r.headers['content-type']}))
              .then(zoneblob => {
                const elem = window.document.createElement('a');
                elem.href = window.URL.createObjectURL(zoneblob);
                elem.download = `${domain.name}.zone`;
                elem.style.display = 'none';
                document.body.appendChild(elem);
                elem.click();
                window.URL.revokeObjectURL(elem.href);
                document.body.removeChild(elem);
            })
          );
        },
        async showDomainInfo(d, isNew = false) {
          const url = this.resourcePath(this.paths.delete, d, ':');
          if (d.keys === undefined) {
            await withWorking(this.error, () => HTTP
                .get(url)
                .then(r => {
                  d.keys = r.data.keys;
                })
            );
          }
          let ds = d.keys.map(key => key.ds);
          ds = ds.concat.apply([], ds).filter(v => v.split(" ")[2] == 2)
          let dnskey = d.keys.map(key => key.dnskey).filter(v => v.split(" ")[0] == 257);
          this.extraComponentBind = {'domain': d.name, 'ds': ds, 'dnskey': dnskey, 'is-new': isNew};
          this.extraComponentName = 'DomainSetupDialog';
        },
        handleRowClick: (value) => {
          this.$router.push({name: 'domain', params: {domain: value.name}});
        },
    }
  },
  computed: {
    actions() {
      return {
        'info': {
          go: d => this.showDomainInfo(d),
          icon: mdiInformation,
          tooltip: 'Setup instructions',
        },
        'export': {
          go: d => this.exportDomain(d),
          icon: mdiDownload,
          if: this.showAdvanced,
          tooltip: 'Export (zonefile format)',
        },
      };
    },
    availableCount: function () {
      return this.limit_domains != null ? Math.max(this.limit_domains - this.rows.length, 0) : Infinity;
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
