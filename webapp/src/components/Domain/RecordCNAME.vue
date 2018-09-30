<script>
import Record from './Record'
import { helpers } from 'vuelidate/lib/validators'

const hostname = helpers.regex('hostname', /^((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))[.]?$/)
const trailingDot = helpers.regex('trailingDot', /[.]$/)

export default {
  name: 'RecordCNAME',
  extends: Record,
  data: () => ({
    messagePool: {
      hostname: 'Please enter a valid hostname.',
      trailingDot: 'Hostname must end with a dot.'
    }
  }),
  validations: {
    value: { hostname, trailingDot }
  }
}
</script>
