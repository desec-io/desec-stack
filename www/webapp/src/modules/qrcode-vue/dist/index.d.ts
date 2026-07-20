import { ExtractPropTypes, PropType } from 'vue';
export type Level = 'L' | 'M' | 'Q' | 'H';
export type RenderAs = 'canvas' | 'svg';
export type GradientType = 'linear' | 'radial';
export type ImageSettings = {
    src: string;
    x?: number;
    y?: number;
    height?: number;
    width?: number;
    excavate?: boolean;
    borderRadius?: number;
    crossOrigin?: 'anonymous' | 'use-credentials' | '';
};
export declare const QrcodeSvg: import("vue").DefineComponent<ExtractPropTypes<{
    value: {
        type: StringConstructor;
        required: boolean;
        default: string;
    };
    size: {
        type: NumberConstructor;
        default: number;
    };
    level: {
        type: PropType<Level>;
        default: "L";
        validator: (l: any) => boolean;
    };
    background: {
        type: StringConstructor;
        default: string;
    };
    foreground: {
        type: StringConstructor;
        default: string;
    };
    margin: {
        type: NumberConstructor;
        default: number;
        validator: (m: any) => boolean;
    };
    imageSettings: {
        type: PropType<ImageSettings>;
        default: () => {};
    };
    gradient: {
        type: BooleanConstructor;
        default: boolean;
    };
    gradientType: {
        type: PropType<GradientType>;
        default: string;
        validator: (t: any) => boolean;
    };
    gradientStartColor: {
        type: StringConstructor;
        default: string;
    };
    gradientEndColor: {
        type: StringConstructor;
        default: string;
    };
    radius: {
        type: NumberConstructor;
        default: number;
        validator: (r: any) => boolean;
    };
    id: {
        type: StringConstructor;
        required: boolean;
    };
}>, () => import("vue").VNode<import("vue").RendererNode, import("vue").RendererElement, {
    [key: string]: any;
}>, {}, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {}, string, import("vue").PublicProps, Readonly<ExtractPropTypes<{
    value: {
        type: StringConstructor;
        required: boolean;
        default: string;
    };
    size: {
        type: NumberConstructor;
        default: number;
    };
    level: {
        type: PropType<Level>;
        default: "L";
        validator: (l: any) => boolean;
    };
    background: {
        type: StringConstructor;
        default: string;
    };
    foreground: {
        type: StringConstructor;
        default: string;
    };
    margin: {
        type: NumberConstructor;
        default: number;
        validator: (m: any) => boolean;
    };
    imageSettings: {
        type: PropType<ImageSettings>;
        default: () => {};
    };
    gradient: {
        type: BooleanConstructor;
        default: boolean;
    };
    gradientType: {
        type: PropType<GradientType>;
        default: string;
        validator: (t: any) => boolean;
    };
    gradientStartColor: {
        type: StringConstructor;
        default: string;
    };
    gradientEndColor: {
        type: StringConstructor;
        default: string;
    };
    radius: {
        type: NumberConstructor;
        default: number;
        validator: (r: any) => boolean;
    };
    id: {
        type: StringConstructor;
        required: boolean;
    };
}>> & Readonly<{}>, {
    value: string;
    size: number;
    level: Level;
    background: string;
    foreground: string;
    margin: number;
    imageSettings: ImageSettings;
    gradient: boolean;
    gradientType: GradientType;
    gradientStartColor: string;
    gradientEndColor: string;
    radius: number;
}, {}, {}, {}, string, import("vue").ComponentProvideOptions, true, {}, any>;
export declare const QrcodeCanvas: import("vue").DefineComponent<ExtractPropTypes<{
    value: {
        type: StringConstructor;
        required: boolean;
        default: string;
    };
    size: {
        type: NumberConstructor;
        default: number;
    };
    level: {
        type: PropType<Level>;
        default: "L";
        validator: (l: any) => boolean;
    };
    background: {
        type: StringConstructor;
        default: string;
    };
    foreground: {
        type: StringConstructor;
        default: string;
    };
    margin: {
        type: NumberConstructor;
        default: number;
        validator: (m: any) => boolean;
    };
    imageSettings: {
        type: PropType<ImageSettings>;
        default: () => {};
    };
    gradient: {
        type: BooleanConstructor;
        default: boolean;
    };
    gradientType: {
        type: PropType<GradientType>;
        default: string;
        validator: (t: any) => boolean;
    };
    gradientStartColor: {
        type: StringConstructor;
        default: string;
    };
    gradientEndColor: {
        type: StringConstructor;
        default: string;
    };
    radius: {
        type: NumberConstructor;
        default: number;
        validator: (r: any) => boolean;
    };
    id: {
        type: StringConstructor;
        required: boolean;
    };
}>, () => import("vue").VNode<import("vue").RendererNode, import("vue").RendererElement, {
    [key: string]: any;
}>, {}, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {}, string, import("vue").PublicProps, Readonly<ExtractPropTypes<{
    value: {
        type: StringConstructor;
        required: boolean;
        default: string;
    };
    size: {
        type: NumberConstructor;
        default: number;
    };
    level: {
        type: PropType<Level>;
        default: "L";
        validator: (l: any) => boolean;
    };
    background: {
        type: StringConstructor;
        default: string;
    };
    foreground: {
        type: StringConstructor;
        default: string;
    };
    margin: {
        type: NumberConstructor;
        default: number;
        validator: (m: any) => boolean;
    };
    imageSettings: {
        type: PropType<ImageSettings>;
        default: () => {};
    };
    gradient: {
        type: BooleanConstructor;
        default: boolean;
    };
    gradientType: {
        type: PropType<GradientType>;
        default: string;
        validator: (t: any) => boolean;
    };
    gradientStartColor: {
        type: StringConstructor;
        default: string;
    };
    gradientEndColor: {
        type: StringConstructor;
        default: string;
    };
    radius: {
        type: NumberConstructor;
        default: number;
        validator: (r: any) => boolean;
    };
    id: {
        type: StringConstructor;
        required: boolean;
    };
}>> & Readonly<{}>, {
    value: string;
    size: number;
    level: Level;
    background: string;
    foreground: string;
    margin: number;
    imageSettings: ImageSettings;
    gradient: boolean;
    gradientType: GradientType;
    gradientStartColor: string;
    gradientEndColor: string;
    radius: number;
}, {}, {}, {}, string, import("vue").ComponentProvideOptions, true, {}, any>;
declare const QrcodeVue: import("vue").DefineComponent<ExtractPropTypes<{
    renderAs: {
        type: PropType<RenderAs>;
        required: boolean;
        default: string;
        validator: (as: any) => boolean;
    };
    value: {
        type: StringConstructor;
        required: boolean;
        default: string;
    };
    size: {
        type: NumberConstructor;
        default: number;
    };
    level: {
        type: PropType<Level>;
        default: "L";
        validator: (l: any) => boolean;
    };
    background: {
        type: StringConstructor;
        default: string;
    };
    foreground: {
        type: StringConstructor;
        default: string;
    };
    margin: {
        type: NumberConstructor;
        default: number;
        validator: (m: any) => boolean;
    };
    imageSettings: {
        type: PropType<ImageSettings>;
        default: () => {};
    };
    gradient: {
        type: BooleanConstructor;
        default: boolean;
    };
    gradientType: {
        type: PropType<GradientType>;
        default: string;
        validator: (t: any) => boolean;
    };
    gradientStartColor: {
        type: StringConstructor;
        default: string;
    };
    gradientEndColor: {
        type: StringConstructor;
        default: string;
    };
    radius: {
        type: NumberConstructor;
        default: number;
        validator: (r: any) => boolean;
    };
    id: {
        type: StringConstructor;
        required: boolean;
    };
}>, () => import("vue").VNode<import("vue").RendererNode, import("vue").RendererElement, {
    [key: string]: any;
}>, {}, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {}, string, import("vue").PublicProps, Readonly<ExtractPropTypes<{
    renderAs: {
        type: PropType<RenderAs>;
        required: boolean;
        default: string;
        validator: (as: any) => boolean;
    };
    value: {
        type: StringConstructor;
        required: boolean;
        default: string;
    };
    size: {
        type: NumberConstructor;
        default: number;
    };
    level: {
        type: PropType<Level>;
        default: "L";
        validator: (l: any) => boolean;
    };
    background: {
        type: StringConstructor;
        default: string;
    };
    foreground: {
        type: StringConstructor;
        default: string;
    };
    margin: {
        type: NumberConstructor;
        default: number;
        validator: (m: any) => boolean;
    };
    imageSettings: {
        type: PropType<ImageSettings>;
        default: () => {};
    };
    gradient: {
        type: BooleanConstructor;
        default: boolean;
    };
    gradientType: {
        type: PropType<GradientType>;
        default: string;
        validator: (t: any) => boolean;
    };
    gradientStartColor: {
        type: StringConstructor;
        default: string;
    };
    gradientEndColor: {
        type: StringConstructor;
        default: string;
    };
    radius: {
        type: NumberConstructor;
        default: number;
        validator: (r: any) => boolean;
    };
    id: {
        type: StringConstructor;
        required: boolean;
    };
}>> & Readonly<{}>, {
    value: string;
    size: number;
    level: Level;
    background: string;
    foreground: string;
    margin: number;
    imageSettings: ImageSettings;
    gradient: boolean;
    gradientType: GradientType;
    gradientStartColor: string;
    gradientEndColor: string;
    radius: number;
    renderAs: RenderAs;
}, {}, {}, {}, string, import("vue").ComponentProvideOptions, true, {}, any>;
export default QrcodeVue;
