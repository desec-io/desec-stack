<script>
  import GenericActionHandler from "./GenericActionHandler"
  import {LOCAL_PUBLIC_SUFFIXES} from '../env';

  export default {
    name: 'ActivateAccountActionHandler',
    extends: GenericActionHandler,
    data: () => ({
      auto_submit: true,
      LOCAL_PUBLIC_SUFFIXES: LOCAL_PUBLIC_SUFFIXES,
    }),
    watch: {
      success(value) {
        if(value) {
          let domain = this.response.data.domain;
          if(domain === undefined) {
            return;
          }
          if(this.LOCAL_PUBLIC_SUFFIXES.some((suffix) => domain.name.endsWith('.' + suffix))) {
            let token = this.response.data.token;
            this.$router.push({ name: 'dynSetup', params: { domain: domain.name }, hash: `#${token}` });
          } else {
            this.$router.push({ name: 'customSetup', params: { domain: domain.name, keys: domain.keys } });
          }
        }
      }
    }
  };
</script>
