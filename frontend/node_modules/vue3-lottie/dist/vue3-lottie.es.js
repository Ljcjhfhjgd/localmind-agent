(function(){"use strict";try{if(typeof document!="undefined"){var t=document.createElement("style");t.appendChild(document.createTextNode(".lottie-animation-container{width:var(--lottie-animation-container-width);height:var(--lottie-animation-container-height);background-color:var(--lottie-animation-container-background-color);overflow:hidden;margin:var(--lottie-animation-margin)}.lottie-animation-container svg{transform:scale(var(--lottie-animation-scale))}")),document.head.appendChild(t)}}catch(n){console.error("vite-plugin-css-injected-by-js",n)}})();
var __defProp = Object.defineProperty;
var __defProps = Object.defineProperties;
var __getOwnPropDescs = Object.getOwnPropertyDescriptors;
var __getOwnPropSymbols = Object.getOwnPropertySymbols;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __propIsEnum = Object.prototype.propertyIsEnumerable;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __spreadValues = (a, b) => {
  for (var prop in b || (b = {}))
    if (__hasOwnProp.call(b, prop))
      __defNormalProp(a, prop, b[prop]);
  if (__getOwnPropSymbols)
    for (var prop of __getOwnPropSymbols(b)) {
      if (__propIsEnum.call(b, prop))
        __defNormalProp(a, prop, b[prop]);
    }
  return a;
};
var __spreadProps = (a, b) => __defProps(a, __getOwnPropDescs(b));
import { defineComponent, ref, watchEffect, computed, watch, openBlock, createElementBlock, normalizeStyle } from "vue";
import Lottie from "lottie-web";
var es6 = function equal(a, b) {
  if (a === b)
    return true;
  if (a && b && typeof a == "object" && typeof b == "object") {
    if (a.constructor !== b.constructor)
      return false;
    var length, i, keys;
    if (Array.isArray(a)) {
      length = a.length;
      if (length != b.length)
        return false;
      for (i = length; i-- !== 0; )
        if (!equal(a[i], b[i]))
          return false;
      return true;
    }
    if (a instanceof Map && b instanceof Map) {
      if (a.size !== b.size)
        return false;
      for (i of a.entries())
        if (!b.has(i[0]))
          return false;
      for (i of a.entries())
        if (!equal(i[1], b.get(i[0])))
          return false;
      return true;
    }
    if (a instanceof Set && b instanceof Set) {
      if (a.size !== b.size)
        return false;
      for (i of a.entries())
        if (!b.has(i[0]))
          return false;
      return true;
    }
    if (ArrayBuffer.isView(a) && ArrayBuffer.isView(b)) {
      length = a.length;
      if (length != b.length)
        return false;
      for (i = length; i-- !== 0; )
        if (a[i] !== b[i])
          return false;
      return true;
    }
    if (a.constructor === RegExp)
      return a.source === b.source && a.flags === b.flags;
    if (a.valueOf !== Object.prototype.valueOf)
      return a.valueOf() === b.valueOf();
    if (a.toString !== Object.prototype.toString)
      return a.toString() === b.toString();
    keys = Object.keys(a);
    length = keys.length;
    if (length !== Object.keys(b).length)
      return false;
    for (i = length; i-- !== 0; )
      if (!Object.prototype.hasOwnProperty.call(b, keys[i]))
        return false;
    for (i = length; i-- !== 0; ) {
      var key = keys[i];
      if (!equal(a[key], b[key]))
        return false;
    }
    return true;
  }
  return a !== a && b !== b;
};
function klona(val) {
  var k, out, tmp;
  if (Array.isArray(val)) {
    out = Array(k = val.length);
    while (k--)
      out[k] = (tmp = val[k]) && typeof tmp === "object" ? klona(tmp) : tmp;
    return out;
  }
  if (Object.prototype.toString.call(val) === "[object Object]") {
    out = {};
    for (k in val) {
      if (k === "__proto__") {
        Object.defineProperty(out, k, {
          value: klona(val[k]),
          configurable: true,
          enumerable: true,
          writable: true
        });
      } else {
        out[k] = (tmp = val[k]) && typeof tmp === "object" ? klona(tmp) : tmp;
      }
    }
    return out;
  }
  return val;
}
var vue3Lottie_vue_vue_type_style_index_0_lang = "";
var _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};
const _sfc_main = defineComponent({
  props: {
    animationData: {
      type: Object,
      default: () => ({})
    },
    animationLink: {
      type: String,
      default: ""
    },
    loop: {
      type: [Boolean, Number],
      default: true
    },
    autoPlay: {
      type: Boolean,
      default: true
    },
    width: {
      type: [Number, String],
      default: "100%"
    },
    height: {
      type: [Number, String],
      default: "100%"
    },
    speed: {
      type: Number,
      default: 1
    },
    delay: {
      type: Number,
      default: 0
    },
    direction: {
      type: String,
      default: "forward"
    },
    pauseOnHover: {
      type: Boolean,
      default: false
    },
    playOnHover: {
      type: Boolean,
      default: false
    },
    backgroundColor: {
      type: String,
      default: "transparent"
    },
    pauseAnimation: {
      type: Boolean,
      default: false
    },
    noMargin: {
      type: Boolean,
      default: false
    },
    scale: {
      type: Number,
      default: 1
    },
    renderer: {
      type: String,
      default: "svg"
    },
    rendererSettings: {
      type: Object,
      default: () => ({})
    },
    assetsPath: {
      type: String,
      default: ""
    }
  },
  emits: {
    onComplete: null,
    onLoopComplete: null,
    onEnterFrame: null,
    onSegmentStart: null,
    onAnimationLoaded: null
  },
  setup(props, { emit: emits }) {
    const lottieAnimationContainer = ref();
    let animationData;
    let lottieAnimation = null;
    let direction = 1;
    watchEffect(async () => {
      if (!lottieAnimationContainer.value)
        return;
      if (props.animationLink != "") {
        try {
          const response = await fetch(props.animationLink);
          const responseJSON = await response.json();
          animationData = responseJSON;
        } catch (error) {
          console.error(error);
          return;
        }
      } else if (es6(props.animationData, {}) === false) {
        animationData = klona(props.animationData);
      } else {
        throw new Error("You must provide either animationLink or animationData");
      }
      loadLottie();
    });
    const loadLottie = () => {
      if (!lottieAnimationContainer.value)
        return;
      if (!animationData)
        return;
      lottieAnimation == null ? void 0 : lottieAnimation.destroy();
      lottieAnimation = null;
      let autoPlay = props.autoPlay;
      let loop = props.loop;
      if (props.playOnHover) {
        autoPlay = false;
      }
      if (typeof loop === "number") {
        if (loop > 0) {
          loop = loop - 1;
        }
      }
      if (props.delay > 0) {
        autoPlay = false;
      }
      const lottieAnimationConfig = {
        container: lottieAnimationContainer.value,
        renderer: props.renderer,
        loop,
        autoplay: autoPlay,
        animationData,
        assetsPath: props.assetsPath
      };
      if (es6(props.rendererSettings, {}) === false) {
        lottieAnimationConfig.rendererSettings = props.rendererSettings;
      }
      if (props.scale !== 1) {
        lottieAnimationConfig.rendererSettings = __spreadProps(__spreadValues({}, lottieAnimationConfig.rendererSettings), {
          viewBoxOnly: true
        });
      }
      lottieAnimation = Lottie.loadAnimation(lottieAnimationConfig);
      setTimeout(() => {
        autoPlay = props.autoPlay;
        if (props.playOnHover) {
          lottieAnimation == null ? void 0 : lottieAnimation.pause();
        } else {
          if (autoPlay) {
            lottieAnimation == null ? void 0 : lottieAnimation.play();
          } else {
            lottieAnimation == null ? void 0 : lottieAnimation.pause();
          }
        }
        emits("onAnimationLoaded");
      }, props.delay);
      lottieAnimation.setSpeed(props.speed);
      if (props.direction === "reverse") {
        lottieAnimation.setDirection(-1);
      }
      if (props.direction === "normal") {
        lottieAnimation.setDirection(1);
      }
      if (props.pauseAnimation) {
        lottieAnimation.pause();
      } else {
        if (props.playOnHover) {
          lottieAnimation.pause();
        }
      }
      lottieAnimation.addEventListener("loopComplete", () => {
        if (props.direction === "alternate") {
          lottieAnimation == null ? void 0 : lottieAnimation.stop();
          direction = direction === -1 ? 1 : -1;
          lottieAnimation == null ? void 0 : lottieAnimation.setDirection(direction);
          lottieAnimation == null ? void 0 : lottieAnimation.play();
        }
        emits("onLoopComplete");
      });
      lottieAnimation.addEventListener("complete", () => {
        emits("onComplete");
      });
      lottieAnimation.addEventListener("enterFrame", () => {
        emits("onEnterFrame");
      });
      lottieAnimation.addEventListener("segmentStart", () => {
        emits("onSegmentStart");
      });
    };
    const getCurrentStyle = computed(() => {
      let width = props.width;
      let height = props.height;
      if (typeof props.width === "number") {
        width = `${props.width}px`;
      }
      if (typeof props.height === "number") {
        height = `${props.height}px`;
      }
      let cssVariables = {
        "--lottie-animation-container-width": width,
        "--lottie-animation-container-height": height,
        "--lottie-animation-container-background-color": props.backgroundColor,
        "--lottie-animation-margin": props.noMargin ? "0" : "0 auto",
        "--lottie-animation-scale": props.scale != 1 ? props.scale : ""
      };
      return cssVariables;
    });
    const hoverStarted = () => {
      if (lottieAnimation && props.pauseOnHover) {
        lottieAnimation.pause();
      }
      if (lottieAnimation && props.playOnHover) {
        lottieAnimation.play();
      }
    };
    const hoverEnded = () => {
      if (lottieAnimation && props.pauseOnHover) {
        lottieAnimation.play();
      }
      if (lottieAnimation && props.playOnHover) {
        lottieAnimation.pause();
      }
    };
    watch(() => props.pauseAnimation, () => {
      if ((props.pauseOnHover || props.playOnHover) && props.pauseAnimation) {
        console.error("If you are using pauseAnimation prop for Vue3-Lottie, please remove the props pauseOnHover and playOnHover");
        return;
      }
      if (lottieAnimation) {
        if (props.pauseAnimation) {
          lottieAnimation.pause();
        } else {
          lottieAnimation.play();
        }
      }
    });
    const play = () => {
      if (lottieAnimation) {
        lottieAnimation.play();
      }
    };
    const pause = () => {
      if (lottieAnimation) {
        lottieAnimation.pause();
      }
    };
    const stop = () => {
      if (lottieAnimation) {
        lottieAnimation.stop();
      }
    };
    const destroy = () => {
      if (lottieAnimation) {
        lottieAnimation.destroy();
      }
    };
    const setSpeed = (speed = 1) => {
      if (speed <= 0) {
        throw new Error("Speed must be greater than 0");
      }
      if (lottieAnimation) {
        lottieAnimation.setSpeed(speed);
      }
    };
    const setDirection = (direction2) => {
      if (lottieAnimation) {
        if (direction2 === "forward") {
          lottieAnimation.setDirection(1);
        } else if (direction2 === "reverse") {
          lottieAnimation.setDirection(-1);
        }
      }
    };
    const goToAndStop = (frame, isFrame = true) => {
      if (lottieAnimation) {
        lottieAnimation.goToAndStop(frame, isFrame);
      }
    };
    const goToAndPlay = (frame, isFrame = true) => {
      if (lottieAnimation) {
        lottieAnimation.goToAndPlay(frame, isFrame);
      }
    };
    const playSegments = (segments, forceFlag = false) => {
      if (lottieAnimation) {
        lottieAnimation.playSegments(segments, forceFlag);
      }
    };
    const setSubFrame = (useSubFrame = true) => {
      if (lottieAnimation) {
        lottieAnimation.setSubframe(useSubFrame);
      }
    };
    const getDuration = (inFrames = true) => {
      if (lottieAnimation) {
        return lottieAnimation.getDuration(inFrames);
      }
    };
    const updateDocumentData = (documentData, index2 = 0) => {
      if (lottieAnimation) {
        lottieAnimation.renderer.elements[index2].updateDocumentData(documentData);
      }
    };
    return {
      lottieAnimationContainer,
      hoverEnded,
      hoverStarted,
      getCurrentStyle,
      play,
      pause,
      stop,
      destroy,
      setSpeed,
      setDirection,
      goToAndStop,
      goToAndPlay,
      playSegments,
      setSubFrame,
      getDuration,
      updateDocumentData
    };
  }
});
function _sfc_render(_ctx, _cache, $props, $setup, $data, $options) {
  return openBlock(), createElementBlock("div", {
    ref: "lottieAnimationContainer",
    class: "lottie-animation-container",
    style: normalizeStyle(_ctx.getCurrentStyle),
    onMouseenter: _cache[0] || (_cache[0] = (...args) => _ctx.hoverStarted && _ctx.hoverStarted(...args)),
    onMouseleave: _cache[1] || (_cache[1] = (...args) => _ctx.hoverEnded && _ctx.hoverEnded(...args))
  }, null, 36);
}
var Vue3Lottie = /* @__PURE__ */ _export_sfc(_sfc_main, [["render", _sfc_render]]);
var index = {
  install(app, options) {
    var _a;
    const name = (_a = options == null ? void 0 : options.name) != null ? _a : "Vue3Lottie";
    app.component(name, Vue3Lottie);
  }
};
export { Vue3Lottie, index as default };
