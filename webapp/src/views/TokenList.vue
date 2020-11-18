<script>
import CrudList from './CrudList';
import store from '../store';

export default {
  name: 'CrudTokenList',
  extends: CrudList,
  data() {
    return {
        createable: true,
        updatable: true,
        destroyable: true,
        headlines: {
          table: 'Tokens',
          create: 'Generate New Token',
          destroy: 'Delete Token',
        },
        texts: {
          banner: () => ('<strong>New feature:</strong> You can now configure your tokens for finer access control. Check out the new settings below!'),
          create: () => ('<p>You can create a new API token here. The token is displayed after submitting this form.</p><p><strong>Warning:</strong> Be sure to protect your tokens appropriately! Knowledge of an API token allows performing actions on your behalf.</p>'),
          createSuccess: (item) => `Your new token is: <code>${item.token}</code><br />It is only displayed once.`,
          destroy: d => (d.name ? `Delete token with name "${d.name}" and ID ${d.id}?` : `Delete unnamed token with ID ${d.id}?`),
          destroyInfo: () => ('This operation is permanent. Any devices using this token will no longer be able to authenticate.'),
          destroyWarning: d => (d.id == store.state.token.id ? 'This is your current session token. Deleting it will invalidate the session.' : ''),
        },
        columns: {
          id: {
            name: 'item.id',
            text: 'Identifier',
            align: 'left',
            value: 'id',
            readonly: true,
            datatype: 'GenericText',
            searchable: true,
          },
          name: {
            name: 'item.name',
            text: 'Name',
            textCreate: 'Token name (for your convenience only)',
            align: 'left',
            sortable: true,
            value: 'name',
            readonly: false,
            writeOnCreate: true,
            datatype: 'GenericText',
            searchable: true,
          },
          allowed_subnets: {
            name: 'item.allowed_subnets',
            text: 'Client subnets',
            textCreate: 'Allowed client subnets',
            align: 'left',
            sortable: true,
            value: 'allowed_subnets',
            readonly: false,
            required: false,
            writeOnCreate: true,
            datatype: 'RecordList',
            fieldProps: () => ({ type: 'Subnet' }),
            searchable: true,
          },
          perm_manage_tokens: {
            name: 'item.perm_manage_tokens',
            text: 'Can manage tokens',
            textCreate: 'Can manage tokens?',
            align: 'left',
            sortable: true,
            value: 'perm_manage_tokens',
            readonly: false,
            writeOnCreate: true,
            datatype: 'Switchbox',
            searchable: false,
          },
          max_age: {
            name: 'item.max_age',
            text: 'Maximum age',
            align: 'left',
            sortable: true,
            value: 'max_age',
            readonly: false,
            writeOnCreate: true,
            datatype: 'GenericText',
            searchable: false,
            fieldProps: () => ({ hint: 'Format: [DD] [HH:[MM:]]ss' }),
          },
          max_unused_period: {
            name: 'item.max_unused_period',
            text: 'Maximum unused period',
            align: 'left',
            sortable: true,
            value: 'max_unused_period',
            readonly: false,
            writeOnCreate: true,
            datatype: 'GenericText',
            searchable: false,
            fieldProps: () => ({ hint: 'Format: [DD] [HH:[MM:]]ss' }),
          },
          is_valid: {
            name: 'item.is_valid',
            text: 'Valid',
            align: 'left',
            sortable: true,
            value: 'is_valid',
            readonly: true,
            datatype: 'Checkbox',
            searchable: false,
          },
          created: {
            name: 'item.created',
            text: 'Created',
            align: 'left',
            sortable: true,
            value: 'created',
            readonly: true,
            datatype: 'TimeAgo',
            searchable: false,
          },
          last_used: {
            name: 'item.last_used',
            text: 'Last used',
            align: 'left',
            sortable: true,
            value: 'last_used',
            readonly: true,
            datatype: 'TimeAgo',
            searchable: false,
          },
        },
        paths: {
          list: 'auth/tokens/',
          create: 'auth/tokens/',
          delete: 'auth/tokens/:{id}/',
          update: 'auth/tokens/:{id}/',
        },
        itemDefaults: () => ({
          name: '', allowed_subnets: [''], 'perm_manage_tokens': false,
        }),
        itemIsReadOnly: (item) => item.id == store.state.token.id,
        postcreate: () => false,  // do not close dialog
        precreate() {
          this.createDialogItem.allowed_subnets = this.createDialogItem.allowed_subnets.filter(subnet => subnet.length);
          if (this.createDialogItem.allowed_subnets.length == 0) {
            delete this.createDialogItem.allowed_subnets;
          }
        },
    }
  },
};
</script>

<style scoped>
    >>> td {
        vertical-align: top;
    }
</style>
