<script>
import { helpers } from '@vuelidate/validators';
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

export default {
  name: 'RecordNS',
  extends: RecordItem,
  setup: RecordItem.setup,
  data: () => ({
    fields: [
      {
        label: 'Hostname',
        validations: { hostname, trailingDot },
      },
    ],
    errors: {
      hostname: 'Please enter a valid hostname.',
      trailingDot: 'Hostname must end with a dot.',
    },
  }),
};
</script>
