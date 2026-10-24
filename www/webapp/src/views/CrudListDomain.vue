<script>
import { HTTP, withWorking } from '@/utils';
import CrudList from './CrudList.vue';
import DomainSetupDialog from '@/views/Console/DomainSetupDialog.vue';
import {mdiDownload, mdiInformation, mdiRefresh} from "@mdi/js";
import DelegationStatus from "@/components/Field/DelegationStatus.vue";
import GenericText from "@/components/Field/GenericText.vue";
import GenericTextarea from "@/components/Field/GenericTextarea.vue";
import TimeAgo from "@/components/Field/TimeAgo.vue";
import {compareBySecurity, isRecheckable, isSecure} from "@/delegation";
import {recheckDelegation} from "@/delegationCheck";

export default {
  name: 'CrudListDomain',
  extends: CrudList,
  components: {
    DelegationStatus,
    DomainSetupDialog,
  },
  data() {
    const self = this;
    // "3 of your 5 domains are securely delegated (with DNSSEC)."
    const securedSentence = () => {
      const n = self.rows.length;
      const s = self.secure_domains;
      if (s == null || !n) {
        return '';
      }
      return `${s} of your ${n} domain${n === 1 ? '' : 's'} ${s === 1 ? 'is' : 'are'} securely delegated (with DNSSEC).`;
    };
    return {
        creatable: true,
        updatable: false,
        destroyable: true,
        rowsClickable: true,
        limit_domains: null,  // unknown until auth/account/ has been retrieved
        secure_domains: null,  // likewise
        checking: {},  // domain name -> true, while a re-check is under way
        unmounted: false,
        headlines: {
          table: 'Domains',
          create: 'Create New Domain',
          destroy: 'Domain Deletion',
        },
        texts: {
          banner: () => 'To edit your DNS records, click on one of your domains.',
          create: () => {
            if (self.limit_domains == null) {
              return '';
            }
            const secured = securedSentence();
            const growth = secured
                ? `${secured} Each domain you secure raises your limit.`
                : 'The limit grows as you delegate your domains to us securely (with DNSSEC).';
            return `You have ${self.availableCount} of ${self.limit_domains} domains left.<br /><small>${growth}</small>`;
          },
          createWarning: () => {
            if (self.availableCount > 0) {
              return '';
            }
            const secured = securedSentence();
            return secured
                ? `Domain limit reached. ${secured} Securing another one raises your limit. The Delegation column shows what each domain is missing.`
                : 'Domain limit reached. Delegate your domains to us securely (with DNSSEC) to make the limit grow.';
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
          status: {
            name: 'item.status',
            text: 'Delegation',
            align: 'left',
            sortable: true,
            sortRaw: compareBySecurity,
            value: 'status',
            readonly: true,
            richReadonly: true,
            datatype: DelegationStatus.name,
            searchable: false,
            fieldProps: item => ({domain: item.name, checking: !!self.checking[item.name]}),
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
            hideOnXs: true,  // leaves room for the delegation status
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
        'recheck': {
          go: d => this.recheckStatus(d),
          // On phones, the setup instructions offer it instead, along with the
          // explanation that the tooltip gives elsewhere; the row has no room.
          if: d => !this.display.xs && isRecheckable(d),
          loading: d => !!this.checking[d.name],
          icon: mdiRefresh,
          tooltip: 'Re-check delegation',
        },
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
  methods: {
    async fetchAccount() {
      await withWorking(this.error, () => HTTP
          .get('auth/account/')
          .then(r => {
            this.limit_domains = r.data.limit_domains;
            this.secure_domains = r.data.secure_domains;
          })
      );
    },
    /** *
     * Asks for the domain's delegation to be re-checked, and shows the result
     * once it is in. Not through withWorking(): waiting for the result may
     * take a while, and must not block the rest of the page.
     */
    async recheckStatus(domain) {
      if (this.checking[domain.name]) {
        return;
      }
      this.checking[domain.name] = true;
      const wasSecure = isSecure(domain.status);
      try {
        const {status, done} = await recheckDelegation(HTTP, domain.name, {
          shouldStop: () => this.unmounted,
        });
        if (this.unmounted) {
          return;
        }
        domain.status = status;
        if (!done) {
          this.notify('The check is taking longer than expected. It will finish in the background; reload later to see the result.', 'info');
        } else if (!wasSecure && isSecure(status)) {
          await this.fetchAccount();
          this.notify(`${domain.name} is now securely delegated. Your domain limit is now ${this.limit_domains}.`);
        }
      } catch (e) {
        if (e.response?.status === 429) {
          const wait = Number.parseInt(e.response.headers?.['retry-after'], 10);
          this.notify(
              Number.isFinite(wait)
                  ? `You can re-check ${domain.name} again in ${wait} seconds.`
                  : `You cannot re-check ${domain.name} again right now. Please try again later.`,
              'info',
          );
        } else {
          this.error(e);
        }
      } finally {
        delete this.checking[domain.name];
      }
    },
  },
  async created() {
    await this.fetchAccount();
  },
  beforeUnmount() {
    this.unmounted = true;
  },
};
</script>
