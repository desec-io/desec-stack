<script>
import { helpers } from 'vuelidate/lib/validators';
import Record from '../Record.vue';

const hostname = helpers.regex('hostname', /^((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z0-9_-]+\.)+[a-zA-Z]{2,}))[.]?$/);
const trailingDot = helpers.regex('trailingDot', /[.]$/);

export default {
  name: 'RecordCNAME',
  extends: Record,
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
