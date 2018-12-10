<script>
import CrudList from '@/components/CrudList'

export default {
  name: 'TokenList',
  extends: CrudList,
  data: () => ({
    headlines: {
      table: 'Account Access Tokens',
      create: 'New Access Token',
      destroy: 'Delete Access Token'
    },
    texts: {
      create: (t) => ('Create a new access token. It can be used to authorize any operations in your account.'),
      destroy: (t) => ('Revoke an access token. It will stop working immediately. Any device or user using it will no longer have access to your account.'),
      destroyWarning: () => (undefined)
    },
    columns: {
      created: {
        text: 'Created',
        align: 'left',
        sortable: true,
        value: 'created',
        readonly: true,
        datatype: 'TimeAgo',
        searchable: false
      },
      id: {
        text: 'Id',
        align: 'right',
        sortable: true,
        value: 'id',
        readonly: true,
        datatype: 'Code',
        searchable: true
      },
      name: {
        text: 'Name',
        textCreate: 'Name (optional)',
        align: 'left',
        sortable: true,
        value: 'name',
        readonly: false,
        datatype: 'GenericText',
        searchable: true
      },
      value: {
        text: 'Token',
        align: 'left',
        sortable: true,
        value: 'value',
        readonly: true,
        datatype: 'Code',
        searchable: true
      }
    },
    paths: {
      'list': 'tokens/',
      'create': 'tokens/',
      'delete': 'tokens/:id/'
    },
    defaultObject: { name: '' }
  })
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>

</style>
