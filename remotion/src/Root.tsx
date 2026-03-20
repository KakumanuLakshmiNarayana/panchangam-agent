import React from 'react';
import { Composition } from 'remotion';
import { PanchangamVideo, VideoData, defaultVideoData } from './PanchangamVideo';

export const Root: React.FC = () => {
  return (
    <Composition
      id="PanchangamVideo"
      component={PanchangamVideo}
      durationInFrames={480}
      fps={24}
      width={1080}
      height={1920}
      defaultProps={defaultVideoData}
      calculateMetadata={({ props }) => ({
        durationInFrames: Math.max(Math.ceil((props as VideoData).audioDurationSec * 24), 480),
      })}
    />
  );
};
