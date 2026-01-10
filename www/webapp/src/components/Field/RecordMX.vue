<script>
import { helpers, integer, between } from '@vuelidate/validators';
import RecordItem from './RecordItem.vue';

const hostnameRegex = /^((([a-zA-Z0-9-]+\.?)+)|\.)$/;
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
  name: 'RecordMX',
  extends: RecordItem,
  setup: RecordItem.setup,
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
