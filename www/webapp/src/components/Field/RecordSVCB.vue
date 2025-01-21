<script>
import { helpers, integer, between } from 'vuelidate/lib/validators';
import RecordItem from './RecordItem.vue';

// Allow for root label only
const hostname = helpers.regex('hostname', /^(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,})?[.]?$/);
const trailingDot = helpers.regex('trailingDot', /[.]$/);

const MAX16 = 65535;
const int16 = between(0, MAX16);

export default {
  name: 'RecordSVCB',
  extends: RecordItem,
  data: () => ({
    fields: [
      { label: 'Priority', validations: { integer, int16 } },
      { label: 'Target Name', validations: { hostname, trailingDot } },
      { label: 'Service Parameters', validations: { }, optional: true },
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
