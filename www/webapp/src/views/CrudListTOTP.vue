<script>
import CrudList from './CrudList.vue';
import TOTPVerifyDialog from '@/views/Console/TOTPVerifyDialog.vue';
import GenericText from "@/components/Field/GenericText.vue";
import TimeAgo from "@/components/Field/TimeAgo.vue";

export default {
  name: 'CrudListTOTP',
  extends: CrudList,
  components: {
    TOTPVerifyDialog,
  },
  data() {
    return {
        creatable: true,
        updatable: false,
        destroyable: true,
        headlines: {
          table: 'TOTP Tokens',
          create: 'New TOTP Token',
          destroy: 'Key Deletion',
        },
        texts: {
          create: () => `Add a new TOTP token.`,
          destroy: factor => (`Delete TOTP token ${factor.name}?`),
          destroyInfo: () => 'This operation cannot be undone. If this is your last active token, 2FA will be disabled on your account.',
        },
        columns: {
          name: {
            name: 'item.name',
            text: 'Name',
            textCreate: 'Enter Name',
            align: 'left',
            sortable: true,
            value: 'name',
            readonly: true,
            required: true,
            writeOnCreate: true,
            datatype: GenericText.name,
            searchable: true,
          },
          created: {
            name: 'item.created',
            text: 'Created',
            align: 'left',
            sortable: true,
            value: 'created',
            readonly: true,
            datatype: TimeAgo.name,
            searchable: false,
          },
          last_used: {
            name: 'item.last_used',
            text: 'Last used',
            align: 'left',
            sortable: true,
            value: 'last_used',
            readonly: true,
            datatype: TimeAgo.name,
            searchable: false,
          },
        },
        paths: {
          list: 'auth/totp/',
          create: 'auth/totp/',
          delete: 'auth/totp/:{id}/',
        },
        itemDefaults: () => ({ name: '' }),
        postcreate: (res, req) => {
          this.close();
          this.showDetail(res, req);
        },
        async showDetail(res, req) {
          if (req === undefined) { // success
            this.extraComponentBind = {'name': res.name, 'data': res};
          } else {
            this.extraComponentBind = {'name': req.name, 'detail': res.data.detail};
          }
          this.extraComponentName = 'TOTPVerifyDialog';
        },
    }
  },
};
</script>
