import React from 'react';
import {Composition} from 'remotion';
import {RedditStory} from './RedditStory';

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="RedditStory"
      component={RedditStory}
      durationInFrames={30 * 60}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        backgroundVideoUrl: '',
        audioUrl: '',
        captions: [],
        introCard: null,
      }}
    />
  );
};
