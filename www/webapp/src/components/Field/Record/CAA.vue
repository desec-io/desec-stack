<script>
import { integer, between } from 'vuelidate/lib/validators';
import Record from '../Record.vue';

const MAX8 = 255;
const int8 = between(0, MAX8);

// https://www.iana.org/assignments/pkix-parameters/pkix-parameters.xhtml#caa-properties
const tags = ['issue', 'issuewild', 'iodef', 'contactemail', 'contactphone'];
const tag = (value) => !value || tags.some(v => value == v);

export default {
  name: 'RecordCAA',
  extends: Record,
  data: () => ({
    fields: [
      { label: 'Flags', validations: { integer, int8 } },
      { label: 'Tag', validations: { tag } },
      { label: 'Value', validations: { } },
    ],
    errors: {
      integer: 'Please enter an integer.',
      int8: `0 ≤ … ≤ ${MAX8}`,
      tag: 'Not a valid tag.',
    },
  }),
};
</script>
