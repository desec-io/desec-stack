<script>
import Record from './Record'
import { ipAddress } from 'vuelidate/lib/validators'

export default {
  name: 'RecordA',
  extends: Record,
  data: () => ({
    errors: {
      ipAddress: 'This field must contain an IPv4 address.'
    },
    fields: [
      { name: 'value', value: '', validations: { ipAddress } }
    ]
  })
}
</script>
