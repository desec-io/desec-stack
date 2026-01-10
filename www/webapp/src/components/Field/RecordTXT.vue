<script>
import { helpers } from '@vuelidate/validators';
import RecordItem from './RecordItem.vue';

const txtToken = helpers.withMessage(
  'TXT records must either be fully quoted or contain no quotes.',
  value => !helpers.req(value) || /^".*"$/.test(value) || !value.includes('"'),
);

export default {
  name: 'RecordTXT',
  extends: RecordItem,
  setup: RecordItem.setup,
  data: () => ({
    errors: {
      txtToken: 'TXT records must either be fully quoted or contain no quotes.',
    },
    fields: [
      { label: 'Content', validations: { txtToken } },
    ],
  }),
};
</script>
