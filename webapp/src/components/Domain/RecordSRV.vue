<script>
import Record from './Record'
import { helpers, integer, minValue } from 'vuelidate/lib/validators'

const hostname = helpers.regex('hostname', /^((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))[.]?$/)
const trailingDot = helpers.regex('trailingDot', /[.]$/)

export default {
  name: 'RecordSRV',
  extends: Record,
  data: () => ({
    fields: [
      { name: 'priority', value: '0', placeholder: 'Prio', validations: { integer, minValue: minValue(0) } },
      { name: 'weight', value: '0', placeholder: 'Weight', validations: { integer, minValue: minValue(0) } },
      { name: 'port', value: '0', placeholder: 'Port', validations: { integer, minValue: minValue(1) } },
      { name: 'target', value: '', placeholder: 'Target', validations: { hostname, trailingDot } }
    ],
    errors: {
      hostname: 'Please enter a valid hostname.',
      trailingDot: 'Hostname must end with a dot.'
    }
  })
}
</script>
