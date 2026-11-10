import React, { useEffect, useRef, useState } from 'react';

export type SpeakingOrbState = 'idle' | 'listening' | 'thinking' | 'searching' | 'speaking' | 'done';
export type SpeakingOrbStyle = 'astral' | 'plasma' | 'sonic';

export interface SpeakingOrbProps {
  state?: SpeakingOrbState;
  audioLevel?: number; // 0.0 to 1.0
  size?: 'sm' | 'md' | 'lg';
  caption?: string | null;
  className?: string;
  particles?: number;
  styleMode?: SpeakingOrbStyle;
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

  // 1. Procedural 3D Curl Fluid Turbulence: gives living organic drift to every particle
  vec3 noiseSample = pos * 1.5 + vec3(0.0, uTime * 0.2, uTime * 0.14) + aDrift * 0.35;
  float n1 = snoise(noiseSample);
  float n2 = snoise(noiseSample + vec3(14.2, 28.1, 7.3));
  float n3 = snoise(noiseSample + vec3(39.1, 11.4, 25.7));
  vec3 fluidDisp = vec3(n1, n2, n3) * 0.17;

  // Non-linear variable orbital rotation (never constant mechanical speed)
  float spinSpeed = 0.32 + sin(uTime * 0.15) * 0.08;
  if (uState >= 1.5 && uState < 2.5) {
    spinSpeed = 1.45; // Thinking mode acceleration
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

  // Apply fluid noise displacement
  pos += fluidDisp * (1.0 + uAudioLevel * 0.6);

  float swell = 1.0;
  float brightness = 1.0;
  vec3 dynamicColor = aColor;

  // StarMaker Color Tokens
  vec3 colorPink = vec3(1.0, 0.18, 0.58);   // #FF2E93 Hot Pink
  vec3 colorPurple = vec3(0.49, 0.23, 0.93); // #7C3AED Royal Purple
  vec3 colorCyan = vec3(0.02, 0.71, 0.83);   // #06B6D4 Electric Cyan

  // STYLE 0: Astral Stardust (Procedural non-repetitive fluid stardust)
  if (uStyle < 0.5) {
    if (uState > 0.5 && uState < 1.5) {
      // Listening: Soundwave ripples reacting to user mic
      float soundRipple = sin(length(pos) * 5.5 - uTime * 6.0) * (uAudioLevel * 0.25);
      pos += normalize(pos) * soundRipple;
      swell = 1.0 + (uAudioLevel * 0.5) + sin(uTime * 3.2 + aPhase * 6.28) * 0.05;
      brightness = 1.0 + uAudioLevel * 1.1;
      dynamicColor = mix(dynamicColor, colorCyan, clamp(uAudioLevel * 1.3, 0.0, 0.8));
    }
    else if (uState >= 1.5 && uState < 2.5) {
      // Thinking: Dual-vortex inward galactic spiral
      float spiral = sin(pos.y * 4.0 + uTime * 6.0) * 0.3;
      pos.x += -pos.z * spiral;
      pos.z += pos.x * spiral;
      swell = 0.93 + sin(uTime * 5.0) * 0.08;
      brightness = 1.3 + sin(uTime * 7.0 + aPhase * 3.14) * 0.45;
      dynamicColor = mix(colorPurple, colorPink, sin(uTime * 3.0 + pos.y * 3.0) * 0.5 + 0.5);
    }
    else if (uState >= 2.5) {
      // Speaking: Syllable lit rings + Harmonic vocal swell
      swell = 1.04 + (uAudioLevel * 0.72);
      float ringWave = sin((pos.y * 3.2) - (uTime * 8.5) + aPhase * 0.5);
      float ringIntensity = smoothstep(0.45, 1.0, ringWave);
      swell += ringIntensity * 0.18;
      brightness = 1.1 + ringIntensity * 1.6 + uAudioLevel * 0.95;
      dynamicColor = mix(dynamicColor, colorPink, ringIntensity * 0.7);
    }
    else {
      // Idle: Fluid respiration
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

  // Smooth radial circular point with glowing luminous core
  float intensity = smoothstep(0.5, 0.05, dist);
  float core = smoothstep(0.2, 0.0, dist) * 0.5;

  gl_FragColor = vec4(vColor + vec3(core), vAlpha * intensity);
}
`;

export const SpeakingOrb: React.FC<SpeakingOrbProps> = ({
  state = 'idle',
  audioLevel = 0,
  size = 'md',
  caption,
  className = '',
  particles: userParticleCount,
  styleMode = 'astral',
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const audioLevelRef = useRef(audioLevel);
  audioLevelRef.current = audioLevel;
  const stateRef = useRef(state);
  stateRef.current = state;
  const styleModeRef = useRef(styleMode);
  styleModeRef.current = styleMode;

  const [hasWebGL, setHasWebGL] = useState(true);

  const sizePixels = {
    sm: 130,
    md: 180,
    lg: 220,
  }[size];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Detect touch/mobile device for particle budget
    const isTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    const count = userParticleCount ?? (isTouch ? 6000 : 12000);

    // Try WebGL first
    const gl = canvas.getContext('webgl', {
      alpha: true,
      antialias: true,
      depth: false,
      powerPreference: 'high-performance',
    });

    if (!gl) {
      setHasWebGL(false);
      return;
    }

    setHasWebGL(true);

    // Compile Shaders
    const createShader = (type: number, src: string) => {
      const s = gl.createShader(type);
      if (!s) return null;
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
        console.warn('Shader compile err:', gl.getShaderInfoLog(s));
        gl.deleteShader(s);
        return null;
      }
      return s;
    };

    const vs = createShader(gl.VERTEX_SHADER, VERTEX_SHADER);
    const fs = createShader(gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
    if (!vs || !fs) return;

    const program = gl.createProgram();
    if (!program) return;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.warn('Program link err:', gl.getProgramInfoLog(program));
      return;
    }

    gl.useProgram(program);

    // Generate 12,000 Fibonacci Sphere Particles
    // StarMaker Signature Colors: Hot Pink (#FF2E93), Royal Purple (#7C3AED), Pure White
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const phases = new Float32Array(count);
    const drifts = new Float32Array(count * 3);

    const radius = 0.88;
    const goldenRatio = (1 + Math.sqrt(5)) / 2;

    for (let i = 0; i < count; i++) {
      // Fibonacci sphere distribution
      const theta = 2 * Math.PI * i / goldenRatio;
      const phi = Math.acos(1 - 2 * (i + 0.5) / count);

      const x = Math.sin(phi) * Math.cos(theta);
      const y = Math.cos(phi);
      const z = Math.sin(phi) * Math.sin(theta);

      // Slight radial scatter for volume
      const rScatter = radius * (0.94 + Math.random() * 0.12);
      positions[i * 3] = x * rScatter;
      positions[i * 3 + 1] = y * rScatter;
      positions[i * 3 + 2] = z * rScatter;

      // Color mapping:
      // Upper pole and center: Hot Pink (#FF2E93: 1.0, 0.18, 0.58)
      // Lower pole and core: Royal Purple (#7C3AED: 0.49, 0.23, 0.93)
      // Accents: Radiant White
      const blend = (y + 1) * 0.5; // 0 (bottom) to 1 (top)
      const isWhiteSparkle = Math.random() < 0.12;

      if (isWhiteSparkle) {
        colors[i * 3] = 1.0;
        colors[i * 3 + 1] = 0.95;
        colors[i * 3 + 2] = 1.0;
      } else {
        // Gradient from Royal Purple to Hot Pink
        colors[i * 3] = 0.49 + blend * 0.51;        // R: 0.49 -> 1.0
        colors[i * 3 + 1] = 0.23 - blend * 0.05;    // G: 0.23 -> 0.18
        colors[i * 3 + 2] = 0.93 - blend * 0.35;    // B: 0.93 -> 0.58
      }

      phases[i] = Math.random();

      // Procedural drift vector for simplex curl turbulence
      drifts[i * 3] = (Math.random() - 0.5) * 2.0;
      drifts[i * 3 + 1] = (Math.random() - 0.5) * 2.0;
      drifts[i * 3 + 2] = (Math.random() - 0.5) * 2.0;
    }

    // Buffers
    const posBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, posBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

    const aPos = gl.getAttribLocation(program, 'aPosition');
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 0, 0);

    const colorBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, colorBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, colors, gl.STATIC_DRAW);

    const aColor = gl.getAttribLocation(program, 'aColor');
    gl.enableVertexAttribArray(aColor);
    gl.vertexAttribPointer(aColor, 3, gl.FLOAT, false, 0, 0);

    const phaseBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, phaseBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, phases, gl.STATIC_DRAW);

    const aPhase = gl.getAttribLocation(program, 'aPhase');
    gl.enableVertexAttribArray(aPhase);
    gl.vertexAttribPointer(aPhase, 1, gl.FLOAT, false, 0, 0);

    const driftBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, driftBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, drifts, gl.STATIC_DRAW);

    const aDrift = gl.getAttribLocation(program, 'aDrift');
    gl.enableVertexAttribArray(aDrift);
    gl.vertexAttribPointer(aDrift, 3, gl.FLOAT, false, 0, 0);

    // Uniforms
    const uMatrix = gl.getUniformLocation(program, 'uMatrix');
    const uTime = gl.getUniformLocation(program, 'uTime');
    const uState = gl.getUniformLocation(program, 'uState');
    const uAudioLevel = gl.getUniformLocation(program, 'uAudioLevel');
    const uPixelRatio = gl.getUniformLocation(program, 'uPixelRatio');
    const uStyle = gl.getUniformLocation(program, 'uStyle');

    // Orthographic / Isometric Projection Matrix
    const aspect = 1.0;
    const zoom = 1.35;
    const matrix = new Float32Array([
      zoom / aspect, 0, 0, 0,
      0, zoom, 0, 0,
      0, 0, -0.5, 0,
      0, 0, 0, 1,
    ]);
    gl.uniformMatrix4fv(uMatrix, false, matrix);

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE); // Additive blending for luminous glow

    let animId: number;
    let startTime = performance.now();
    let smoothedLevel = 0;

    const render = (now: number) => {
      const elapsed = (now - startTime) / 1000;

      // Smooth audio level
      const targetLevel = audioLevelRef.current || 0;
      smoothedLevel += (targetLevel - smoothedLevel) * 0.25;

      const stateVal = {
        idle: 0,
        done: 0,
        listening: 1,
        thinking: 2,
        searching: 2,
        speaking: 3,
      }[stateRef.current] ?? 0;

      const styleVal = {
        astral: 0.0,
        plasma: 1.0,
        sonic: 2.0,
      }[styleModeRef.current] ?? 0.0;

      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const width = canvas.clientWidth * dpr;
      const height = canvas.clientHeight * dpr;

      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
        gl.viewport(0, 0, width, height);
      }

      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);

      gl.uniform1f(uTime, elapsed);
      gl.uniform1f(uState, stateVal);
      gl.uniform1f(uAudioLevel, smoothedLevel);
      gl.uniform1f(uPixelRatio, dpr);
      gl.uniform1f(uStyle, styleVal);

      gl.drawArrays(gl.POINTS, 0, count);

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animId);
      gl.deleteBuffer(posBuffer);
      gl.deleteBuffer(colorBuffer);
      gl.deleteBuffer(phaseBuffer);
      gl.deleteBuffer(driftBuffer);
      gl.deleteProgram(program);
    };
  }, [userParticleCount]);

  return (
    <div
      className={`speaking-orb-wrapper ${className}`}
      data-state={state}
      style={{
        width: sizePixels,
        minHeight: sizePixels,
      }}
    >
      {/* Outer Atmospheric Radiant Rings */}
      <div
        className={`speaking-orb-aura ${state === 'speaking' ? 'speaking-orb-aura--speaking' : ''} ${
          state === 'listening' ? 'speaking-orb-aura--listening' : ''
        }`}
        style={{
          transform: `scale(${1 + Math.min(0.4, audioLevel * 0.8)})`,
        }}
      />

      {/* High-Performance 12,000 Particle WebGL Canvas */}
      <canvas
        ref={canvasRef}
        className="speaking-orb-canvas"
        style={{ width: sizePixels, height: sizePixels }}
      />

      {/* Live Particle-Style Spoken Captions */}
      {caption && (
        <div className="speaking-orb-caption-pod" role="status" aria-live="polite">
          <span className="speaking-orb-caption-pulse" />
          <p className="speaking-orb-caption-text">
            {caption.split(' ').map((word, idx, arr) => {
              const isRecent = idx >= arr.length - 2;
              return (
                <span
                  key={idx}
                  className={`speaking-orb-caption-word ${isRecent ? 'speaking-orb-caption-word--active' : ''}`}
                >
                  {word}{' '}
                </span>
              );
            })}
          </p>
        </div>
      )}
    </div>
  );
};

// Register <speaking-orb> Web Component if in browser environment
if (typeof window !== 'undefined' && !customElements.get('speaking-orb')) {
  class SpeakingOrbElement extends HTMLElement {
    private _state: SpeakingOrbState = 'listening';
    private _rest: SpeakingOrbState = 'listening';
    private _level = 0;
    private _styleMode: SpeakingOrbStyle = 'astral';
    private _micStopFn: (() => void) | null = null;

    static get observedAttributes() {
      return ['state', 'level', 'caption', 'rest', 'style-mode'];
    }

    connectedCallback() {
      this.render();
    }

    disconnectedCallback() {
      if (this._micStopFn) {
        this._micStopFn();
        this._micStopFn = null;
      }
    }

    attributeChangedCallback(name: string, _oldVal: string, newVal: string) {
      if (name === 'state') this._state = (newVal as SpeakingOrbState) || 'listening';
      if (name === 'rest') this._rest = (newVal as SpeakingOrbState) || 'listening';
      if (name === 'level') this._level = parseFloat(newVal) || 0;
      if (name === 'style-mode') this._styleMode = (newVal as SpeakingOrbStyle) || 'astral';
      this.render();
    }

    set styleMode(val: SpeakingOrbStyle) {
      this._styleMode = val;
      this.setAttribute('style-mode', val);
    }

    get styleMode(): SpeakingOrbStyle {
      return this._styleMode;
    }

    set state(val: SpeakingOrbState) {
      this._state = val;
      this.setAttribute('state', val);
    }

    get state(): SpeakingOrbState {
      return this._state;
    }

    set rest(val: SpeakingOrbState) {
      this._rest = val;
      this.setAttribute('rest', val);
    }

    get rest(): SpeakingOrbState {
      return this._rest;
    }

    set level(val: number) {
      this._level = val;
      this.setAttribute('level', String(val));
    }

    get level(): number {
      return this._level;
    }

    async listen(): Promise<() => void> {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
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
            void ctx.close();
          } catch {}
        };
        this._micStopFn = stop;
        return stop;
      } catch (err) {
        console.warn('Microphone access denied:', err);
        return () => {};
      }
    }

    say(text: string, options?: { audio?: HTMLAudioElement; voice?: SpeechSynthesisVoice }) {
      this.state = 'speaking';
      this.setAttribute('caption', text);

      if (options && options.audio) {
        const audioEl = options.audio;
        try {
          const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
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

          audioEl.addEventListener(
            'ended',
            () => {
              active = false;
              this.state = this._rest;
              this.dispatchEvent(new CustomEvent('end'));
            },
            { once: true },
          );
        } catch {
          audioEl.addEventListener(
            'ended',
            () => {
              this.state = this._rest;
              this.dispatchEvent(new CustomEvent('end'));
            },
            { once: true },
          );
        }
        return;
      }

      if ('speechSynthesis' in window) {
        const u = new SpeechSynthesisUtterance(text);
        if (options && options.voice) {
          u.voice = options.voice;
        } else {
          const voices = window.speechSynthesis.getVoices();
          const natural = voices.find((v) => /natural|neural|google|samantha/i.test(v.name));
          if (natural) u.voice = natural;
        }

        u.onboundary = (e) => {
          if (e.name === 'word') {
            this.level = 0.65 + Math.random() * 0.35;
          }
        };

        u.onend = () => {
          this.state = this._rest;
          this.dispatchEvent(new CustomEvent('end'));
        };
        window.speechSynthesis.speak(u);
      }
    }

    render() {
      const caption = this.getAttribute('caption');
      this.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;width:100%;height:100%;">
          <div style="width:220px;height:220px;border-radius:50%;background:radial-gradient(circle,#ff2e93,#7c3aed);filter:blur(30px);opacity:0.25;position:absolute;"></div>
          <div style="font-size:13px;font-weight:700;color:#7c3aed;margin-top:10px;">Speaking Orb (${this._state})</div>
          ${caption ? `<div style="font-size:12px;font-weight:600;color:#1f1633;margin-top:4px;padding:4px 10px;background:#ffffff;border:1px solid rgba(124,58,237,0.2);border-radius:12px;">${caption}</div>` : ''}
        </div>
      `;
    }
  }

  try {
    customElements.define('speaking-orb', SpeakingOrbElement);
  } catch {}
}

export default SpeakingOrb;
