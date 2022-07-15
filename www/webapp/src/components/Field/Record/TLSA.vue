<script>
import { and, helpers, integer, between } from 'vuelidate/lib/validators';
import Record from '../Record.vue';

const hex = helpers.regex('hex', /^([0-9a-fA-F]\s*)*[0-9a-fA-F]$/);
const trim = and(helpers.regex('trimBegin', /^[^\s]/), helpers.regex('trimEnd', /[^\s]$/));

const MAX8 = 255;
const int8 = between(0, MAX8);

export default {
  name: 'RecordTLSA',
  extends: Record,
  data: () => ({
    fields: [
      { label: 'Usage', validations: { integer, int8 } },
      { label: 'Selector', validations: { integer, int8 } },
      { label: 'Matching Type', validations: { integer, int8 } },
      { label: 'Certificate Data', validations: { trim, hex } },
    ],
    errors: {
      integer: 'Please enter an integer.',
      int8: `0 ≤ … ≤ ${MAX8}`,
      hex: 'Please use hexadecimal format.',
      trim: 'Only internal whitespace allowed.',
    },
  }),
};
</script>
