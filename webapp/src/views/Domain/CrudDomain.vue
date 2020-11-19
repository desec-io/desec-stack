<script>
import CrudList from '@/views/CrudList';
import {HTTP, withWorking} from "@/utils"

export default {
  name: 'CrudDomain',
  extends: CrudList,
  data: function () {
    const self = this;
    return {
      minimumTTL: 60,
      fullWidth: true,
      createable: true,
      updatable: true,
      destroyable: true,
      headlines: {
        table: `Record Sets ${self.$route.params.domain}`,
        create: `Create New Record Set (${self.$route.params.domain})`,
        destroy: 'Delete Record Set',
      },
      texts: {
        banner: () => 'You can edit your DNS records here. As this feature is evolving, we would like to gather your feedback. Feel free to post in <a href="https://talk.desec.io/" target="_blank">our forum</a>, or shoot us an email.',
        create: () => ('Create a record set'),
        destroy: rrset => (`Delete record set ${rrset.type} ${rrset.subname}?`),
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
          datatype: 'RRSetType',
          searchable: true,
          writeOnCreate: true,
          width: '130px',
        },
        subname: {
          name: 'item.subname',
          text: 'Subname',
          align: 'left',
          sortable: true,
          value: 'subname',
          readonly: true,
          datatype: 'GenericText',
          searchable: true,
          writeOnCreate: true,
          width: '200px',
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
          datatype: 'RecordList',
          fieldProps: rrSet => ({ type: rrSet.type || 'A' }),
          searchable: true,
        },
        ttl: {
          name: 'item.ttl',
          text: 'TTL (seconds)',
          align: 'left',
          sortable: true,
          value: 'ttl',
          readonly: false,
          required: true,
          datatype: 'TTL',
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
          datatype: 'TimeAgo',
          searchable: false,
          width: '130px',
        },
      },
      actions: [
      ],
      paths: {
        list: 'domains/::{domain}/rrsets/', // TODO dangerous?
        create: 'domains/::{domain}/rrsets/',
        delete: 'domains/::{domain}/rrsets/:{subname}.../:{type}/',
        update: 'domains/::{domain}/rrsets/:{subname}.../:{type}/',
      },
      itemDefaults: () => ({
        type: 'A', subname: '', records: [''], ttl: 3600,
      }),
    }
  },
  async created() {
    const self = this;
    const url = self.resourcePath('domains/::{domain}/', self.$route.params, '::');
    await withWorking(this.error, () => HTTP
        .get(url)
        .then(r => self.minimumTTL = r.data['minimum_ttl'])
    );
  },
};
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
    >>> td {
        vertical-align: top;
    }
    >>> .v-data-table .v-data-table__mobile-row {
        height: auto;
        margin: -11px 0;
    }
    >>> .theme--light.v-data-table > .v-data-table__wrapper > table > tbody > tr:not(:last-child).v-data-table__mobile-table-row > td:last-child {
        border-bottom-width: 4px;
    }

    >>> tr.successFade td {
        animation: successFade 1s;
    }
    >>> tr.successFade:focus-within td {
        animation: none;
    }
    @keyframes successFade {
        from { background-color: forestgreen; }
    }
    >>> tr:focus-within .mdi-content-save-edit {
        color: forestgreen;
    }
    >>> tr:focus-within :focus {
        background-color: #FFFFFF;
    }
</style>
