<script>
import { helpers } from 'vuelidate/lib/validators';
import Record from '../Record.vue';

// from https://stackoverflow.com/a/17871737/6867099, without the '%' and '.' parts
const ip6Address = helpers.regex('ip6Address', /^(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:))$/);

export default {
  name: 'RecordAAAA',
  extends: Record,
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
