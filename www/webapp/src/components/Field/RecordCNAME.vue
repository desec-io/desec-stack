<script>
import { helpers } from '@vuelidate/validators';
import RecordItem from './RecordItem.vue';

const domainRegex = /^(([a-zA-Z0-9_\\-]+\.)+[a-zA-Z]{2,})[.]?$/;
const trailingDotRegex = /[.]$/;
const domain = helpers.withParams(
  { type: 'domain' },
  value => !helpers.req(value) || domainRegex.test(String(value).trim()),
);
const trailingDot = helpers.withParams(
  { type: 'trailingDot' },
  value => !helpers.req(value) || trailingDotRegex.test(String(value).trim()),
);

export default {
  name: 'RecordCNAME',
  extends: RecordItem,
  setup: RecordItem.setup,
  data: () => ({
    errors: {
      domain: 'Please enter a valid domain name.',
      trailingDot: 'Domain name must end with a dot.',
    },
    fields: [
      { label: 'Target domain name', validations: { domain, trailingDot } },
    ],
  }),
};
</script>
