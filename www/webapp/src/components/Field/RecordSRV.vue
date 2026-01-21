<script>
import { helpers, integer, between } from '@vuelidate/validators';
import RecordItem from './RecordItem.vue';

// Allow for root label only, see RFC 2052
const hostnameRegex = /^(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,})?[.]?$/;
const trailingDotRegex = /[.]$/;
const hostname = helpers.withParams(
  { type: 'hostname' },
  value => !helpers.req(value) || hostnameRegex.test(String(value).trim()),
);
const trailingDot = helpers.withParams(
  { type: 'trailingDot' },
  value => !helpers.req(value) || trailingDotRegex.test(String(value).trim()),
);

const MAX16 = 65535;
const int16 = between(0, MAX16);

export default {
  name: 'RecordSRV',
  extends: RecordItem,
  setup: RecordItem.setup,
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
