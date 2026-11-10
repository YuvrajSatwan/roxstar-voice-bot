/**
 * Speaking Orb — StarMaker Edition
 * 12,000 particles WebGL voice assistant face.
 * - Procedural 3D Simplex Curl Turbulence (Organic, non-repetitive motion)
 * - Syllable lit rings from bottom to top
 * - 3 Curated Styles: Astral Stardust (0), Plasma Core (1), Cyber Sonic (2)
 * - Particle-landed live captions with aria-live="polite"
 * - States: listening, thinking, searching, speaking, done
 * - Zero libraries, zero network dependencies.
 */

(function () {
  'use strict';

  if (typeof window === 'undefined' || customElements.get('speaking-orb')) {
    return;
  }

  const VERTEX_SHADER = `
    precision highp float;
    attribute vec3 aPosition;
    attribute vec3 aColor;
    attribute float aPhase;
    attribute vec3 aDrift;

    uniform mat4 uMatrix;
    uniform float uTime;
    uniform float uState;     // 0: idle, 1: listening, 2: thinking, 3: speaking
    uniform float uAudioLevel; // 0.0 - 1.0
    uniform float uPixelRatio;
    uniform float uStyle;     // 0: astral, 1: plasma, 2: sonic

    varying vec3 vColor;
    varying float vAlpha;

    // Simplex 3D procedural noise for organic, non-repetitive fluid eddies
    vec4 permute(vec4 x){return mod(((x*34.0)+1.0)*x, 289.0);}
    vec4 taylorInvSqrt(vec4 r){return 1.79284291400159 - 0.85373472095314 * r;}

    float snoise(vec3 v){
      const vec2 C = vec2(1.0/6.0, 1.0/3.0);
      const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);

      vec3 i  = floor(v + dot(v, C.yyy) );
      vec3 x0 = v - i + dot(i, C.xxx) ;

      vec3 g = step(x0.yzx, x0.xyz);
      vec3 l = 1.0 - g;
      vec3 i1 = min( g.xyz, l.zxy );
      vec3 i2 = max( g.xyz, l.zxy );

      vec3 x1 = x0 - i1 + 1.0 * C.xxx;
      vec3 x2 = x0 - i2 + 2.0 * C.xxx;
      vec3 x3 = x0 - 1.0 + 3.0 * C.xxx;

      i = mod(i, 289.0 );
      vec4 p = permute( permute( permute(
                 i.z + vec4(0.0, i1.z, i2.z, 1.0 ))
               + i.y + vec4(0.0, i1.y, i2.y, 1.0 ))
               + i.x + vec4(0.0, i1.x, i2.x, 1.0 ));

      float n_ = 0.142857142857;
      vec3  ns = n_ * D.wyz - D.xzx;

      vec4 j = p - 49.0 * floor(p * ns.z *ns.z);

      vec4 x_ = floor(j * ns.z);
      vec4 y_ = floor(j - 7.0 * x_ );

      vec4 x = x_ *ns.x + ns.yyyy;
      vec4 y = y_ *ns.x + ns.yyyy;
      vec4 h = 1.0 - abs(x) - abs(y);

      vec4 b0 = vec4( x.xy, y.xy );
      vec4 b1 = vec4( x.zw, y.zw );

      vec4 s0 = floor(b0)*2.0 + 1.0;
      vec4 s1 = floor(b1)*2.0 + 1.0;
      vec4 sh = -step(h, vec4(0.0));

      vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy ;
      vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww ;

      vec3 p0 = vec3(a0.xy,h.x);
      vec3 p1 = vec3(a0.zw,h.y);
      vec3 p2 = vec3(a1.zw,h.z);
      vec3 p3 = vec3(a1.xy,h.w);

      vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
      p0 *= norm.x;
      p1 *= norm.y;
      p2 *= norm.z;
      p3 *= norm.w;

      vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
      m = m * m;
      return 42.0 * dot( m*m, vec4( dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3) ) );
    }

    void main() {
      vec3 pos = aPosition;

      // 1. Procedural 3D Curl Fluid Turbulence
      vec3 noiseSample = pos * 1.5 + vec3(0.0, uTime * 0.2, uTime * 0.14) + aDrift * 0.35;
      float n1 = snoise(noiseSample);
      float n2 = snoise(noiseSample + vec3(14.2, 28.1, 7.3));
      float n3 = snoise(noiseSample + vec3(39.1, 11.4, 25.7));
      vec3 fluidDisp = vec3(n1, n2, n3) * 0.17;

      // Non-linear variable orbital rotation
      float spinSpeed = 0.32 + sin(uTime * 0.15) * 0.08;
      if (uState >= 1.5 && uState < 2.5) {
        spinSpeed = 1.45;
      }
      float angleY = uTime * spinSpeed;
      float cosY = cos(angleY);
      float sinY = sin(angleY);
      mat3 rotY = mat3(
        cosY, 0.0, sinY,
        0.0, 1.0, 0.0,
        -sinY, 0.0, cosY
      );

      float angleX = sin(uTime * 0.2 + aPhase * 1.5) * 0.14;
      float cosX = cos(angleX);
      float sinX = sin(angleX);
      mat3 rotX = mat3(
        1.0, 0.0, 0.0,
        0.0, cosX, -sinX,
        0.0, sinX, cosX
      );

      pos = rotX * (rotY * pos);
      pos += fluidDisp * (1.0 + uAudioLevel * 0.6);

      float swell = 1.0;
      float brightness = 1.0;
      vec3 dynamicColor = aColor;

      // StarMaker Color Tokens
      vec3 colorPink = vec3(1.0, 0.18, 0.58);   // #FF2E93 Hot Pink
      vec3 colorPurple = vec3(0.49, 0.23, 0.93); // #7C3AED Royal Purple
      vec3 colorCyan = vec3(0.02, 0.71, 0.83);   // #06B6D4 Electric Cyan

      // STYLE 0: Astral Stardust (Fluid non-repetitive stardust)
      if (uStyle < 0.5) {
        if (uState > 0.5 && uState < 1.5) {
          float soundRipple = sin(length(pos) * 5.5 - uTime * 6.0) * (uAudioLevel * 0.25);
          pos += normalize(pos) * soundRipple;
          swell = 1.0 + (uAudioLevel * 0.5) + sin(uTime * 3.2 + aPhase * 6.28) * 0.05;
          brightness = 1.0 + uAudioLevel * 1.1;
          dynamicColor = mix(dynamicColor, colorCyan, clamp(uAudioLevel * 1.3, 0.0, 0.8));
        } else if (uState >= 1.5 && uState < 2.5) {
          float spiral = sin(pos.y * 4.0 + uTime * 6.0) * 0.3;
          pos.x += -pos.z * spiral;
          pos.z += pos.x * spiral;
          swell = 0.93 + sin(uTime * 5.0) * 0.08;
          brightness = 1.3 + sin(uTime * 7.0 + aPhase * 3.14) * 0.45;
          dynamicColor = mix(colorPurple, colorPink, sin(uTime * 3.0 + pos.y * 3.0) * 0.5 + 0.5);
        } else if (uState >= 2.5) {
          swell = 1.04 + (uAudioLevel * 0.72);
          float ringWave = sin((pos.y * 3.2) - (uTime * 8.5) + aPhase * 0.5);
          float ringIntensity = smoothstep(0.45, 1.0, ringWave);
          swell += ringIntensity * 0.18;
          brightness = 1.1 + ringIntensity * 1.6 + uAudioLevel * 0.95;
          dynamicColor = mix(dynamicColor, colorPink, ringIntensity * 0.7);
        } else {
          swell = 1.0 + sin(uTime * 1.6 + aPhase * 2.5) * 0.045;
          brightness = 0.88 + sin(uTime * 2.2 + aPhase * 4.0) * 0.12;
        }
      }
      // STYLE 1: Bioluminescent Plasma Core
      else if (uStyle >= 0.5 && uStyle < 1.5) {
        float coreDist = length(pos);
        float solarFlare = sin(coreDist * 8.0 - uTime * 5.0 + n1 * 3.5) * (0.1 + uAudioLevel * 0.3);
        pos += normalize(pos) * solarFlare;
        swell = 0.96 + (uAudioLevel * 0.65) + sin(uTime * 2.0) * 0.05;
        brightness = 1.15 + (1.0 - clamp(coreDist * 0.8, 0.0, 1.0)) * 0.8 + uAudioLevel * 1.2;
        dynamicColor = mix(colorPink, colorPurple, clamp(coreDist * 0.9, 0.0, 1.0));
      }
      // STYLE 2: Cyber Sonic Wave
      else {
        float ringLat = abs(pos.y);
        float harmonicRing = sin(ringLat * 12.0 - uTime * 7.0) * (0.08 + uAudioLevel * 0.35);
        pos.x += pos.x * harmonicRing;
        pos.z += pos.z * harmonicRing;
        swell = 1.0 + (uAudioLevel * 0.55);
        brightness = 1.0 + harmonicRing * 2.0 + uAudioLevel * 1.0;
        dynamicColor = mix(colorCyan, colorPink, smoothstep(0.1, 0.6, ringLat));
      }

      pos *= swell;

      vec4 finalPos = uMatrix * vec4(pos, 1.0);
      gl_Position = finalPos;

      float pSize = (2.8 + brightness * 1.6) * uPixelRatio;
      gl_PointSize = clamp(pSize * (1.2 / (finalPos.w + 0.3)), 1.5, 9.0);

      vColor = dynamicColor * brightness;
      vAlpha = clamp(0.42 + brightness * 0.55, 0.3, 1.0);
    }
  `;

  const FRAGMENT_SHADER = `
    precision highp float;
    varying vec3 vColor;
    varying float vAlpha;

    void main() {
      vec2 coord = gl_PointCoord - vec2(0.5);
      float dist = length(coord);
      if (dist > 0.5) {
        discard;
      }

      float intensity = smoothstep(0.5, 0.05, dist);
      float core = smoothstep(0.2, 0.0, dist) * 0.5;

      gl_FragColor = vec4(vColor + vec3(core), vAlpha * intensity);
    }
  `;

  class SpeakingOrbElement extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._state = 'listening';
      this._rest = 'listening';
      this._level = 0;
      this._styleMode = 'astral';
      this._caption = '';
      this._micStopFn = null;
      this._animId = 0;
      this._gl = null;
      this._program = null;
      this._startTime = performance.now();
      this._smoothedLevel = 0;
    }

    static get observedAttributes() {
      return ['state', 'level', 'caption', 'rest', 'style-mode'];
    }

    attributeChangedCallback(name, _oldVal, newVal) {
      if (name === 'state') this._state = newVal || 'listening';
      if (name === 'rest') this._rest = newVal || 'listening';
      if (name === 'level') this._level = parseFloat(newVal) || 0;
      if (name === 'style-mode') this._styleMode = newVal || 'astral';
      if (name === 'caption') {
        this._caption = newVal || '';
        this._updateCaption();
      }
    }

    get state() {
      return this._state;
    }

    set state(val) {
      this._state = val;
      this.setAttribute('state', val);
    }

    get rest() {
      return this._rest;
    }

    set rest(val) {
      this._rest = val;
      this.setAttribute('rest', val);
    }

    get level() {
      return this._level;
    }

    set level(val) {
      this._level = val;
      this.setAttribute('level', String(val));
    }

    get styleMode() {
      return this._styleMode;
    }

    set styleMode(val) {
      this._styleMode = val;
      this.setAttribute('style-mode', val);
    }

    connectedCallback() {
      this._initDOM();
      this._initWebGL();
    }

    disconnectedCallback() {
      if (this._animId) cancelAnimationFrame(this._animId);
      if (this._micStopFn) {
        this._micStopFn();
        this._micStopFn = null;
      }
    }

    async listen() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        const ctx = new AudioCtx();
        const src = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        src.connect(analyser);

        const data = new Uint8Array(analyser.frequencyBinCount);
        let active = true;

        const pollMic = () => {
          if (!active) return;
          analyser.getByteFrequencyData(data);
          let sum = 0;
          for (let i = 0; i < data.length; i++) sum += data[i];
          const avg = sum / data.length;
          this.level = Math.min(1.0, (avg / 128) * 1.4);
          requestAnimationFrame(pollMic);
        };
        requestAnimationFrame(pollMic);

        const stop = () => {
          active = false;
          stream.getTracks().forEach((t) => t.stop());
          try {
            ctx.close();
          } catch {}
        };
        this._micStopFn = stop;
        return stop;
      } catch (err) {
        console.warn('Microphone access denied:', err);
        return () => {};
      }
    }

    say(text, options) {
      this.state = 'speaking';
      this.setAttribute('caption', text);

      if (options && options.audio) {
        const audioEl = options.audio;
        try {
          const AudioCtx = window.AudioContext || window.webkitAudioContext;
          const ctx = new AudioCtx();
          const src = ctx.createMediaElementSource(audioEl);
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 256;
          src.connect(analyser);
          analyser.connect(ctx.destination);

          const data = new Uint8Array(analyser.frequencyBinCount);
          let active = true;

          const pollAudio = () => {
            if (!active) return;
            analyser.getByteFrequencyData(data);
            let sum = 0;
            for (let i = 0; i < data.length; i++) sum += data[i];
            this.level = Math.min(1.0, (sum / data.length / 128) * 1.5);
            requestAnimationFrame(pollAudio);
          };
          requestAnimationFrame(pollAudio);

          audioEl.addEventListener('ended', () => {
            active = false;
            this.state = this._rest;
            this.dispatchEvent(new CustomEvent('end'));
          }, { once: true });
        } catch {
          audioEl.addEventListener('ended', () => {
            this.state = this._rest;
            this.dispatchEvent(new CustomEvent('end'));
          }, { once: true });
        }
        return;
      }

      if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        if (options && options.voice) {
          utterance.voice = options.voice;
        } else {
          const voices = window.speechSynthesis.getVoices();
          const natural = voices.find((v) => /natural|neural|google|samantha/i.test(v.name));
          if (natural) utterance.voice = natural;
        }

        utterance.onboundary = (e) => {
          if (e.name === 'word') {
            this.level = 0.65 + Math.random() * 0.35;
          }
        };

        utterance.onend = () => {
          this.state = this._rest;
          this.dispatchEvent(new CustomEvent('end'));
        };

        window.speechSynthesis.speak(utterance);
      }
    }

    _initDOM() {
      this.shadowRoot.innerHTML = `
        <style>
          :host {
            display: inline-flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            position: relative;
            width: 240px;
            height: 240px;
          }
          .aura {
            position: absolute;
            width: 86%;
            height: 86%;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(255, 46, 147, 0.35) 0%, rgba(124, 58, 237, 0.22) 55%, transparent 75%);
            filter: blur(24px);
            pointer-events: none;
            transition: transform 0.25s ease;
            z-index: 1;
          }
          canvas {
            position: relative;
            z-index: 2;
            width: 100%;
            height: 100%;
            display: block;
          }
          .caption-pod {
            position: absolute;
            bottom: -32px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #ffffff;
            border: 1px solid rgba(124, 58, 237, 0.2);
            border-radius: 14px;
            padding: 5px 12px;
            font-size: 12px;
            font-weight: 600;
            color: #1f1633;
            box-shadow: 0 4px 14px rgba(124, 58, 237, 0.1);
            z-index: 3;
            max-width: 90%;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
        </style>
        <div class="aura"></div>
        <canvas></canvas>
        <div class="caption-pod" role="status" aria-live="polite" style="display:none;"></div>
      `;
    }

    _updateCaption() {
      const pod = this.shadowRoot.querySelector('.caption-pod');
      if (!pod) return;
      if (this._caption) {
        pod.style.display = 'inline-flex';
        pod.textContent = this._caption;
      } else {
        pod.style.display = 'none';
      }
    }

    _initWebGL() {
      const canvas = this.shadowRoot.querySelector('canvas');
      if (!canvas) return;

      const gl = canvas.getContext('webgl', { alpha: true, antialias: true, depth: false });
      if (!gl) return;
      this._gl = gl;

      const compile = (type, src) => {
        const s = gl.createShader(type);
        gl.shaderSource(s, src);
        gl.compileShader(s);
        return s;
      };

      const vs = compile(gl.VERTEX_SHADER, VERTEX_SHADER);
      const fs = compile(gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
      const prg = gl.createProgram();
      gl.attachShader(prg, vs);
      gl.attachShader(prg, fs);
      gl.linkProgram(prg);
      gl.useProgram(prg);
      this._program = prg;

      // 12,000 Fibonacci Sphere Particles
      const count = ('ontouchstart' in window || navigator.maxTouchPoints > 0) ? 6000 : 12000;
      const positions = new Float32Array(count * 3);
      const colors = new Float32Array(count * 3);
      const phases = new Float32Array(count);
      const drifts = new Float32Array(count * 3);
      const goldenRatio = (1 + Math.sqrt(5)) / 2;

      for (let i = 0; i < count; i++) {
        const theta = 2 * Math.PI * i / goldenRatio;
        const phi = Math.acos(1 - 2 * (i + 0.5) / count);
        const x = Math.sin(phi) * Math.cos(theta);
        const y = Math.cos(phi);
        const z = Math.sin(phi) * Math.sin(theta);

        const r = 0.88 * (0.94 + Math.random() * 0.12);
        positions[i * 3] = x * r;
        positions[i * 3 + 1] = y * r;
        positions[i * 3 + 2] = z * r;

        const blend = (y + 1) * 0.5;
        if (Math.random() < 0.12) {
          colors[i * 3] = 1.0;
          colors[i * 3 + 1] = 0.95;
          colors[i * 3 + 2] = 1.0;
        } else {
          colors[i * 3] = 0.49 + blend * 0.51;        // Hot Pink to Royal Purple
          colors[i * 3 + 1] = 0.23 - blend * 0.05;
          colors[i * 3 + 2] = 0.93 - blend * 0.35;
        }
        phases[i] = Math.random();

        drifts[i * 3] = (Math.random() - 0.5) * 2.0;
        drifts[i * 3 + 1] = (Math.random() - 0.5) * 2.0;
        drifts[i * 3 + 2] = (Math.random() - 0.5) * 2.0;
      }

      const bindBuf = (data, loc, size) => {
        const b = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, b);
        gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
        gl.enableVertexAttribArray(loc);
        gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0);
      };

      bindBuf(positions, gl.getAttribLocation(prg, 'aPosition'), 3);
      bindBuf(colors, gl.getAttribLocation(prg, 'aColor'), 3);
      bindBuf(phases, gl.getAttribLocation(prg, 'aPhase'), 1);
      bindBuf(drifts, gl.getAttribLocation(prg, 'aDrift'), 3);

      const uMatrix = gl.getUniformLocation(prg, 'uMatrix');
      const uTime = gl.getUniformLocation(prg, 'uTime');
      const uState = gl.getUniformLocation(prg, 'uState');
      const uAudioLevel = gl.getUniformLocation(prg, 'uAudioLevel');
      const uPixelRatio = gl.getUniformLocation(prg, 'uPixelRatio');
      const uStyle = gl.getUniformLocation(prg, 'uStyle');

      const zoom = 1.35;
      gl.uniformMatrix4fv(uMatrix, false, new Float32Array([
        zoom, 0, 0, 0,
        0, zoom, 0, 0,
        0, 0, -0.5, 0,
        0, 0, 0, 1,
      ]));

      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE);

      const aura = this.shadowRoot.querySelector('.aura');

      const render = (now) => {
        const elapsed = (now - this._startTime) / 1000;
        this._smoothedLevel += (this._level - this._smoothedLevel) * 0.25;

        const stateVal = {
          idle: 0,
          done: 0,
          listening: 1,
          thinking: 2,
          searching: 2,
          speaking: 3,
        }[this._state] || 0;

        const styleVal = {
          astral: 0.0,
          plasma: 1.0,
          sonic: 2.0,
        }[this._styleMode] || 0.0;

        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const w = canvas.clientWidth * dpr;
        const h = canvas.clientHeight * dpr;
        if (canvas.width !== w || canvas.height !== h) {
          canvas.width = w;
          canvas.height = h;
          gl.viewport(0, 0, w, h);
        }

        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);

        gl.uniform1f(uTime, elapsed);
        gl.uniform1f(uState, stateVal);
        gl.uniform1f(uAudioLevel, this._smoothedLevel);
        gl.uniform1f(uPixelRatio, dpr);
        gl.uniform1f(uStyle, styleVal);

        gl.drawArrays(gl.POINTS, 0, count);

        if (aura) {
          const auraScale = 1.0 + Math.min(0.4, this._smoothedLevel * 0.8);
          aura.style.transform = `scale(${auraScale})`;
        }

        this._animId = requestAnimationFrame(render);
      };

      this._animId = requestAnimationFrame(render);
    }
  }

  customElements.define('speaking-orb', SpeakingOrbElement);
})();
