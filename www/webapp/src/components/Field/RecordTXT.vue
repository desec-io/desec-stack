<script>
import { helpers } from 'vuelidate/lib/validators';
import RecordItem from './RecordItem.vue';

const txtToken = helpers.regex('txtToken', /^".*"$/);

export default {
  name: 'RecordTXT',
  extends: RecordItem,
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
