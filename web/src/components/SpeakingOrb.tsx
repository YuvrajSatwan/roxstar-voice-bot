import React, { useEffect, useRef, useState } from 'react';

export type SpeakingOrbState = 'idle' | 'listening' | 'thinking' | 'searching' | 'speaking' | 'done';

export interface SpeakingOrbProps {
  state?: SpeakingOrbState;
  audioLevel?: number; // 0.0 to 1.0
  size?: 'sm' | 'md' | 'lg';
  caption?: string | null;
  className?: string;
  particles?: number;
}

const VERTEX_SHADER = `
precision highp float;
attribute vec3 aPosition;
attribute vec3 aColor;
attribute float aPhase;

uniform mat4 uMatrix;
uniform float uTime;
uniform float uState;     // 0: idle, 1: listening, 2: thinking, 3: speaking
uniform float uAudioLevel; // 0.0 - 1.0
uniform float uPixelRatio;

varying vec3 vColor;
varying float vAlpha;

void main() {
  vec3 pos = aPosition;

  // Base rotation around Y and subtle wobble on X
  float angleY = uTime * 0.4;
  float cosY = cos(angleY);
  float sinY = sin(angleY);
  mat3 rotY = mat3(
    cosY, 0.0, sinY,
    0.0, 1.0, 0.0,
    -sinY, 0.0, cosY
  );

  float angleX = sin(uTime * 0.25) * 0.2;
  float cosX = cos(angleX);
  float sinX = sin(angleX);
  mat3 rotX = mat3(
    1.0, 0.0, 0.0,
    0.0, cosX, -sinX,
    0.0, sinX, cosX
  );

  pos = rotX * (rotY * pos);

  float swell = 1.0;
  float brightness = 1.0;

  // State 1: Listening (Voice Reactivity from user mic)
  if (uState > 0.5 && uState < 1.5) {
    float pulse = sin(uTime * 3.0 + aPhase * 6.28) * 0.06;
    swell = 1.0 + (uAudioLevel * 0.55) + pulse;
    brightness = 1.0 + uAudioLevel * 0.8;
  }
  // State 2: Thinking (Swirling orbital acceleration)
  else if (uState >= 1.5 && uState < 2.5) {
    float twist = sin(pos.y * 3.5 + uTime * 4.0) * 0.25;
    pos.x += -pos.z * twist;
    pos.z += pos.x * twist;
    swell = 0.95 + sin(uTime * 5.0) * 0.08;
    brightness = 1.2 + sin(uTime * 6.0 + aPhase * 3.14) * 0.4;
  }
  // State 3: Speaking (Assistant voice swell & bottom-to-top lit rings)
  else if (uState >= 2.5) {
    // Vocal swell from audio level
    swell = 1.05 + (uAudioLevel * 0.7);

    // Traveling lit rings from bottom (-y) to top (+y) with every syllable
    float ringWave = sin((pos.y * 2.8) - (uTime * 7.5) + aPhase * 0.5);
    float ringIntensity = smoothstep(0.4, 1.0, ringWave);
    swell += ringIntensity * 0.18;
    brightness = 1.1 + ringIntensity * 1.4 + uAudioLevel * 0.9;
  }
  // State 0: Idle (Gentle resting respiration)
  else {
    swell = 1.0 + sin(uTime * 1.5 + aPhase * 2.0) * 0.04;
    brightness = 0.85;
  }

  pos *= swell;

  vec4 finalPos = uMatrix * vec4(pos, 1.0);
  gl_Position = finalPos;

  // Point size scaled with depth and screen pixel ratio
  float pSize = (3.2 + brightness * 1.6) * uPixelRatio;
  gl_PointSize = clamp(pSize * (1.2 / (finalPos.w + 0.3)), 1.5, 9.0);

  vColor = aColor * brightness;
  vAlpha = clamp(0.4 + brightness * 0.5, 0.3, 1.0);
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
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const audioLevelRef = useRef(audioLevel);
  audioLevelRef.current = audioLevel;
  const stateRef = useRef(state);
  stateRef.current = state;

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

    // Uniforms
    const uMatrix = gl.getUniformLocation(program, 'uMatrix');
    const uTime = gl.getUniformLocation(program, 'uTime');
    const uState = gl.getUniformLocation(program, 'uState');
    const uAudioLevel = gl.getUniformLocation(program, 'uAudioLevel');
    const uPixelRatio = gl.getUniformLocation(program, 'uPixelRatio');

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

      gl.drawArrays(gl.POINTS, 0, count);

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animId);
      gl.deleteBuffer(posBuffer);
      gl.deleteBuffer(colorBuffer);
      gl.deleteBuffer(phaseBuffer);
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
    private _micStopFn: (() => void) | null = null;

    static get observedAttributes() {
      return ['state', 'level', 'caption', 'rest'];
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
      this.render();
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
