<script>
import { helpers } from 'vuelidate/lib/validators';
import Record from '../Record.vue';

const txtToken = helpers.regex('txtToken', /^".*"$/);

export default {
  name: 'RecordTXT',
  extends: Record,
  data: () => ({
    errors: {
      txtToken: 'This record must begin and end with quotes (").',
    },
    fields: [
      { label: 'Content', validations: { txtToken } },
    ],
  }),
};
</script>
