<script>
import { ip6Address } from './ipAddressValidators';
import RecordItem from './RecordItem.vue';

export default {
  name: 'RecordAAAA',
  extends: RecordItem,
  setup: RecordItem.setup,
  data: () => ({
    errors: {
      ip6Address: 'This field must contain an IPv6 address.',
    },
    fields: [
      { label: 'IPv6 address', validations: { ip6Address } },
    ],
  }),
};
</script>
