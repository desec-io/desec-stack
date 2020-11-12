<script>
import Record from '../Record.vue';

export default {
  name: 'RecordNS',
  extends: Record,
  data: () => ({
    fields: [
      { label: 'Hostname', validations: {} },
    ],
  }),
};
</script>
