<script>
import Record from './Record'
import { ipAddress } from 'vuelidate/lib/validators'

export default {
  name: 'RecordA',
  extends: Record,
  data: () => ({
    messagePool: {
      ipAddress: 'This field must contain an IPv4 address.'
    }
  }),
  validations: {
    value: { ipAddress }
  }
}
</script>
