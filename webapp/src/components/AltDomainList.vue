<script>
import CrudList from '@/components/CrudList'

export default {
  name: 'AltDomainList',
  extends: CrudList,
  data: () => ({
    createable: true,
    updateable: false,
    destroyable: true,
    headlines: {
      table: 'Domains',
      create: 'Create New Domain',
      destroy: 'Domain Deletion'
    },
    texts: {
      create: () => ('You have TODO of 5 domains left. Upgrade now!'),
      destroy: (d) => ('Delete domain ' + d.name + '?'),
      destroyWarning: (d) => 'This operation will cause the domain to disappear from the DNS. It will no longer be reachable from the Internet.'
    },
    columns: {
      name: {
        text: 'Name',
        textCreate: 'Enter Domain Name',
        align: 'left',
        sortable: true,
        value: 'name',
        readonly: true,
        datatype: 'GenericText',
        searchable: true
      },
      published: {
        text: 'Published',
        align: 'left',
        sortable: true,
        value: 'published',
        readonly: true,
        datatype: 'TimeAgo',
        searchable: false
      }
    },
    actions: [
      {
        key: 'info',
        go: (d) => (alert(d.name)),
        icon: 'info'
      }
    ],
    paths: {
      'list': 'domains/',
      'create': 'domains/',
      'delete': 'domains/:name/'
    },
    defaultObject: { name: '' },
    postcreate: (d) => (alert('postcreate ' + d.name)),
    rowclick: function (domain) { this.$router.push({name: 'AltDomain', params: { name: domain.name }}) }
  })
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>

</style>
