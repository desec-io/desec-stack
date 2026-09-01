<script>
import CrudList from '@/views/CrudList.vue';
import {HTTP, withWorking} from "@/utils"
import GenericText from "@/components/Field/GenericText.vue";
import RecordList from "@/components/Field/RecordList.vue";
import TTL from "@/components/Field/TTL.vue";
import TimeAgo from "@/components/Field/TimeAgo.vue";
import RRSetType from "@/components/Field/RRSetType.vue";

const DEFAULT_TTL = Number.parseInt(import.meta.env.VITE_APP_DEFAULT_TTL || '3600', 10) || 3600;

export default {
  name: 'CrudListRecord',
  extends: CrudList,
  data: function () {
    const self = this;
    return {
      minimumTTL: 60,
      defaultTTL: DEFAULT_TTL,
      domainTTLLoaded: false,
      fullWidth: true,
      creatable: true,
      updatable: true,
      destroyable: true,
      headlines: {
        table: `Record Sets ${self.$route.params.domain}`,
        create: `Create New Record Set (${self.$route.params.domain})`,
        destroy: 'Delete Record Set',
      },
      texts: {
        banner: () => 'You can edit your DNS records here. If you have questions, feel free to post in <a href="https://talk.desec.io/" target="_blank">our forum</a>, or shoot us an email.',
        create: () => (''),
        destroy: rrset => (`Delete record set for type ${rrset.type} at ${rrset.subname && rrset.subname || "domain origin"}?`),
        destroyInfo: () => ('This operation will permanently remove this information from the DNS.'),
      },
      columns: {
        type: {
          name: 'item.type',
          text: 'Type',
          textCreate: 'Record Set Type',
          align: 'left',
          sortable: true,
          value: 'type',
          readonly: true,
          required: true,
          datatype: RRSetType.name,
          searchable: true,
          writeOnCreate: true,
          width: '120px',
        },
        subname: {
          name: 'item.subname',
          text: 'Subname',
          align: 'left',
          hint: 'This is only the part in front of your domain. Example: "www"',
          sortable: true,
          value: 'subname',
          readonly: true,
          datatype: GenericText.name,
          fieldProps: () => ({
            rules: [
              v => !(v.startsWith('.') || v.endsWith('.') || v.includes('..'))
                  || 'Dots must be surrounded by other characters.',
              v => !!v.match(/^([*]|(([*][.])?([a-z0-9_-]{1,63}[.])*[a-z0-9_-]{1,63}))?$/)
                  || 'Allowed characters: a-z, 0-9, and -_. May start with "*." or just be "*".',
            ],
            hintWarning: v => ('.' + v).endsWith('.' + self.$route.params.domain),
          }),
          searchable: true,
          writeOnCreate: true,
        },
        records: {
          name: 'item.records',
          text: 'Content',
          textCreate: 'Record Set Content',
          align: 'left',
          sortable: false,
          value: 'records',
          readonly: false,
          required: true,
          datatype: RecordList.name,
          fieldProps: rrSet => ({ type: rrSet.type || 'A' }),
          searchable: true,
          maxWidth: '35vw',  // long values scroll inside the cell instead of widening the table
        },
        ttl: {
          name: 'item.ttl',
          text: 'TTL (seconds)',
          align: 'left',
          sortable: true,
          value: 'ttl',
          readonly: false,
          required: true,
          datatype: TTL.name,
          fieldProps: () => ({ min: self.minimumTTL }),
          searchable: true,
          width: '130px',
        },
        touched: {
          name: 'item.touched',
          text: 'Last touched',
          align: 'left',
          sortable: true,
          value: 'touched',
          readonly: true,
          datatype: TimeAgo.name,
          searchable: false,
          width: '130px',
        },
      },
      paths: {
        list: 'domains/::{domain}/rrsets/', // TODO dangerous?
        create: 'domains/::{domain}/rrsets/',
        delete: 'domains/::{domain}/rrsets/:{subname}.../:{type}/',
        update: 'domains/::{domain}/rrsets/:{subname}.../:{type}/',
      },
      itemDefaults: () => ({
        type: 'A', subname: '', records: [''], ttl: self.defaultTTL,
      }),
    }
  },
  computed: {
    createInhibited() {
      return !this.domainTTLLoaded;
    },
  },
  async created() {
    const self = this;
    const url = self.resourcePath('domains/::{domain}/', self.$route.params, '::');
    const response = await withWorking(this.error, () => HTTP.get(url));
    if (!response) {
      return;
    }
    self.minimumTTL = response.data['minimum_ttl'];
    self.defaultTTL = Math.max(DEFAULT_TTL, self.minimumTTL);
    self.domainTTLLoaded = true;
    if (!self.createDialog) {
      // CrudList.created() snapshots the defaults before this request completes.
      self.createDialogItem = Object.assign({}, self.itemDefaults());
    }
  },
};
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
    ::v-deep tr:not(.v-data-table__empty-wrapper) td {
        vertical-align: top;
    }
    ::v-deep tr.successFade > td {
        animation: successFade 1s;
    }
    ::v-deep tr.successFade:focus-within > td {
        animation: none;
    }
    @keyframes successFade {
        from { background-color: forestgreen; }
    }
    ::v-deep tr:focus-within .button-save .v-icon {
        color: forestgreen;
    }
    ::v-deep tr:focus-within :focus {
        background-color: #FFFFFF;
    }
</style>
