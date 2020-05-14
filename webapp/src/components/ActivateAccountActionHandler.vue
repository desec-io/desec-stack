<script>
  import GenericActionHandler from "./GenericActionHandler"

  export default {
    name: 'ActivateAccountActionHandler',
    extends: GenericActionHandler,
    data: () => ({
      auto_submit: true,
      LOCAL_PUBLIC_SUFFIXES: process.env.VUE_APP_LOCAL_PUBLIC_SUFFIXES.split(','),
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
