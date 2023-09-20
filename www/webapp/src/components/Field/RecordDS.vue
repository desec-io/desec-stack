<script>
import { and, helpers, integer, between } from 'vuelidate/lib/validators';
import RecordItem from './RecordItem.vue';
import { dnskey_algorithm_mnemonics } from './RecordDNSKEY.vue';

const hex = helpers.regex('hex', /^([0-9a-fA-F]\s*)*[0-9a-fA-F]$/);
const trim = and(helpers.regex('trimBegin', /^[^\s]/), helpers.regex('trimEnd', /[^\s]$/));

const MAX8 = 255;
const int8 = between(0, MAX8);

const MAX16 = 65535;
const int16 = between(0, MAX16);

const digest_types_mnemonics = {
  1: 'SHA-1',
  2: 'SHA-256',
  3: 'GOST',
  4: 'SHA-384',
}

export default {
  name: 'RecordDS',
  extends: RecordItem,
  data: () => ({
    fields: [
      { label: 'Key Tag', validations: { integer, int16 } },
      { label: 'Algorithm', validations: { integer, int8 }, mnemonics: dnskey_algorithm_mnemonics },
      { label: 'Digest Type', validations: { integer, int8 }, mnemonics: digest_types_mnemonics },
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
