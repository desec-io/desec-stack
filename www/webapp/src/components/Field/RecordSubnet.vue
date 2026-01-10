<script>
import { ipAddressOrSubnet } from './ipAddressValidators';
import RecordItem from './RecordItem.vue';

export default {
  name: 'RecordSubnet',
  extends: RecordItem,
  setup: RecordItem.setup,
  data: () => ({
    errors: {
      ipAddressOrSubnet: 'This field must contain an IP address or subnet.'
    },
    fields: [
      { label: 'Subnet (IPv4 / IPv6)', validations: { ipAddressOrSubnet } },
    ],
  }),
};
</script>
