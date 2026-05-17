<script>
import CrudList from './CrudList.vue';
import GenericText from '@/components/Field/GenericText.vue';
import GenericSwitchbox from '@/components/Field/GenericSwitchbox.vue';

export default {
  name: 'CrudListTokenPolicy',
  extends: CrudList,
  data() {
    const self = this;
    return {
      creatable: true,
      updatable: true,
      destroyable: true,
      headlines: {
        table: `Policies for token ${self.$route.query.name ? `${self.$route.query.name} (${self.$route.params.tokenId})` : self.$route.params.tokenId}`,
        create: 'Add Policy',
        destroy: 'Delete Policy',
      },
      texts: {
        banner: () => (
          'Policies restrict DNS write access for this token. A default policy (all fields empty) must exist before specific policies can be added. ' +
          '<a href="https://desec.readthedocs.io/en/latest/auth/tokens.html#token-scoping-policies" target="_blank">Documentation</a>'
        ),
        create: () => 'Add a policy. Leave domain, subname, and type empty to create the default (deny-all) policy.',
        destroy: p => {
          const domain = p.domain || 'any domain';
          const subname = p.subname || 'any subname';
          const type = p.type || 'any type';
          const write = p.perm_write ? 'write allowed' : 'write denied';
          return `Delete policy (${domain}, ${subname}, ${type}, ${write})?`;
        },
      },
      columns: {
        domain: {
          name: 'item.domain',
          text: 'Domain',
          align: 'left',
          sortable: true,
          value: 'domain',
          readonly: false,
          required: false,
          writeOnCreate: true,
          datatype: GenericText.name,
          searchable: true,
          fieldProps: () => ({ placeholder: '(any domain)' }),
        },
        subname: {
          name: 'item.subname',
          text: 'Subname',
          align: 'left',
          sortable: true,
          value: 'subname',
          readonly: false,
          required: false,
          writeOnCreate: true,
          datatype: GenericText.name,
          searchable: true,
          fieldProps: () => ({ placeholder: '(any subname)' }),
        },
        type: {
          name: 'item.type',
          text: 'Type',
          align: 'left',
          sortable: true,
          value: 'type',
          readonly: false,
          required: false,
          writeOnCreate: true,
          datatype: 'RRSetType',
          searchable: true,
          fieldProps: (item) => ({ value: item.type || '', hint: 'Leave empty to match any record type. You can also enter types not listed.' }),
        },
        perm_write: {
          name: 'item.perm_write',
          text: 'Write',
          align: 'left',
          sortable: true,
          value: 'perm_write',
          readonly: false,
          writeOnCreate: true,
          datatype: GenericSwitchbox.name,
          searchable: false,
        },
      },
      paths: {
        list: 'auth/tokens/::{tokenId}/policies/rrsets/',
        create: 'auth/tokens/::{tokenId}/policies/rrsets/',
        delete: 'auth/tokens/::{tokenId}/policies/rrsets/:{id}/',
        update: 'auth/tokens/::{tokenId}/policies/rrsets/:{id}/',
      },
      itemDefaults: () => ({ domain: '', subname: '', type: '', perm_write: false }),
      precreate() {
        this.createDialogItem.domain = this.createDialogItem.domain || null;
        this.createDialogItem.subname = this.createDialogItem.subname || null;
        this.createDialogItem.type = this.createDialogItem.type || null;
      },
      preupdate(item) {
        item.domain = item.domain || null;
        item.subname = item.subname || null;
        item.type = item.type || null;
      },
    };
  },
};
</script>
