<script>
import { helpers } from 'vuelidate/lib/validators';
import Record from '../Record.vue';

const base64 = helpers.regex('base64', /^[0-9a-zA-Z+/][0-9a-zA-Z+/\s]*(=\s*){0,3}$/);

export default {
  name: 'RecordOPENPGPKEY',
  extends: Record,
  data: () => ({
    fields: [
      { label: 'Public Key', validations: { base64 } },
    ],
    errors: {
      base64: 'Please use base64 encoding.',
    },
  }),
};
</script>
