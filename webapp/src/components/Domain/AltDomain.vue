<script>
import CrudList from '@/components/CrudList'

export default {
  name: 'AltDomain',
  extends: CrudList,
  data: () => ({
    createable: true,
    updateable: false,
    destroyable: true,
    headlines: {
      table: 'Record Sets',
      create: 'Create New Record Set',
      destroy: 'Delete Record Set'
    },
    texts: {
      create: () => ('Create a record set'),
      destroy: (rrset) => ('Delete record set ' + rrset.type + ' ' + rrset.subname + '?'),
      destroyWarning: (d) => ('This operation will permanently remove this information from the DNS.')
    },
    columns: {
      type: {
        text: 'Type',
        textCreate: 'Record Set Type',
        align: 'left',
        sortable: true,
        value: 'type',
        readonly: false,
        datatype: 'RRSetTypeField',
        searchable: true
      },
      subname: {
        text: 'Subname',
        align: 'left',
        sortable: true,
        value: 'subname',
        readonly: true,
        datatype: 'TextField',
        searchable: true
      },
      records: {
        text: 'Content',
        textCreate: 'Record Set Content',
        align: 'left',
        sortable: true,
        value: 'records',
        readonly: false,
        datatype: (rrset) => (rrset.type === undefined || rrset.type === '' ? 'RRSetAField' : 'RRSet' + rrset.type + 'Field'),
        searchable: true
      },
      ttl: {
        text: 'TTL',
        align: 'right',
        sortable: true,
        value: 'ttl',
        readonly: false,
        datatype: 'TextField',
        searchable: true
      }
    },
    actions: [
    ],
    paths: {
      'list': 'domains/::name/rrsets/', // TODO dangerous?
      'create': 'domains/::name/rrsets/',
      'delete': 'domains/::name/rrsets/:subname.../:type/'
    },
    defaultObject: { type: 'A', subname: '', records: '[]', ttl: 60 * 60 * 24 * 7 }
  })
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>

</style>
