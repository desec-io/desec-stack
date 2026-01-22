<script>
import { helpers } from 'vuelidate/lib/validators';
import RecordItem from './RecordItem.vue';

const domain = helpers.regex('domain', /^(([a-zA-Z0-9_\\-]+\.)+[a-zA-Z0-9\\-]{2,})[.]?$/);
const trailingDot = helpers.regex('trailingDot', /[.]$/);

export default {
  name: 'RecordCNAME',
  extends: RecordItem,
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
