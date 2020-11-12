<script>
import { helpers, integer, between } from 'vuelidate/lib/validators';
import Record from '../Record.vue';

const hostname = helpers.regex('hostname', /^((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))[.]?$/);
const trailingDot = helpers.regex('trailingDot', /[.]$/);

const MAX16 = 65535;
const int16 = between(0, MAX16);

export default {
  name: 'RecordSRV',
  extends: Record,
  data: () => ({
    fields: [
      { label: 'Priority', validations: { integer, int16 } },
      { label: 'Weight', validations: { integer, int16 } },
      { label: 'Port', validations: { integer, int16 } },
      { label: 'Target', validations: { hostname, trailingDot } },
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
