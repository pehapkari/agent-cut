import { Composition, Folder } from "remotion";
import { brandProps, still } from "./Brand";
import {
  BackgroundCard,
  EventCard,
  InstagramEvent,
  InstagramQuote,
  InstagramSpeaker,
  SpeakerCard,
  ThumbnailA,
  ThumbnailB,
} from "./brand/cards";
import { Intro, INTRO_FRAMES, Outro, OUTRO_FRAMES, Teaser, teaserFrames } from "./Intro";

// Ids of the still compositions are the output file names (11_brand.py).
const STILLS = [
  { id: "event-card", card: EventCard, w: 1920, h: 1080 },
  { id: "speaker-card", card: SpeakerCard, w: 1920, h: 1080 },
  { id: "video-background", card: BackgroundCard, w: 1920, h: 1080 },
  { id: "youtube-thumbnail-a", card: ThumbnailA, w: 1280, h: 720 },
  { id: "youtube-thumbnail-b", card: ThumbnailB, w: 1280, h: 720 },
  { id: "instagram-speaker", card: InstagramSpeaker, w: 1080, h: 1080 },
  { id: "instagram-event", card: InstagramEvent, w: 1080, h: 1080 },
  { id: "instagram-quote", card: InstagramQuote, w: 1080, h: 1080 }, // 13_publish.py, one per post
];

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Intro" component={Intro} durationInFrames={INTRO_FRAMES} fps={30} width={1920} height={1080} />
    <Composition id="Outro" component={Outro} durationInFrames={OUTRO_FRAMES} fps={30} width={1920} height={1080} />
    <Composition
      id="Teaser"
      component={Teaser}
      durationInFrames={1}
      fps={30}
      width={1920}
      height={1080}
      calculateMetadata={() => ({ durationInFrames: teaserFrames(brandProps().teaser ?? []) })}
    />
    <Folder name="Stills">
      {STILLS.map((s) => (
        <Composition
          key={s.id}
          id={s.id}
          component={still(s.card)}
          durationInFrames={1}
          fps={30}
          width={s.w}
          height={s.h}
        />
      ))}
    </Folder>
  </>
);
