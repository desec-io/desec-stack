<script>
import { ipAddress } from 'vuelidate/lib/validators';
import RecordItem from '../RecordItem.vue';

export default {
  name: 'RecordA',
  extends: RecordItem,
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
