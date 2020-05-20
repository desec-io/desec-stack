module.exports = {
  configureWebpack: {
    devServer: {
      disableHostCheck: true,
      sockHost: 'desec.' + process.env.VUE_APP_DESECSTACK_DOMAIN,
      public: 'https://desec.' + process.env.VUE_APP_DESECSTACK_DOMAIN + '/',
    },
  },
  publicPath: '/',
};
