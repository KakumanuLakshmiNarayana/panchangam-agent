import '@fontsource/noto-sans-telugu/400.css';
import '@fontsource/noto-sans-telugu/700.css';
import React, { useEffect, useState } from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  continueRender,
  delayRender,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

// ── VideoData interface ───────────────────────────────────────────────────────
export interface VideoData {
  city: string;
  date: string;
  weekday: string;
  tz: string;
  tithi: string;
  tithiTime: string;
  nakshatra: string;
  nakshatraTime: string;
  paksha: string;
  rahukaal: string;
  durmuhurtam: string;
  brahma: string;
  abhijit: string;
  sunrise: string;
  sunset: string;
  audioDurationSec: number;
  audioFile: string;
  /** Per-scene frame counts measured from actual audio segments — enables exact sync */
  sceneFrames?: [number, number, number, number];
}

export const defaultVideoData: VideoData = {
  city: 'Dallas, TX',
  date: 'March 16, 2026',
  weekday: 'Monday',
  tz: 'CT',
  tithi: 'Dwadashi',
  tithiTime: 'upto 2:45 PM CT',
  nakshatra: 'Uttara Phalguni',
  nakshatraTime: 'upto 8:30 PM CT',
  paksha: 'Shukla Paksha',
  rahukaal: '12:00 PM – 1:30 PM CT',
  durmuhurtam: '3:15 PM – 4:45 PM CT',
  brahma: '5:12 AM – 6:00 AM CT',
  abhijit: '11:45 AM – 12:45 PM CT',
  sunrise: '6:45 AM CT',
  sunset: '6:15 PM CT',
  audioDurationSec: 20,
  audioFile: '',
};

// ── Palette ──────────────────────────────────────────────────────────────────
const WHITE = '#FFFFFF';
const MUTED = '#888888';
const GOLD = '#FFC81E';
const RED = '#E63C3C';
const SAFFRON = '#FF7800';
const ORANGE = '#FF6E0F';
const TELUGU = 'Noto Sans Telugu, system-ui, sans-serif';
const LATIN = 'system-ui, -apple-system, sans-serif';

// ── Shared helpers ────────────────────────────────────────────────────────────
const useEntrance = (localFrame: number) => {
  const { fps } = useVideoConfig();
  const prog = spring({ frame: localFrame, fps, config: { damping: 28, mass: 0.8, stiffness: 120 } });
  return {
    opacity: interpolate(localFrame, [0, 5], [0, 1], { extrapolateRight: 'clamp' }),
    ty: interpolate(prog, [0, 1], [24, 0]),
  };
};

const useCard = (localFrame: number, delay: number) => {
  const { fps } = useVideoConfig();
  const f = Math.max(0, localFrame - delay);
  const prog = spring({ frame: f, fps, config: { damping: 25, stiffness: 72, mass: 0.9 } });
  return {
    opacity: interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' }),
    transform: `translateY(${interpolate(prog, [0, 1], [50, 0])}px)`,
  };
};

// ── Stars background ──────────────────────────────────────────────────────────
const Stars: React.FC = () => {
  const stars = Array.from({ length: 180 }, (_, i) => {
    const a = i * 137.508;
    return {
      x: ((a * 1.234) % 1080),
      y: ((a * 0.765) % 1344),
      r: i % 6 === 0 ? 2 : 1,
      opacity: 0.12 + (i % 8) * 0.055,
    };
  });
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      <svg width={1080} height={1920} style={{ position: 'absolute', top: 0, left: 0 }}>
        {stars.map((s, i) => (
          <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="#FFD882" opacity={s.opacity} />
        ))}
      </svg>
    </AbsoluteFill>
  );
};

// ── Handle badge ──────────────────────────────────────────────────────────────
const Handle: React.FC<{ opacity: number }> = ({ opacity }) => (
  <div
    style={{
      position: 'absolute',
      top: 46,
      left: '50%',
      transform: 'translateX(-50%)',
      opacity,
      background: 'rgba(35, 16, 3, 0.88)',
      border: `2px solid ${ORANGE}`,
      borderRadius: 30,
      padding: '16px 52px',
      fontSize: 38,
      color: ORANGE,
      fontFamily: LATIN,
      fontWeight: 'bold',
      letterSpacing: 0.5,
      whiteSpace: 'nowrap',
    }}
  >
    @PanthuluPanchangam
  </div>
);

// ── Pandit character ──────────────────────────────────────────────────────────
const PanditChar: React.FC<{ opacity: number; frame: number }> = ({ opacity, frame }) => {
  const breathe = 1 + 0.007 * Math.sin(frame * 0.14);
  return (
    <div
      style={{
        position: 'absolute',
        bottom: 0,
        left: '50%',
        transform: `translateX(-50%) scaleY(${breathe})`,
        transformOrigin: 'bottom center',
        opacity,
        width: 600,
        height: 1080,
      }}
    >
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          width: 580,
          height: 580,
          borderRadius: '50%',
          background:
            'radial-gradient(circle, rgba(255,110,15,0.22) 0%, rgba(255,110,15,0.07) 40%, transparent 70%)',
        }}
      />
      <Img
        src={staticFile('pandit_character.png')}
        style={{
          position: 'absolute',
          bottom: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          height: 1060,
          width: 'auto',
          objectFit: 'contain',
        }}
      />
    </div>
  );
};

// ── Crossfade overlay ────────────────────────────────────────────────────────
const FadeOverlay: React.FC<{ localFrame: number; totalFrames: number }> = ({
  localFrame,
  totalFrames,
}) => {
  const FADE = 8;
  let alpha = 0;
  if (localFrame < FADE) {
    alpha = 1 - localFrame / FADE;
  } else if (localFrame >= totalFrames - FADE) {
    alpha = (localFrame - (totalFrames - FADE)) / FADE;
  }
  if (alpha <= 0) return null;
  return (
    <AbsoluteFill
      style={{ background: `rgba(0,0,0,${Math.min(alpha, 1)})`, pointerEvents: 'none' }}
    />
  );
};

// ── Divider ───────────────────────────────────────────────────────────────────
const Divider: React.FC<{ color?: string; opacity?: number }> = ({
  color = ORANGE,
  opacity = 0.45,
}) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 28 }}>
    <div style={{ flex: 1, height: 2, background: color, opacity }} />
    <div
      style={{
        width: 12,
        height: 12,
        borderRadius: 6,
        background: color,
        opacity: Math.min(opacity * 2, 1),
      }}
    />
    <div style={{ flex: 1, height: 2, background: color, opacity }} />
  </div>
);

// ════════════════════════════════════════════════════════════════════════════
// Scene 0 — Intro
// ════════════════════════════════════════════════════════════════════════════
const IntroScene: React.FC<{ localFrame: number; data: VideoData }> = ({ localFrame, data }) => {
  const { opacity, ty } = useEntrance(localFrame);
  const card1 = useCard(localFrame, 6);
  const paksha = useCard(localFrame, 20);

  return (
    <AbsoluteFill>
      <div
        style={{
          padding: '130px 60px 0',
          color: WHITE,
          display: 'flex',
          flexDirection: 'column',
          gap: 0,
        }}
      >
        {/* City */}
        <div
          style={{
            textAlign: 'center',
            fontSize: 110,
            fontWeight: 'bold',
            color: WHITE,
            fontFamily: LATIN,
            opacity,
            transform: `translateY(${ty}px)`,
            marginBottom: 10,
            lineHeight: 1.1,
          }}
        >
          {data.city}
        </div>

        {/* Date */}
        <div
          style={{
            textAlign: 'center',
            fontSize: 46,
            color: MUTED,
            fontFamily: LATIN,
            opacity,
            transform: `translateY(${ty}px)`,
            marginBottom: 22,
          }}
        >
          {data.weekday} &nbsp;•&nbsp; {data.date}
        </div>

        <div style={{ opacity, transform: `translateY(${ty}px)` }}>
          <Divider />
        </div>

        {/* Tithi + Nakshatra side by side */}
        <div style={{ display: 'flex', gap: 18, marginBottom: 22, ...card1 }}>
          {[
            { label: 'తిథి', value: data.tithi, sub: data.tithiTime },
            { label: 'నక్షత్రం', value: data.nakshatra, sub: data.nakshatraTime },
          ].map(({ label, value, sub }) => (
            <div
              key={label}
              style={{
                flex: 1,
                background: 'rgba(22, 12, 4, 0.92)',
                border: '2px solid rgba(200, 155, 40, 0.8)',
                borderRadius: 20,
                padding: '28px 18px 26px',
                textAlign: 'center',
              }}
            >
              <div
                style={{
                  fontSize: 42,
                  color: GOLD,
                  fontWeight: 'bold',
                  fontFamily: TELUGU,
                  marginBottom: 10,
                }}
              >
                {label}
              </div>
              <div style={{ height: 1, background: 'rgba(200,155,40,0.35)', marginBottom: 16 }} />
              <div
                style={{
                  fontSize: 72,
                  fontWeight: 'bold',
                  color: WHITE,
                  fontFamily: LATIN,
                  marginBottom: 8,
                  lineHeight: 1.1,
                }}
              >
                {value}
              </div>
              <div style={{ fontSize: 34, color: MUTED, fontFamily: LATIN }}>{sub}</div>
            </div>
          ))}
        </div>

        {/* Paksha */}
        <div
          style={{
            background: 'rgba(22, 12, 4, 0.88)',
            border: '2px solid rgba(200, 155, 40, 0.55)',
            borderRadius: 18,
            padding: '22px 30px',
            display: 'flex',
            alignItems: 'center',
            gap: 20,
            ...paksha,
          }}
        >
          <div style={{ fontSize: 42, color: GOLD, fontFamily: TELUGU, fontWeight: 'bold', whiteSpace: 'nowrap' }}>
            పక్షం
          </div>
          <div style={{ width: 1, height: 52, background: 'rgba(200,155,40,0.4)' }} />
          <div style={{ fontSize: 60, fontWeight: 'bold', color: WHITE, fontFamily: LATIN }}>
            {data.paksha}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ════════════════════════════════════════════════════════════════════════════
// Scene 1 — Bad Timings
// ════════════════════════════════════════════════════════════════════════════
const BadTimingsScene: React.FC<{ localFrame: number; data: VideoData }> = ({ localFrame, data }) => {
  const headerOp = interpolate(localFrame, [0, 10], [0, 1], { extrapolateRight: 'clamp' });
  const pulse = 1 + 0.012 * Math.sin(localFrame * 0.18);
  const card1 = useCard(localFrame, 6);
  const card2 = useCard(localFrame, 18);

  return (
    <AbsoluteFill>
      <div style={{ padding: '130px 60px 0', color: WHITE }}>
        <div
          style={{
            textAlign: 'center',
            fontSize: 72,
            fontWeight: 'bold',
            color: RED,
            fontFamily: TELUGU,
            opacity: headerOp,
            transform: `scale(${pulse})`,
            marginBottom: 18,
          }}
        >
          జాగ్రత్త! నివారించండి
        </div>
        <div
          style={{
            height: 2,
            background: 'rgba(145,28,28,0.85)',
            marginBottom: 28,
            opacity: headerOp,
          }}
        />

        {/* Rahu Kalam */}
        <div
          style={{
            position: 'relative',
            background: 'rgba(55, 6, 6, 0.96)',
            border: '3px solid rgba(230, 60, 60, 0.9)',
            borderRadius: 24,
            padding: '30px 34px',
            marginBottom: 22,
            overflow: 'hidden',
            ...card1,
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: 24,
              background: 'radial-gradient(ellipse at 50% 0%, rgba(230,60,60,0.14) 0%, transparent 55%)',
              pointerEvents: 'none',
            }}
          />
          <div
            style={{ fontSize: 52, fontWeight: 'bold', color: RED, fontFamily: TELUGU, marginBottom: 10 }}
          >
            రాహు కాలం
          </div>
          <div style={{ height: 1, background: 'rgba(230,60,60,0.3)', marginBottom: 16 }} />
          <div
            style={{ fontSize: 86, fontWeight: 'bold', color: WHITE, fontFamily: LATIN, lineHeight: 1.1 }}
          >
            {data.rahukaal}
          </div>
          <div
            style={{ fontSize: 40, color: 'rgba(255,160,160,0.9)', marginTop: 14, fontFamily: TELUGU }}
          >
            కొత్త పని మొదలు పెట్టకండి
          </div>
        </div>

        {/* Durmuhurtam */}
        <div
          style={{
            background: 'rgba(42, 8, 8, 0.93)',
            border: '2px solid rgba(200, 50, 50, 0.7)',
            borderRadius: 20,
            padding: '26px 34px',
            ...card2,
          }}
        >
          <div
            style={{ fontSize: 48, fontWeight: 'bold', color: RED, fontFamily: TELUGU, marginBottom: 10 }}
          >
            దుర్ముహూర్తం
          </div>
          <div style={{ height: 1, background: 'rgba(200,50,50,0.3)', marginBottom: 14 }} />
          <div
            style={{ fontSize: 76, fontWeight: 'bold', color: WHITE, fontFamily: LATIN, lineHeight: 1.1 }}
          >
            {data.durmuhurtam}
          </div>
          <div style={{ fontSize: 38, color: MUTED, marginTop: 10, fontFamily: TELUGU }}>
            శుభ కార్యాలు వద్దు
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ════════════════════════════════════════════════════════════════════════════
// Scene 2 — Good Timings
// ════════════════════════════════════════════════════════════════════════════
const GoodTimingsScene: React.FC<{ localFrame: number; data: VideoData }> = ({ localFrame, data }) => {
  const headerOp = interpolate(localFrame, [0, 10], [0, 1], { extrapolateRight: 'clamp' });
  const shimmer = 0.65 + 0.35 * Math.sin(localFrame * 0.11);
  const card1 = useCard(localFrame, 6);
  const card2 = useCard(localFrame, 18);

  return (
    <AbsoluteFill>
      <div style={{ padding: '130px 60px 0', color: WHITE }}>
        <div
          style={{
            textAlign: 'center',
            fontSize: 72,
            fontWeight: 'bold',
            color: GOLD,
            fontFamily: TELUGU,
            opacity: headerOp,
            marginBottom: 18,
            textShadow: `0 0 ${28 * shimmer}px rgba(255,200,30,0.65)`,
          }}
        >
          శుభ ముహూర్తాలు ✨
        </div>
        <div
          style={{
            height: 2,
            background: 'rgba(145,115,18,0.85)',
            marginBottom: 28,
            opacity: headerOp,
          }}
        />

        {/* Brahma Muhurtam */}
        <div
          style={{
            position: 'relative',
            background: 'rgba(22, 14, 2, 0.93)',
            border: '3px solid rgba(200, 165, 30, 0.85)',
            borderRadius: 24,
            padding: '30px 34px',
            marginBottom: 22,
            overflow: 'hidden',
            ...card1,
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: 24,
              background: 'radial-gradient(ellipse at 50% 0%, rgba(255,200,30,0.10) 0%, transparent 55%)',
              pointerEvents: 'none',
            }}
          />
          <div
            style={{ fontSize: 50, fontWeight: 'bold', color: GOLD, fontFamily: TELUGU, marginBottom: 10 }}
          >
            బ్రహ్మ ముహూర్తం
          </div>
          <div style={{ height: 1, background: 'rgba(200,165,30,0.3)', marginBottom: 16 }} />
          <div
            style={{ fontSize: 86, fontWeight: 'bold', color: WHITE, fontFamily: LATIN, lineHeight: 1.1 }}
          >
            {data.brahma}
          </div>
          <div
            style={{ fontSize: 40, color: 'rgba(210,210,170,0.9)', marginTop: 14, fontFamily: TELUGU }}
          >
            ప్రార్థన & ధ్యానానికి ఉత్తమ సమయం
          </div>
        </div>

        {/* Abhijit */}
        <div
          style={{
            background: 'rgba(20, 14, 2, 0.90)',
            border: '2px solid rgba(180, 145, 20, 0.72)',
            borderRadius: 20,
            padding: '26px 34px',
            ...card2,
          }}
        >
          <div
            style={{ fontSize: 48, fontWeight: 'bold', color: GOLD, fontFamily: TELUGU, marginBottom: 10 }}
          >
            అభిజిత్ ముహూర్తం
          </div>
          <div style={{ height: 1, background: 'rgba(180,145,20,0.3)', marginBottom: 14 }} />
          <div
            style={{ fontSize: 76, fontWeight: 'bold', color: WHITE, fontFamily: LATIN, lineHeight: 1.1 }}
          >
            {data.abhijit}
          </div>
          <div style={{ fontSize: 38, color: MUTED, marginTop: 10, fontFamily: TELUGU }}>
            ముఖ్య పనులకు అత్యంత శుభ సమయం
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ════════════════════════════════════════════════════════════════════════════
// Scene 3 — Closing
// ════════════════════════════════════════════════════════════════════════════
const ClosingScene: React.FC<{ localFrame: number; data: VideoData }> = ({ localFrame, data }) => {
  const headerOp = interpolate(localFrame, [0, 10], [0, 1], { extrapolateRight: 'clamp' });
  const card1 = useCard(localFrame, 4);
  const card2 = useCard(localFrame, 14);
  const blessing = useCard(localFrame, 26);

  return (
    <AbsoluteFill>
      <div style={{ padding: '130px 60px 0', color: WHITE }}>
        <div
          style={{
            textAlign: 'center',
            fontSize: 72,
            fontWeight: 'bold',
            color: GOLD,
            fontFamily: TELUGU,
            opacity: headerOp,
            marginBottom: 18,
          }}
        >
          సూర్య సమయాలు
        </div>
        <div
          style={{
            height: 2,
            background: 'rgba(145,115,18,0.85)',
            marginBottom: 24,
            opacity: headerOp,
          }}
        />

        {/* Sunrise */}
        <div
          style={{
            background: 'rgba(22, 12, 4, 0.92)',
            border: '2px solid rgba(200, 155, 40, 0.8)',
            borderRadius: 20,
            padding: '22px 30px',
            marginBottom: 18,
            ...card1,
          }}
        >
          <div style={{ fontSize: 46, color: SAFFRON, fontFamily: TELUGU, marginBottom: 8 }}>
            సూర్యోదయం 🌅
          </div>
          <div style={{ fontSize: 80, fontWeight: 'bold', color: WHITE, fontFamily: LATIN }}>
            {data.sunrise}
          </div>
        </div>

        {/* Sunset */}
        <div
          style={{
            background: 'rgba(22, 12, 4, 0.92)',
            border: '2px solid rgba(200, 155, 40, 0.8)',
            borderRadius: 20,
            padding: '22px 30px',
            marginBottom: 28,
            ...card2,
          }}
        >
          <div style={{ fontSize: 46, color: SAFFRON, fontFamily: TELUGU, marginBottom: 8 }}>
            సూర్యాస్తమయం 🌇
          </div>
          <div style={{ fontSize: 80, fontWeight: 'bold', color: WHITE, fontFamily: LATIN }}>
            {data.sunset}
          </div>
        </div>

        {/* Blessing + CTA */}
        <div style={{ textAlign: 'center', ...blessing }}>
          <div
            style={{
              fontSize: 54,
              fontWeight: 'bold',
              color: WHITE,
              fontFamily: TELUGU,
              marginBottom: 6,
            }}
          >
            మీకు శుభమైన రోజు కలగాలని
          </div>
          <div
            style={{
              fontSize: 64,
              fontWeight: 'bold',
              color: GOLD,
              fontFamily: TELUGU,
              marginBottom: 22,
            }}
          >
            ఆశిస్తున్నాము! 🙏
          </div>
          <div style={{ height: 1, background: 'rgba(45,45,45,0.9)', marginBottom: 20 }} />
          <div
            style={{
              fontSize: 46,
              fontWeight: 'bold',
              color: SAFFRON,
              fontFamily: TELUGU,
              marginBottom: 8,
            }}
          >
            Save చేయండి &nbsp;|&nbsp; Share చేయండి
          </div>
          <div style={{ fontSize: 38, color: MUTED, fontFamily: TELUGU, marginBottom: 16 }}>
            Family WhatsApp లో పంచుకోండి
          </div>
          <div style={{ fontSize: 42, fontWeight: 'bold', color: GOLD, fontFamily: LATIN }}>
            @PanthuluPanchangam
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ════════════════════════════════════════════════════════════════════════════
// Main composition
// ════════════════════════════════════════════════════════════════════════════
export const PanchangamVideo: React.FC<VideoData> = (props) => {
  const frame = useCurrentFrame();
  const [fontHandle] = useState(() => delayRender('Loading NotoSansTelugu fonts'));

  useEffect(() => {
    document.fonts.ready.then(() => continueRender(fontHandle));
  }, [fontHandle]);

  // Use measured per-scene frame counts when available (exact sync),
  // otherwise fall back to ratio estimation.
  const audioDurFrames = Math.max(Math.ceil(props.audioDurationSec * 24), 480);
  const SCENE_FRAMES: [number, number, number, number] =
    props.sceneFrames && props.sceneFrames.every((f) => f > 0)
      ? props.sceneFrames
      : (() => {
          // Fallback ratios: intro 24%, bad 19%, good 24%, closing 33%
          // (based on Telugu syllable counts per scene)
          const RATIOS = [0.24, 0.19, 0.24, 0.33];
          const sf = RATIOS.map((r) => Math.round(r * audioDurFrames)) as [number, number, number, number];
          sf[3] += audioDurFrames - sf.reduce((a, b) => a + b, 0);
          return sf;
        })();
  const TOTAL = SCENE_FRAMES.reduce((a, b) => a + b, 0);

  const SCENE_STARTS = SCENE_FRAMES.reduce<number[]>((acc, _, i) => {
    acc.push(i === 0 ? 0 : acc[i - 1] + SCENE_FRAMES[i - 1]);
    return acc;
  }, []);

  const globalFade = interpolate(frame, [TOTAL - 12, TOTAL], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{ background: '#080808', overflow: 'hidden', opacity: globalFade }}>
      {/* Background gradient */}
      <AbsoluteFill
        style={{ background: 'radial-gradient(ellipse at 50% 22%, #0d1b2e 0%, #080808 62%)' }}
      />

      {/* Stars */}
      <Stars />

      {/* Audio track — starts at frame 0, no delay */}
      {props.audioFile ? <Audio src={staticFile(props.audioFile)} startFrom={0} /> : null}

      {/* Scene content — renders BEFORE pandit so pandit covers any overflow */}
      <Sequence from={SCENE_STARTS[0]} durationInFrames={SCENE_FRAMES[0]}>
        <IntroScene localFrame={frame - SCENE_STARTS[0]} data={props} />
      </Sequence>
      <Sequence from={SCENE_STARTS[1]} durationInFrames={SCENE_FRAMES[1]}>
        <BadTimingsScene localFrame={frame - SCENE_STARTS[1]} data={props} />
      </Sequence>
      <Sequence from={SCENE_STARTS[2]} durationInFrames={SCENE_FRAMES[2]}>
        <GoodTimingsScene localFrame={frame - SCENE_STARTS[2]} data={props} />
      </Sequence>
      <Sequence from={SCENE_STARTS[3]} durationInFrames={SCENE_FRAMES[3]}>
        <ClosingScene localFrame={frame - SCENE_STARTS[3]} data={props} />
      </Sequence>

      {/* Pandit character — renders AFTER scene content so it always appears in front */}
      <PanditChar
        opacity={interpolate(frame, [0, 18], [0, 1], { extrapolateRight: 'clamp' })}
        frame={frame}
      />

      {/* Persistent handle on top */}
      <Handle opacity={interpolate(frame, [0, 10], [0, 1], { extrapolateRight: 'clamp' })} />

      {/* Per-scene crossfade overlays */}
      {SCENE_STARTS.map((start, i) => (
        <Sequence key={i} from={start} durationInFrames={SCENE_FRAMES[i]}>
          <FadeOverlay localFrame={frame - start} totalFrames={SCENE_FRAMES[i]} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
