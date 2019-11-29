<script>
  import GenericActionHandler from "./GenericActionHandler"

  export default {
    name: 'ActivateAccountActionHandler',
    extends: GenericActionHandler,
    data: () => ({
      auto_submit: true,
    }),
    watch: {
      success(value) {
        if(value) {
          let domain = this.response.data.domain
          if(domain !== undefined) {
            let token = this.response.data.token
            this.$router.push({ name: 'dynsetup', params: { domain: domain.name }, hash: `#${token}` })
          }
        }
      }
    }
  };
</script>
