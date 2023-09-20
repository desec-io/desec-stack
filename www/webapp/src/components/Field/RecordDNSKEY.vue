<script>
import { helpers, integer, between } from 'vuelidate/lib/validators';
import RecordItem from './RecordItem.vue';

const base64 = helpers.regex('base64', /^[0-9a-zA-Z+/][0-9a-zA-Z+/\s]*(=\s*){0,3}$/);

const MAX8 = 255;
const int8 = between(0, MAX8);

const MAX16 = 65535;
const int16 = between(0, MAX16);

const equals3 = (value) => !value || value == 3;

const dnskey_flag_mnemonics = {
  256: 'ZSK',
  257: 'KSK',
}

export const dnskey_algorithm_mnemonics = {
  8: 'RSASHA256',
  13: 'ECDSAP256-SHA256',
  14: 'ECDSAP384-SHA384',
  15: 'ED25519',
  16: 'ED448',
}

export default {
  name: 'RecordDNSKEY',
  extends: RecordItem,
  data: () => ({
    fields: [
      { label: 'Flags', validations: { integer, int16 }, mnemonics: dnskey_flag_mnemonics },
      { label: 'Protocol', validations: { integer, equals3 } },
      { label: 'Algorithm', validations: { integer, int8 }, mnemonics: dnskey_algorithm_mnemonics },
      { label: 'Public Key', validations: { base64 } },
    ],
    errors: {
      integer: 'Please enter an integer.',
      int8: `0 ≤ … ≤ ${MAX8}`,
      int16: `0 ≤ … ≤ ${MAX16}`,
      equals3: 'Must be 3.',
      base64: 'Please use base64 encoding.',
    },
  }),
};
</script>
