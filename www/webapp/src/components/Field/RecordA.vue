<script>
import { ipAddress } from '@vuelidate/validators';
import RecordItem from './RecordItem.vue';

export default {
  name: 'RecordA',
  extends: RecordItem,
  setup: RecordItem.setup,
  data: () => ({
    errors: {
      ipAddress: 'This field must contain an IPv4 address.',
    },
    fields: [
      { label: 'IPv4 address', validations: { ipAddress } },
    ],
  }),
};
</script>
