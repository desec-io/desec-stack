<script>
import { ip4Address } from './ipAddressValidators';
import RecordItem from './RecordItem.vue';

export default {
  name: 'RecordA',
  extends: RecordItem,
  setup: RecordItem.setup,
  data: () => ({
    errors: {
      ip4Address: 'This field must contain an IPv4 address.',
    },
    fields: [
      { label: 'IPv4 address', validations: { ip4Address } },
    ],
  }),
};
</script>
