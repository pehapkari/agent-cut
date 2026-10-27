import React from "react";
import {
  BAR,
  Bars,
  C,
  Card,
  Cover,
  ELEPHANT_H,
  ELEPHANT_W,
  Elephant,
  PartnerBadge,
  SpeakerPhoto,
  Text,
  fit,
  MONO,
  type BrandProps,
} from "./kit";

// Every card is a pure function of the data (+ optional animation values),
// so the same code renders video frames, PNG stills and the SVG export.

const W = 1920;
const H = 1080;

// Elephant positions (top-left of the artwork) in the 1920×1080 templates.
export const ELEPHANT = {
  event: { x: 27, y: 879.5, mirror: true }, // white, bottom-left on the bar
  speaker: { x: 1623.71, y: 351.53, mirror: false }, // standing on the panel
  background: { x: 1623.71, y: 864.53, mirror: false }, // standing on the bottom bar
};

const barText = (props: BrandProps, y = 80, opacity = 1) => (
  <Text x={W / 2} y={y} anchor="middle" color={C.white} style={{ opacity }}>
    {props.event.name}
  </Text>
);

// ------------------------------------------------------------------ event card
export type EventAnim = { split?: number; elephant?: React.ReactNode; textOpacity?: number; partner?: number };

// Illustration between the bars, event name on top, elephant bottom-left,
// partner badge bottom-right. `split` 0 = solid panel, 1 = bars in place.
export const EventCard: React.FC<{ readonly props: BrandProps; readonly a?: EventAnim }> = ({ props, a = {} }) => {
  const split = a.split ?? 1;
  const half = H / 2;
  return (
    <Card w={W} h={H} props={props}>
      <Cover file={props.event.image} w={W} h={H} />
      <rect width={W} height={half + (split < 1 ? 1 : 0)} fill={C.bar} transform={`translate(0 ${(BAR - half) * split})`} />
      <rect y={half} width={W} height={half} fill={C.bar} transform={`translate(0 ${(half - BAR) * split})`} />
      {barText(props, 80, a.textOpacity ?? 1)}
      {a.elephant ?? <Elephant {...ELEPHANT.event} />}
      <PartnerBadge partner={props.event.partner} cx={1764} cy={1001} logoDx={9} logoDy={-15.5} scale={a.partner ?? 1} />
    </Card>
  );
};

// ---------------------------------------------------------------- speaker card
// `split` 0 = solid brand panel (two halves meeting in the middle), 1 = the
// halves pulled apart into the bars. `elephant` replaces the standing one.
export type SpeakerAnim = {
  photoDx?: number;
  name?: [number, number];
  title?: [number, number];
  split?: number;
  elephant?: React.ReactNode;
  onPanel?: React.ReactNode; // content riding on the bottom half (partner, event name)
};

export const PHOTO_BOX = { x: 0, y: 540, w: 378, h: 423 };

export const SpeakerCard: React.FC<{ readonly props: BrandProps; readonly a?: SpeakerAnim }> = ({ props, a = {} }) => {
  const [nameO, nameDx] = a.name ?? [1, 0];
  const [titleO, titleDx] = a.title ?? [1, 0];
  const split = a.split ?? 1;
  const half = H / 2;
  return (
    <Card w={W} h={H} props={props}>
      <rect y={half} width={W} height={half} fill={C.panel} />
      <SpeakerPhoto id="speaker" photo={props.talk.photo} {...PHOTO_BOX} dx={a.photoDx ?? 0} />
      <g transform={`translate(${nameDx} 0)`} style={{ opacity: nameO }}>
        <Text x={412.5} y={669} color={C.name}>
          {props.talk.speaker}
        </Text>
      </g>
      <g transform={`translate(${titleDx} 0)`} style={{ opacity: titleO }}>
        <Text x={425.5} y={780} maxWidth={W - 425 - 60} lineHeight={1.2}>
          {props.talk.title}
        </Text>
      </g>
      <rect width={W} height={half + (split < 1 ? 1 : 0)} fill={C.bar} transform={`translate(0 ${(BAR - half) * split})`} />
      <g transform={`translate(0 ${(half - BAR) * split})`}>
        <rect y={half} width={W} height={half} fill={C.bar} />
        {a.onPanel}
        <g style={{ opacity: Math.max(0, (split - 0.85) / 0.15) }}>{barText(props, 1044 - (half - BAR))}</g>
      </g>
      {a.elephant ?? <Elephant {...ELEPHANT.speaker} />}
    </Card>
  );
};

// ------------------------------------------------------- lecture background
// Under the speaker and the slides (10_layout.py) and the end screen.
export const BackgroundCard: React.FC<{
  readonly props: BrandProps;
  readonly slide?: number;
  readonly elephant?: React.ReactNode;
}> = ({ props, slide = 0, elephant }) => (
  <Card w={W} h={H} props={props}>
    <rect y={H / 2} width={W} height={H / 2} fill={C.panel} />
    <Bars
      w={W}
      h={H}
      slide={slide}
      top={barText(props)}
      bottom={
        <Text x={27.7} y={1044} color={C.white}>
          {`://${props.event.url}`}
        </Text>
      }
    />
    {elephant === undefined ? <Elephant {...ELEPHANT.background} /> : elephant}
  </Card>
);

// ---------------------------------------------------------- brand panel
// The solid purple panel that opens and closes every video: elephant in the
// middle, a line of text under it and the partner badge (the event's partner).
export const PANEL_ELEPHANT = { scale: 2, cy: 330 };
export const panelElephant = () => ({
  ...centerOf(PANEL_ELEPHANT.scale, PANEL_ELEPHANT.cy),
  scale: PANEL_ELEPHANT.scale,
  mirror: false,
});
export const PanelPartner: React.FC<{ readonly props: BrandProps; readonly pop?: number; readonly cy?: number }> = ({
  props,
  pop = 1,
  cy = 850,
}) => <PartnerBadge partner={props.event.partner} cx={W / 2} cy={cy} scale={0.7 * pop} />;

// Elephant centered (and enlarged) on the solid panel, for the intro / outro.
export const CENTER_SCALE = 2.2;
export const centerOf = (scale: number, y = H / 2) => ({
  x: W / 2 - (ELEPHANT_W * scale) / 2,
  y: y - (ELEPHANT_H * scale) / 2,
});

// ------------------------------------------------------------ end screen
// Closing: the bars close into the brand panel with a thank-you and the partner.
// `close` 0 = bars in place (background card), 1 = solid panel.
export type EndAnim = { close: number; elephant: React.ReactNode; text: number };

export const ThanksCard: React.FC<{ readonly props: BrandProps; readonly a: EndAnim }> = ({ props, a }) => {
  const half = H / 2;
  return (
    <Card w={W} h={H} props={props}>
      <rect y={half} width={W} height={half} fill={C.panel} />
      <rect width={W} height={half + (a.close > 0 ? 1 : 0)} fill={C.bar} transform={`translate(0 ${(BAR - half) * (1 - a.close)})`} />
      <rect y={half} width={W} height={half} fill={C.bar} transform={`translate(0 ${(half - BAR) * (1 - a.close)})`} />
      {a.elephant}
      <g style={{ opacity: a.text }}>
        <Text x={W / 2} y={640} anchor="middle" size={84} color={C.white}>
          Díky za sledování!
        </Text>
        <Text x={W / 2} y={712} anchor="middle" size={44} color={C.panel}>
          {`Podpořit nás můžete na ${props.event.url}`}
        </Text>
        <PanelPartner props={props} cy={880} />
      </g>
    </Card>
  );
};

// ------------------------------------------------------------ thumbnails 1280×720
const TW = 1280;
const TH = 720;

// A: speaker photo on the left, big title on the right.
export const ThumbnailA: React.FC<{ readonly props: BrandProps }> = ({ props }) => {
  const t = fit(props.metrics, props.talk.title, TW - 550 - 50, 4, [96, 88, 80, 72, 64, 56], TH - 90 - 150 - 20);
  return (
    <Card w={TW} h={TH} props={props}>
      <rect width={TW} height={TH} fill={C.panel} />
      <SpeakerPhoto id="thumb-a" photo={props.talk.photo} x={0} y={0} w={500} h={TH - 90} faceShare={0.38} />
      <Text x={550} y={130} size={44} color={C.name}>
        {props.talk.speaker}
      </Text>
      <Text x={550} y={140 + t.size * 1.1} size={t.size} lineHeight={1.1}>
        {t.lines.join("\n")}
      </Text>
      <rect y={TH - 90} width={TW} height={90} fill={C.bar} />
      <Text x={40} y={TH - 30} size={44} color={C.white}>
        {props.event.name}
      </Text>
      <Elephant x={TW - 40 - ELEPHANT_W * 0.55} y={TH - 90 - ELEPHANT_H * 0.55} scale={0.55} />
    </Card>
  );
};

// B: event illustration with a round speaker photo and the title on a panel strip.
export const ThumbnailB: React.FC<{ readonly props: BrandProps }> = ({ props }) => {
  const t = fit(props.metrics, props.talk.title, TW - 440 - 50, 3, [80, 72, 64, 56, 48], 320 - 80 - 20);
  return (
    <Card w={TW} h={TH} props={props}>
      <Cover file={props.event.image} w={TW} h={TH} />
      <rect y={TH - 320} width={TW} height={320} fill={C.panel} />
      <SpeakerPhoto id="thumb-b" photo={props.talk.photo} x={60} y={TH - 320 - 170} w={340} h={340} round faceShare={0.42} />
      <Text x={440} y={TH - 320 + 70} size={40} color={C.name}>
        {props.talk.speaker}
      </Text>
      <Text x={440} y={TH - 320 + 80 + t.size * 1.1} size={t.size} lineHeight={1.1}>
        {t.lines.join("\n")}
      </Text>
    </Card>
  );
};

// ------------------------------------------------------------ Instagram 1080×1080
const IG = 1080;

export const InstagramSpeaker: React.FC<{ readonly props: BrandProps }> = ({ props }) => {
  const t = fit(props.metrics, props.talk.title, IG - 140, 3, [60, 54, 48], 200, 1.15);
  const abstractY = 600 + (t.lines.length - 1) * t.size * 1.15 + 100;
  return (
    <Card w={IG} h={IG} props={props}>
      <rect width={IG} height={423} fill={C.panel} />
      <SpeakerPhoto id="ig-speaker" photo={props.talk.photo} x={0} y={0} w={377} h={423} />
      <Text x={438} y={108} color={C.name}>
        {props.talk.speaker}
      </Text>
      <PartnerBadge partner={props.event.partner} cx={910} cy={377} logoW={266} logoH={66} />
      <rect y={423} width={IG} height={IG - 423} fill={C.white} />
      <Text x={70} y={600} size={t.size} lineHeight={1.15}>
        {t.lines.join("\n")}
      </Text>
      <Text x={70} y={abstractY} size={34} lineHeight={1.45} maxWidth={IG - 140} family={MONO}>
        {props.talk.abstract}
      </Text>
      <Elephant x={1060 - ELEPHANT_W * 0.38} y={1048 - ELEPHANT_H * 0.38} scale={0.38} />
    </Card>
  );
};

export const InstagramEvent: React.FC<{ readonly props: BrandProps }> = ({ props }) => {
  const n = props.talks.length;
  const r = 88;
  const gap = 195.5;
  const x0 = IG / 2 - ((n - 1) * gap) / 2;
  return (
    <Card w={IG} h={IG} props={props}>
      <Cover file={props.event.image} w={IG} h={IG} />
      <PartnerBadge partner={props.event.partner} cx={927} cy={206} logoW={266} logoH={66} />
      {props.talks.map((t, i) => (
        <SpeakerPhoto
          key={i}
          id={`ig-event-${i}`}
          photo={t.photo}
          x={x0 + i * gap - r}
          y={851 - r}
          w={2 * r}
          h={2 * r}
          round
          faceShare={0.45}
        />
      ))}
      <Bars
        w={IG}
        h={IG}
        top={
          <Text x={IG / 2} y={80} anchor="middle" color={C.white}>
            {props.event.name}
          </Text>
        }
        bottom={
          <Text x={1050} y={1012} anchor="end" size={44} color={C.white} lineHeight={1.0}>
            {`${props.event.when}\n${props.event.where}`}
          </Text>
        }
      />
      <Elephant x={27} y={879.5} mirror />
    </Card>
  );
};

// Social post for one point of the talk: a frame of the speaker saying it,
// the line itself, the speaker and the event on the bar (13_publish.py social).
export const InstagramQuote: React.FC<{ readonly props: BrandProps }> = ({ props }) => {
  const photoH = 540;
  const q = fit(props.metrics, `„${props.quote?.text ?? props.talk.title}“`, IG - 140, 4, [88, 80, 72, 64, 56, 50, 44], 300, 1.2);
  const top = photoH + (IG - BAR - photoH - q.lines.length * q.size * 1.2) / 2 + q.size * 0.85;
  return (
    <Card w={IG} h={IG} props={props}>
      <SpeakerPhoto id="ig-quote" photo={props.quote?.photo ?? props.talk.photo} x={0} y={0} w={IG} h={photoH} faceShare={0.4} />
      <PartnerBadge partner={props.event.partner} cx={1000} cy={60} scale={0.62} logoDx={-40} logoDy={20} />
      <Text x={70} y={top} size={q.size} lineHeight={1.2}>
        {q.lines.join("\n")}
      </Text>
      <rect y={IG - BAR} width={IG} height={BAR} fill={C.bar} />
      <Text x={50} y={IG - BAR + 74} size={40} color={C.white}>
        {`${props.talk.speaker} · ${props.event.name}`}
      </Text>
      <Elephant x={IG - 30 - ELEPHANT_W * 0.6} y={IG - BAR + 22 - ELEPHANT_H * 0.6} scale={0.6} />
    </Card>
  );
};
