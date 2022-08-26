module.exports = {
  configureWebpack: {
    devServer: {
      allowedHosts: 'all',
    },
  },
  chainWebpack: config => {
    config.module
      .rule('fonts')
      .set('parser', {
        dataUrlCondition: {
          maxSize: 0 // Disable inline font to improve FCP (first contentful paint).
        }
      });
  },
};
