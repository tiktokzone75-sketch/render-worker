import React from 'react';
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  Img,
  interpolate,
} from 'remotion';

export interface Caption {
  text: string;
  start: number;
  end: number;
}

export interface IntroCard {
  enabled: boolean;
  theme: 'light' | 'dark';
  isRTL: boolean;
  avatarUrl: string;
  username: string;
  postText: string;
}

export interface RedditStoryProps {
  backgroundVideoUrl: string;
  audioUrl: string;
  captions: Caption[];
  introCard: IntroCard | null;
}

const CARD_DURATION_SEC = 5;

function IntroCardOverlay({card}: {card: IntroCard}) {
  const isDark = card.theme === 'dark';
  const colors = isDark
    ? {bg: '#1a1a1b', border: '#343536', text: '#d7dadc', sub: '#818384', pill: '#272729'}
    : {bg: '#ffffff', border: '#cccccc', text: '#1c1c1c', sub: '#787c7e', pill: '#f6f7f8'};

  return (
    <AbsoluteFill
      style={{
        alignItems: 'center',
        justifyContent: 'center',
        direction: card.isRTL ? 'rtl' : 'ltr',
      }}
    >
      <div
        style={{
          width: '88%',
          background: colors.bg,
          border: `2px solid ${colors.border}`,
          borderRadius: 26,
          padding: 40,
          boxShadow: '0 10px 30px rgba(0,0,0,.35)',
          fontFamily: 'Tajawal, Cairo, sans-serif',
        }}
      >
        <div style={{display: 'flex', alignItems: 'center', gap: 20, marginBottom: 26}}>
          <div
            style={{
              width: 76,
              height: 76,
              borderRadius: '50%',
              overflow: 'hidden',
              flexShrink: 0,
              background: '#e2e2e2',
            }}
          >
            {card.avatarUrl && (
              <Img src={card.avatarUrl} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
            )}
          </div>
          <div style={{fontSize: 32, fontWeight: 700, color: colors.text}}>
            {card.username || 'u/ThrowAwayStory'}
          </div>
        </div>

        <div style={{fontSize: 34, fontWeight: 600, color: colors.text, lineHeight: 1.5, marginBottom: 20}}>
          {card.postText}
        </div>

        <div style={{display: 'flex', gap: 10}}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: colors.pill,
              borderRadius: 27,
              padding: '13px 20px',
              color: colors.sub,
              fontSize: 26,
              fontWeight: 700,
            }}
          >
            ❤️ 2.4K
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: colors.pill,
              borderRadius: 27,
              padding: '13px 20px',
              color: colors.sub,
              fontSize: 26,
              fontWeight: 700,
            }}
          >
            💬 84
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

function CaptionOverlay({captions}: {captions: Caption[]}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const currentTimeSec = frame / fps;

  const active = captions.find((c) => currentTimeSec >= c.start && currentTimeSec < c.end);
  if (!active) return null;

  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'flex-end', paddingBottom: 220}}>
      <div
        style={{
          fontFamily: 'Tajawal, Cairo, sans-serif',
          fontSize: 46,
          fontWeight: 700,
          color: '#fff',
          textAlign: 'center',
          WebkitTextStroke: '2px black',
          padding: '0 60px',
          lineHeight: 1.4,
        }}
      >
        {active.text}
      </div>
    </AbsoluteFill>
  );
}

export const RedditStory: React.FC<RedditStoryProps> = ({
  backgroundVideoUrl,
  audioUrl,
  captions,
  introCard,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const currentTimeSec = frame / fps;

  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <OffthreadVideo
        src={backgroundVideoUrl}
        style={{width: '100%', height: '100%', objectFit: 'cover'}}
        muted
        loop
      />
      <Audio src={audioUrl} />
      <CaptionOverlay captions={captions} />
      {introCard && introCard.enabled && currentTimeSec < CARD_DURATION_SEC && (
        <IntroCardOverlay card={introCard} />
      )}
    </AbsoluteFill>
  );
};
