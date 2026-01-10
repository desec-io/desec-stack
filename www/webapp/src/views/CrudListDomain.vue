<script>
import { HTTP, withWorking } from '@/utils';
import CrudList from './CrudList.vue';
import DomainSetupDialog from '@/views/Console/DomainSetupDialog.vue';
import {mdiDownload, mdiInformation, mdiRefresh} from "@mdi/js";
import GenericText from "@/components/Field/GenericText.vue";
import GenericTextarea from "@/components/Field/GenericTextarea.vue";
import TimeAgo from "@/components/Field/TimeAgo.vue";
import DelegationStatus from "@/components/Field/DelegationStatus.vue";
import DelegationCheckDialog from "@/views/Console/DelegationCheckDialog.vue";

export default {
  name: 'CrudListDomain',
  extends: CrudList,
  components: {
    DomainSetupDialog,
    DelegationCheckDialog,
  },
  data() {
    const self = this;
    return {
        creatable: true,
        updatable: false,
        destroyable: true,
        limit_domains: 0,
        limit_insecure_domains: null,
        insecure_delegated_domains: 0,
        headlines: {
          table: 'Domains',
          create: 'Create New Domain',
          destroy: 'Domain Deletion',
        },
        texts: {
          banner: () => 'To edit your DNS records, click on one of your domains.',
          create: () => {
            if (self.limit_domains != null) {
              return `You have ${self.availableCount} of ${self.limit_domains} domains left.<br /><small>Contact support to apply for a higher limit.</small>`;
            }
            if (self.limit_insecure_domains == null) {
              return 'You can create multiple domains.';
            }
            return `You can create multiple domains. You currently have ${self.insecure_delegated_domains} of ${self.limit_insecure_domains} domains without DNSSEC. Secure them before creating more.`;
          },
          createWarning: () => {
            if (self.availableCount <= 0 && self.limit_domains != null) {
              return 'You have reached your maximum number of domains. Please contact support to apply for a higher limit.';
            }
            if (self.limit_insecure_domains === 0) {
              return 'Domain creation is disabled for your account. Please contact support if you need additional domains.';
            }
            if (self.limit_insecure_domains != null && self.insecure_delegated_domains >= self.limit_insecure_domains) {
              return 'You have reached your limit of domains without DNSSEC. Secure an existing domain first, then you can create more.';
            }
            return '';
          },
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
          delegation_status: {
            name: 'item.delegation_status',
            text: 'Delegation Status',
            align: 'left',
            sortable: false,
            value: 'delegation_checked',
            readonly: true,
            datatype: DelegationStatus.name,
            searchable: false,
            fieldProps: item => ({ item }),
          },
          delegation_checked: {
            name: 'item.delegation_checked',
            text: 'Last Checked',
            align: 'left',
            sortable: true,
            value: 'delegation_checked',
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
          delegationCheck: 'domains/:{name}/delegation-check/',
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
        async runDelegationCheck(domain) {
          const url = this.resourcePath(this.paths.delegationCheck, domain, ':');
          await withWorking(this.error, () => HTTP
              .post(url)
              .then(r => {
                Object.assign(domain, r.data);
                this.extraComponentBind = { domain };
                this.extraComponentName = 'DelegationCheckDialog';
              })
          );
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
        'delegation_check': {
          go: d => this.runDelegationCheck(d),
          icon: mdiRefresh,
          tooltip: 'Check delegation status',
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
      return this.availableCount <= 0
        || this.limit_insecure_domains === 0
        || (this.limit_insecure_domains != null
          && this.insecure_delegated_domains >= this.limit_insecure_domains);
    },
  },
  async created() {
    const self = this;
    await withWorking(this.error, () => HTTP
        .get('auth/account/')
        .then(r => {
          self.limit_domains = r.data.limit_domains;
          self.limit_insecure_domains = r.data.limit_insecure_domains ?? null;
          self.insecure_delegated_domains = r.data.insecure_delegated_domains ?? 0;
        })
    );
  },
};
</script>
