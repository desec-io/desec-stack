<script>
import Record from './Record'

export default {
  name: 'RecordNS',
  extends: Record,
  data: () => ({
    fields: [
      { name: 'value', value: '', validations: {} }
    ]
  })
}
</script>
