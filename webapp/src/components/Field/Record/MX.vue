<script>
import { helpers, integer, between } from 'vuelidate/lib/validators';
import Record from '../Record.vue';

const hostname = helpers.regex('hostname', /^(([a-zA-Z0-9-]+\.?)+)|\.$/);
const trailingDot = helpers.regex('trailingDot', /[.]$/);

const MAX16 = 65535;
const int16 = between(0, MAX16);

export default {
  name: 'RecordMX',
  extends: Record,
  data: () => ({
    fields: [
      {
        label: 'Preference',
        validations: { integer, int16 },
      },
      {
        label: 'Hostname',
        validations: { hostname, trailingDot },
      },
    ],
    errors: {
      integer: 'Please enter an integer.',
      int16: `0 ≤ … ≤ ${MAX16}`,
      hostname: 'Please enter a valid hostname.',
      trailingDot: 'Hostname must end with a dot.',
    },
  }),
};
</script>
