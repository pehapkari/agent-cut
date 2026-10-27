import { Audio, Video } from "@remotion/media";
import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  Sequence,
  Series,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { BrandRoot, brandProps } from "./Brand";
import {
  BackgroundCard,
  ELEPHANT,
  panelElephant,
  PanelPartner,
  SpeakerCard,
  ThanksCard,
} from "./brand/cards";
import { BAR, Bars, C, Card, ELEPHANT_H, ELEPHANT_W, Elephant, Text, fit, type BrandProps, type TeaserClip } from "./brand/kit";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const ease = { ...clamp, easing: Easing.inOut(Easing.cubic) };
const out = { ...clamp, easing: Easing.bezier(0.16, 1, 0.3, 1) };
const pop = { ...clamp, easing: Easing.bezier(0.34, 1.56, 0.64, 1) };

const lerp = (t: number, a: number, b: number) => a + (b - a) * t;
type Place = { x: number; y: number; scale: number; mirror: boolean };
const at = (p: { x: number; y: number; mirror: boolean }): Place => ({ ...p, scale: 1 });

// Elephant between two placements, t 0 → 1.
const MovingElephant = ({ t, from, to }: { readonly t: number; readonly from: Place; readonly to: Place }) => (
  <Elephant
    x={lerp(t, from.x, to.x)}
    y={lerp(t, from.y, to.y)}
    scale={lerp(t, from.scale, to.scale)}
    mirror={t < 0.5 ? from.mirror : to.mirror}
  />
);

// ------------------------------------------------------------------ intro
// Short sting (algorithms punish long intros): brand panel with the elephant
// and the partner → the panel splits into the speaker card → lecture background.
export const OPEN = 120; // panel + speaker card
export const BACKGROUND = 45;
export const INTRO_FRAMES = OPEN + BACKGROUND; // 165 = 5.5 s at 30 fps

const OpenScene = ({ props }: { readonly props: BrandProps }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [30, 54], [0, 1], ease);
  return (
    <SpeakerCard
      props={props}
      a={{
        split: p,
        elephant: <MovingElephant t={p} from={panelElephant()} to={at(ELEPHANT.speaker)} />,
        onPanel: (
          <>
            <Text x={960} y={640} anchor="middle" color={C.white} style={{ opacity: Math.min(interpolate(frame, [0, 8], [0, 1], clamp), interpolate(p, [0, 0.3], [1, 0], clamp)) }}>
              {props.event.name}
            </Text>
            <PanelPartner props={props} pop={interpolate(frame, [4, 16], [0, 1], pop)} />
          </>
        ),
        photoDx: interpolate(frame, [46, 64], [-440, 0], out),
        name: [interpolate(frame, [52, 64], [0, 1], clamp), interpolate(frame, [52, 67], [60, 0], out)],
        title: [interpolate(frame, [58, 70], [0, 1], clamp), interpolate(frame, [58, 73], [60, 0], out)],
      }}
    />
  );
};

// Card bars slide out, background bars slide in, the elephant slides down.
// Ends on exactly the frame the lecture layout (10_layout.py) starts on.
const ToBackground = ({ props }: { readonly props: BrandProps }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const half = 0.3 * fps;
  const slide =
    frame < half
      ? interpolate(frame, [0, half], [0, 1], ease)
      : interpolate(frame, [half, 2 * half], [1, 0], ease);
  const t = interpolate(frame, [0, 2 * half], [0, 1], ease);
  const elephant = <MovingElephant t={t} from={at(ELEPHANT.speaker)} to={at(ELEPHANT.background)} />;
  if (frame >= half) return <BackgroundCard props={props} slide={slide} elephant={elephant} />;
  // first half: the speaker card's bars (event name at the bottom) leave
  return (
    <Card w={1920} h={1080} props={props}>
      <rect y={540} width={1920} height={540} fill={C.panel} />
      <Bars
        w={1920}
        h={1080}
        slide={slide}
        bottom={
          <Text x={960} y={1044} anchor="middle" color={C.white}>
            {props.event.name}
          </Text>
        }
      />
      {elephant}
    </Card>
  );
};

const Music = ({ file }: { readonly file: string }) => {
  const { fps, durationInFrames } = useVideoConfig();
  return (
    <Audio
      name="Music"
      src={staticFile(file)}
      volume={(f) =>
        interpolate(f, [0, 10, durationInFrames - 1.5 * fps, durationInFrames], [0, 1, 1, 0], clamp)
      }
    />
  );
};

export const Intro = () => {
  const props = brandProps();
  return (
    <BrandRoot>
      <Series>
        <Series.Sequence name="Open" durationInFrames={OPEN}>
          <OpenScene props={props} />
        </Series.Sequence>
        <Series.Sequence name="Background" durationInFrames={BACKGROUND}>
          <ToBackground props={props} />
        </Series.Sequence>
      </Series>
      {props.music ? <Music file={props.music} /> : null}
    </BrandRoot>
  );
};

// ------------------------------------------------------------------ outro
// From the lecture background the bars close into the brand panel: elephant,
// thank-you and the partner; then the panel opens again onto the empty
// background, held long enough for YouTube end-screen cards (≥ 5 s).
export const CLOSE = 27;
export const THANKS = 90;
export const OPEN_END = 27;
export const END_SCREEN = 171; // 5.7 s
export const OUTRO_FRAMES = CLOSE + THANKS + OPEN_END + END_SCREEN; // 315 = 10.5 s

const ThanksScene = ({ props }: { readonly props: BrandProps }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const closing = interpolate(frame, [0, CLOSE], [0, 1], ease);
  const opening = interpolate(frame, [CLOSE + THANKS, CLOSE + THANKS + OPEN_END], [0, 1], ease);
  const close = closing * (1 - opening);
  const mid = panelElephant();
  const elephant =
    opening > 0 ? (
      <MovingElephant t={opening} from={mid} to={at(ELEPHANT.background)} />
    ) : (
      <MovingElephant t={closing} from={at(ELEPHANT.background)} to={mid} />
    );
  const text =
    interpolate(frame, [CLOSE, CLOSE + 0.5 * fps], [0, 1], clamp) *
    interpolate(frame, [CLOSE + THANKS, CLOSE + THANKS + 0.2 * fps], [1, 0], clamp);
  // bar texts belong to the background card: fade out while closing, back in while opening
  return (
    <>
      <ThanksCard props={props} a={{ close, elephant, text }} />
      <svg width={1920} height={1080} style={{ position: "absolute", left: 0, top: 0, opacity: 1 - close }}>
        <Text x={960} y={80} anchor="middle" color={C.white}>
          {props.event.name}
        </Text>
        <Text x={27.7} y={1044} color={C.white}>
          {`://${props.event.url}`}
        </Text>
      </svg>
    </>
  );
};

export const Outro = () => {
  const props = brandProps();
  return (
    <BrandRoot>
      <Series>
        <Series.Sequence name="Thanks" durationInFrames={CLOSE + THANKS + OPEN_END}>
          <ThanksScene props={props} />
        </Series.Sequence>
        <Series.Sequence name="End screen" durationInFrames={END_SCREEN}>
          <BackgroundCard props={props} />
        </Series.Sequence>
      </Series>
    </BrandRoot>
  );
};

// ------------------------------------------------------------------ teaser
// Cold open: a few short punchy lines from the talk. Bars twice as tall as in
// the talk: on top "V této epizodě uvidíte" and a full-width progress bar, at
// the bottom the line; slide and speaker in between, a big elephant in front.
// Each new line is wiped in by a bar sweeping up the frame (clips overlap by
// WIPE frames). At the end the bars close into the brand panel – exactly the
// first frame of the intro, so the two run as one.
export const WIPE = 8;
export const CLOSE_TEASER = 15; // = TEASER_CLOSE in 11_brand.py
const AUDIO_FADE = 3;
const TBAR = 2 * BAR; // = TEASER_BAR in 11_brand.py
const GAP = 48; // = TEASER_GAP in 11_brand.py
const TEASER_ELEPHANT = { scale: 1.5, mirror: false, x: 1920 - 40 - ELEPHANT_W * 1.5, y: 1080 - TBAR + 30 - ELEPHANT_H * 1.5 };

export const teaserFrames = (clips: TeaserClip[]) =>
  Math.max(1, clips.reduce((n, c) => n + c.frames, 0) - WIPE * Math.max(0, clips.length - 1));

const clipStarts = (clips: TeaserClip[]) => {
  let at = 0;
  return clips.map((c) => {
    const from = at;
    at += c.frames - WIPE;
    return from;
  });
};

const Layer = ({ children }: { readonly children: React.ReactNode }) => (
  <svg width={1920} height={1080} style={{ position: "absolute", left: 0, top: 0 }}>
    {children}
  </svg>
);

// The line on the bottom bar, as large as fits on one or two lines.
const Quote = ({ props, text }: { readonly props: BrandProps; readonly text: string }) => {
  const t = fit(props.metrics, text, 1760, 2, [80, 72, 64, 56], Infinity, 1.15);
  const mid = 1080 - TBAR / 2;
  const first = mid - ((t.lines.length - 1) * t.size * 1.15) / 2 + 0.35 * t.size;
  return (
    <>
      <rect y={1080 - TBAR} width={1920} height={TBAR} fill={C.bar} />
      <Text x={960} y={first} anchor="middle" size={t.size} lineHeight={1.15} color={C.white}>
        {t.lines.join("\n")}
      </Text>
    </>
  );
};

// Slide and speaker side by side, centred between the bars, framed like the talk layout.
const Clip = ({
  props,
  clip,
  wipeIn,
  last,
}: {
  readonly props: BrandProps;
  readonly clip: TeaserClip;
  readonly wipeIn: boolean;
  readonly last: boolean;
}) => {
  const frame = useCurrentFrame();
  const y = wipeIn ? interpolate(frame, [0, WIPE], [1080, -TBAR], ease) : -TBAR;
  // the sound ends with the line; the padded tail only carries the picture
  const end = clip.frames - (last ? CLOSE_TEASER : WIPE);
  const vol = (f: number) =>
    Math.min(
      wipeIn ? interpolate(f, [0, AUDIO_FADE], [0, 1], clamp) : 1,
      interpolate(f, [end, end + AUDIO_FADE], [1, 0], clamp),
    );
  const [sw, sh] = clip.screenSize;
  const hs = clip.headSize;
  const sx = (1920 - sw - GAP - hs) / 2;
  const hx = sx + sw + GAP;
  const box = (x: number, top: number, w: number, h: number) => (
    <rect x={x - 1.5} y={top - 1.5} width={w + 3} height={h + 3} fill="none" stroke={C.bar} strokeWidth={3} />
  );
  return (
    <AbsoluteFill style={{ clipPath: `inset(${Math.max(0, y + TBAR)}px 0 0 0)` }}>
      <Video src={staticFile(clip.screen)} muted style={{ position: "absolute", left: sx, top: 540 - sh / 2, width: sw, height: sh }} />
      <Video src={staticFile(clip.head)} volume={vol} style={{ position: "absolute", left: hx, top: 540 - hs / 2, width: hs, height: hs }} />
      <Layer>
        {box(sx, 540 - sh / 2, sw, sh)}
        {box(hx, 540 - hs / 2, hs, hs)}
        <Quote props={props} text={clip.text} />
      </Layer>
    </AbsoluteFill>
  );
};

const Sweep = () => {
  const frame = useCurrentFrame();
  const y = interpolate(frame, [0, WIPE], [1080, -TBAR], ease);
  return (
    <Layer>
      <rect y={y} width={1920} height={TBAR} fill={C.bar} />
    </Layer>
  );
};

// Top bar: the label, and under it one segment per line across the full width,
// filling up as the lines play.
const TopBar = ({ clips, opacity }: { readonly clips: TeaserClip[]; readonly opacity: number }) => {
  const frame = useCurrentFrame();
  const starts = clipStarts(clips);
  const gap = 16;
  const x0 = 60;
  const seg = (1920 - 2 * x0 - (clips.length - 1) * gap) / clips.length;
  return (
    <Layer>
      <rect width={1920} height={TBAR} fill={C.bar} />
      <g style={{ opacity }}>
        <Text x={960} y={120} anchor="middle" size={88} color={C.white}>
          V této epizodě uvidíte
        </Text>
        {clips.map((c, i) => {
          const shown = c.frames - (i < clips.length - 1 ? WIPE : CLOSE_TEASER);
          const p = interpolate(frame, [starts[i], starts[i] + shown], [0, 1], clamp);
          const x = x0 + i * (seg + gap);
          return (
            <g key={i}>
              <rect x={x} y={170} width={seg} height={10} fill={C.white} opacity={0.3} />
              <rect x={x} y={170} width={seg * p} height={10} fill={C.white} />
            </g>
          );
        })}
      </g>
    </Layer>
  );
};

// The bars close into the solid brand panel, the elephant walks to its centre.
// (No Card: its white ground would hide the last line under the closing bars.)
const Close = () => {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [0, CLOSE_TEASER], [0, 1], ease);
  const half = 540;
  return (
    <Layer>
      <rect width={1920} height={half + 1} fill={C.bar} transform={`translate(0 ${(TBAR - half) * (1 - t)})`} />
      <rect y={half - 1} width={1920} height={half + 1} fill={C.bar} transform={`translate(0 ${(half - TBAR) * (1 - t)})`} />
      <MovingElephant t={t} from={TEASER_ELEPHANT} to={panelElephant()} />
    </Layer>
  );
};

export const Teaser = () => {
  const props = brandProps();
  const clips = props.teaser ?? [];
  const frame = useCurrentFrame();
  const starts = clipStarts(clips);
  const closeAt = teaserFrames(clips) - CLOSE_TEASER;
  return (
    <BrandRoot>
      <AbsoluteFill>
        <Card w={1920} h={1080} props={props}>
          <rect y={540} width={1920} height={540} fill={C.panel} />
        </Card>
        {clips.map((c, i) => (
          <React.Fragment key={c.head}>
            <Sequence from={starts[i]} durationInFrames={c.frames} name={c.text}>
              <Clip props={props} clip={c} wipeIn={i > 0} last={i === clips.length - 1} />
            </Sequence>
            {i > 0 ? (
              <Sequence from={starts[i]} durationInFrames={WIPE} name="wipe">
                <Sweep />
              </Sequence>
            ) : null}
          </React.Fragment>
        ))}
        <TopBar clips={clips} opacity={interpolate(frame, [closeAt, closeAt + 6], [1, 0], clamp)} />
        {frame < closeAt ? (
          <Layer>
            <Elephant {...TEASER_ELEPHANT} />
          </Layer>
        ) : null}
        <Sequence from={closeAt} name="close">
          <Close />
        </Sequence>
      </AbsoluteFill>
    </BrandRoot>
  );
};
