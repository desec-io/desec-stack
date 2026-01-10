<script>
import { h } from 'vue';
import LegacyQrcodeVue from '@/modules/qrcode.vue/dist/qrcode.vue.esm';

export default {
  name: 'QrcodeVue',
  ...LegacyQrcodeVue,
  render() {
    const {
      className,
      value,
      level,
      background,
      foreground,
      size,
      renderAs,
      numCells,
      fgPath,
    } = this;

    const containerProps = {
      class: className || undefined,
      value,
      level,
      background,
      foreground,
    };

    if (renderAs === 'svg') {
      return h('div', containerProps, [
        h(
          'svg',
          {
            height: size,
            width: size,
            shapeRendering: 'crispEdges',
            viewBox: `0 0 ${numCells} ${numCells}`,
            style: { width: `${size}px`, height: `${size}px` },
          },
          [
            h('path', {
              fill: background,
              d: `M0,0 h${numCells}v${numCells}H0z`,
            }),
            h('path', { fill: foreground, d: fgPath }),
          ],
        ),
      ]);
    }

    return h('div', containerProps, [
      h('canvas', {
        height: size,
        width: size,
        style: { width: `${size}px`, height: `${size}px` },
        ref: 'qrcode-vue',
      }),
    ]);
  },
};
</script>
