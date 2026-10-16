/**
 * Motor Acústico Semiológico Procedural (StethoscopeAudioEngine)
 * Síntese DSP Biomédica em Web Audio API pura (Zero-Dependency Audio Assets).
 * 
 * Modula sons cardíacos e pulmonares em tempo real sincronizados com
 * a Frequência Cardíaca (HR) e Frequência Respiratória (RR) atuais do paciente.
 */

export type AuscultationSoundType =
  | 'NORMAL_VESICULAR'      // Murmúrio vesicular fisiológico
  | 'COARSE_CRACKLES'       // Estertores crepitantes teleinspiratórios (congestão alveolar)
  | 'EXPIRATORY_WHEEZES'    // Sibilos expiratórios polifônicos (broncoespasmo)
  | 'SYSTOLIC_MURMUR'       // Sopro holossistólico rude em diamante (estenose aórtica / IM)
  | 'PERICARDIAL_RUB'       // Atrito pericárdico áspero trifásico (pericardite aguda)
  | 'NORMAL_HEART';         // B1 + B2 normofonéticas fisiológicas

export class StethoscopeAudioEngine {
  private ctx: AudioContext | null = null;
  private isPlaying: boolean = false;
  private loopTimer: number | null = null;
  private masterGain: GainNode | null = null;

  private initContext() {
    if (!this.ctx) {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;
      this.ctx = new AudioCtx();
      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.value = 0.85;
      this.masterGain.connect(this.ctx.destination);
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
  }

  /**
   * Gera um buffer de ruído branco para síntese subtrativa (sopros, murmúrio e crepitações)
   */
  private createWhiteNoiseBuffer(durationSec: number): AudioBuffer | null {
    if (!this.ctx) return null;
    const bufferSize = Math.max(1, Math.floor(this.ctx.sampleRate * durationSec));
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = Math.random() * 2 - 1;
    }
    return buffer;
  }

  /**
   * Dispara uma bulha cardíaca (B1 ou B2) usando oscilador senoidal com decaimento exponencial
   */
  private triggerHeartSound(time: number, freq: number, duration: number, gainVal: number) {
    if (!this.ctx || !this.masterGain) return;
    try {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, time);
      osc.frequency.exponentialRampToValueAtTime(20, time + duration);

      gain.gain.setValueAtTime(0.001, time);
      gain.gain.linearRampToValueAtTime(gainVal, time + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.001, time + duration);

      osc.connect(gain);
      gain.connect(this.masterGain);

      osc.start(time);
      osc.stop(time + duration);
    } catch {
      // Falha defensiva de áudio não interrompe execução
    }
  }

  /**
   * Inicia a ausculta contínua no foco selecionado, modulada por FC e FR.
   */
  public startAuscultation(soundType: AuscultationSoundType, hr: number = 80, rr: number = 18) {
    this.stopAuscultation();
    this.initContext();
    if (!this.ctx) return;
    this.isPlaying = true;

    const isCardiac = ['NORMAL_HEART', 'SYSTOLIC_MURMUR', 'PERICARDIAL_RUB'].includes(soundType);

    if (isCardiac) {
      const clampedHr = Math.max(40, Math.min(hr || 80, 220));
      const beatIntervalMs = (60 / clampedHr) * 1000;

      const playCardiacCycle = () => {
        if (!this.isPlaying || !this.ctx || !this.masterGain) return;
        const now = this.ctx.currentTime;
        const systoleDuration = (beatIntervalMs / 1000) * 0.35;

        // B1 (TUM) - Fechamento Mitral/Tricúspide (~55Hz)
        this.triggerHeartSound(now, 55, 0.09, 0.9);
        // B2 (TÁ) - Fechamento Aórtico/Pulmonar (~85Hz, mais seca e rápida)
        this.triggerHeartSound(now + systoleDuration, 85, 0.06, 0.7);

        if (soundType === 'SYSTOLIC_MURMUR') {
          // Sopro holossistólico em diamante entre B1 e B2 (Ruído filtrado passa-banda 240Hz)
          const noiseBuffer = this.createWhiteNoiseBuffer(systoleDuration);
          if (noiseBuffer) {
            const noise = this.ctx.createBufferSource();
            noise.buffer = noiseBuffer;
            const filter = this.ctx.createBiquadFilter();
            filter.type = 'bandpass';
            filter.frequency.value = 240;
            filter.Q.value = 2.5;

            const env = this.ctx.createGain();
            env.gain.setValueAtTime(0.01, now + 0.04);
            env.gain.linearRampToValueAtTime(0.42, now + systoleDuration / 2); // Pico mesossistólico
            env.gain.linearRampToValueAtTime(0.01, now + systoleDuration);

            noise.connect(filter);
            filter.connect(env);
            env.connect(this.masterGain);
            noise.start(now + 0.04);
          }
        }

        if (soundType === 'PERICARDIAL_RUB') {
          // Som áspero trifásico de raspagem (alta frequência de atrito 650-800Hz)
          [0.05, systoleDuration + 0.05, systoleDuration + 0.22].forEach((offset) => {
            if (!this.ctx || !this.masterGain) return;
            const rubBuffer = this.createWhiteNoiseBuffer(0.07);
            if (rubBuffer) {
              const rubNoise = this.ctx.createBufferSource();
              rubNoise.buffer = rubBuffer;
              const bandpass = this.ctx.createBiquadFilter();
              bandpass.type = 'bandpass';
              bandpass.frequency.value = 750;
              bandpass.Q.value = 4.0;
              const g = this.ctx.createGain();
              g.gain.value = 0.35;
              rubNoise.connect(bandpass);
              bandpass.connect(g);
              g.connect(this.masterGain);
              rubNoise.start(now + offset);
            }
          });
        }
      };

      playCardiacCycle();
      this.loopTimer = window.setInterval(playCardiacCycle, beatIntervalMs);
    } else {
      // CICLO RESPIRATÓRIO
      const clampedRr = Math.max(8, Math.min(rr || 16, 50));
      const breathCycleSec = 60 / clampedRr;
      const inspDuration = breathCycleSec * 0.4;
      const expDuration = breathCycleSec * 0.6;

      const playRespiratoryCycle = () => {
        if (!this.isPlaying || !this.ctx || !this.masterGain) return;
        const now = this.ctx.currentTime;

        // Base: Murmúrio Vesicular fisiológico (Ruído passa-baixa 280Hz na inspiração)
        const mvBuffer = this.createWhiteNoiseBuffer(breathCycleSec);
        if (mvBuffer) {
          const mvSource = this.ctx.createBufferSource();
          mvSource.buffer = mvBuffer;
          const lowpass = this.ctx.createBiquadFilter();
          lowpass.type = 'lowpass';
          lowpass.frequency.value = 280;

          const mvGain = this.ctx.createGain();
          mvGain.gain.setValueAtTime(0.01, now);
          mvGain.gain.linearRampToValueAtTime(0.25, now + inspDuration * 0.7);
          mvGain.gain.linearRampToValueAtTime(0.08, now + inspDuration + expDuration * 0.3);
          mvGain.gain.linearRampToValueAtTime(0.005, now + breathCycleSec - 0.1);

          mvSource.connect(lowpass);
          lowpass.connect(mvGain);
          mvGain.connect(this.masterGain);
          mvSource.start(now);
        }

        if (soundType === 'COARSE_CRACKLES') {
          // Estertores Crepitantes Teleinspiratórios (micro-impulsos explosivos de 6ms no terço final da inspiração)
          const crackleStart = now + inspDuration * 0.55;
          const numCrackles = 14;
          for (let i = 0; i < numCrackles; i++) {
            const popTime = crackleStart + Math.random() * (inspDuration * 0.42);
            const popBuffer = this.createWhiteNoiseBuffer(0.006);
            if (popBuffer && this.ctx && this.masterGain) {
              const pop = this.ctx.createBufferSource();
              pop.buffer = popBuffer;
              const hp = this.ctx.createBiquadFilter();
              hp.type = 'bandpass';
              hp.frequency.value = 950 + Math.random() * 500;
              hp.Q.value = 3.0;
              const popGain = this.ctx.createGain();
              popGain.gain.value = 0.5 + Math.random() * 0.3;

              pop.connect(hp);
              hp.connect(popGain);
              popGain.connect(this.masterGain);
              pop.start(popTime);
            }
          }
        }

        if (soundType === 'EXPIRATORY_WHEEZES') {
          // Sibilos Expiratórios Polifônicos (osciladores dente de serra em 420Hz e 590Hz na expiração)
          const expStart = now + inspDuration;
          [420, 590].forEach((freq) => {
            if (!this.ctx || !this.masterGain) return;
            const wheezeOsc = this.ctx.createOscillator();
            wheezeOsc.type = 'sawtooth';
            wheezeOsc.frequency.setValueAtTime(freq, expStart);
            wheezeOsc.frequency.linearRampToValueAtTime(freq - 45, expStart + expDuration * 0.85);

            const wf = this.ctx.createBiquadFilter();
            wf.type = 'bandpass';
            wf.frequency.value = freq;
            wf.Q.value = 6.0;

            const wg = this.ctx.createGain();
            wg.gain.setValueAtTime(0.001, expStart);
            wg.gain.linearRampToValueAtTime(0.12, expStart + 0.15);
            wg.gain.linearRampToValueAtTime(0.001, expStart + expDuration * 0.85);

            wheezeOsc.connect(wf);
            wf.connect(wg);
            wg.connect(this.masterGain);
            wheezeOsc.start(expStart);
            wheezeOsc.stop(expStart + expDuration * 0.88);
          });
        }
      };

      playRespiratoryCycle();
      this.loopTimer = window.setInterval(playRespiratoryCycle, breathCycleSec * 1000);
    }
  }

  public stopAuscultation() {
    this.isPlaying = false;
    if (this.loopTimer !== null) {
      clearInterval(this.loopTimer);
      this.loopTimer = null;
    }
  }

  public destroy() {
    this.stopAuscultation();
    if (this.ctx && this.ctx.state !== 'closed') {
      this.ctx.close().catch(() => {});
      this.ctx = null;
    }
  }
}

export const stethoscopeEngine = new StethoscopeAudioEngine();
