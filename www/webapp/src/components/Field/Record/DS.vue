<script>
import { and, helpers, integer, between } from 'vuelidate/lib/validators';
import Record from '../Record.vue';

const hex = helpers.regex('hex', /^([0-9a-fA-F]\s*)*[0-9a-fA-F]$/);
const trim = and(helpers.regex('trimBegin', /^[^\s]/), helpers.regex('trimEnd', /[^\s]$/));

const MAX8 = 255;
const int8 = between(0, MAX8);

const MAX16 = 65535;
const int16 = between(0, MAX16);

export default {
  name: 'RecordDS',
  extends: Record,
  data: () => ({
    fields: [
      { label: 'Key Tag', validations: { integer, int16 } },
      { label: 'Algorithm', validations: { integer, int8 } },
      { label: 'Digest Type', validations: { integer, int8 } },
      { label: 'Digest', validations: { trim, hex } },
    ],
    errors: {
      integer: 'Please enter an integer.',
      int8: `0 ≤ … ≤ ${MAX8}`,
      int16: `0 ≤ … ≤ ${MAX16}`,
      hex: 'Please use hexadecimal format.',
      trim: 'Only internal whitespace allowed.',
    },
  }),
};
</script>
