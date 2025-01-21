<script>
import { helpers } from 'vuelidate/lib/validators';
import RecordItem from './RecordItem.vue';

const hostname = helpers.regex('hostname', /^(([a-zA-Z0-9_-]+\.)+[a-zA-Z]{2,})[.]?$/);
const trailingDot = helpers.regex('trailingDot', /[.]$/);

export default {
  name: 'RecordCNAME',
  extends: RecordItem,
  data: () => ({
    errors: {
      hostname: 'Please enter a valid hostname.',
      trailingDot: 'Hostname must end with a dot.',
    },
    fields: [
      { label: 'Target hostname', validations: { hostname, trailingDot } },
    ],
  }),
};
</script>
