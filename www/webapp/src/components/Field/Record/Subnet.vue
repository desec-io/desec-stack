<script>
import { helpers, or } from 'vuelidate/lib/validators';
import Record from '../Record.vue';

// from https://www.oreilly.com/library/view/regular-expressions-cookbook/9781449327453/ch08s16.html, adding subnet
const ip4AddressOrSubnet = helpers.regex('ip4Address', /^(?:(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])(\/(3[0-2]|[12]?[0-9]))?$/);

// from https://stackoverflow.com/a/17871737/6867099, without the '%' and '.' parts, adding subnet
const ip6AddressOrSubnet = helpers.regex('ip6Address', /^(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:))([/](12[0-8]|1[01][0-9]|[1-9]?[0-9]))?$/);

const ipAddressOrSubnet = or(ip4AddressOrSubnet, ip6AddressOrSubnet);

export default {
  name: 'RecordSubnet',
  extends: Record,
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
