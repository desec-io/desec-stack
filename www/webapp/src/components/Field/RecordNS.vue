<script>
import { helpers } from 'vuelidate/lib/validators';
import RecordItem from './RecordItem.vue';

const hostname = helpers.regex('hostname', /^((([a-zA-Z0-9-]+\.?)+)|\.)$/);
const trailingDot = helpers.regex('trailingDot', /[.]$/);

export default {
  name: 'RecordNS',
  extends: RecordItem,
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
