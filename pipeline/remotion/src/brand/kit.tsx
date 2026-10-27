import React, { createContext, useContext } from "react";
import { ELEPHANT_EYE, ELEPHANT_FACETS, ELEPHANT_ORIGIN, ELEPHANT_SIZE } from "./elephant-paths";

// Brand kit: colors, sizes and the pieces every template is built from.
// Everything is plain SVG so a card renders the same in Remotion (video,
// PNG stills) and in the static SVG export (pipeline/11_brand.py svg).

export const C = {
  bar: "#4F5B93",
  ink: "#4E5A95", // elephant lines, photo tint
  panel: "#C5CFFF",
  name: "#4F5B93",
  title: "#141F51",
  white: "#FFFFFF",
};
export const BAR = 117;
export const FONT = "Hagrid";
// The trial Hagrid has no digits (they draw a "TRIAL" watermark), so the font
// face skips them (UNICODE_RANGE) and digits fall back to a similar sans.
// With the licensed font: drop UNICODE_RANGE and the fallback.
export const UNICODE_RANGE = "U+0-2F, U+3A-B1, U+B4-B8, U+BA-BB, U+BF-65F, U+66A-6EF, U+6FA-2043, U+2045-2073, U+2075-10FFFF";
export const FAMILY = `${FONT}, "Avenir Next", sans-serif`;
export const MONO = `Menlo, monospace`; // abstract on the Instagram post (TODO: the font from the design)
export const TEXT = 60;
export const TRACKING = 0.9; // px of letter spacing at 60 px (matches the Figma exports)

// ---------------------------------------------------------------- data
export type Face = { x: number; y: number; w: number; h: number }; // normalized 0–1
export type Photo = { file: string; w: number; h: number; face: Face | null };
export type Talk = {
  speaker: string;
  title: string;
  abstract: string;
  photo: Photo | null;
};
export type Event = {
  name: string; // "pražský sraz přátel PHP"
  number: number;
  when: string; // "středa 30. září"
  where: string; // "od 18:00 v Impact Hub"
  url: string;
  image: string | null;
  partner: { name: string; logo: string | null } | null;
};
// One teaser line (11_brand.py teaser): screen and head videos, padded past the
// spoken words by the transition into the next line (or into the sting).
export type TeaserClip = {
  screen: string;
  head: string;
  frames: number;
  text: string;
  screenSize: [number, number];
  headSize: number;
};

export type BrandProps = {
  event: Event;
  talk: Talk;
  talks: Talk[];
  metrics: Record<string, number>; // Hagrid advance widths per 1000 units
  music: string | null;
  teaser?: TeaserClip[]; // cold-open clips (11_brand.py teaser)
  quote?: { text: string; photo: Photo | null }; // one social post (13_publish.py social)
};

export const sampleProps: BrandProps = {
  event: {
    name: "pražský sraz přátel PHP",
    number: 0,
    when: "středa 1. ledna",
    where: "od 18:00",
    url: "pehapkari.cz",
    image: null,
    partner: null,
  },
  talk: { speaker: "Jméno Řečníka", title: "Název přednášky", abstract: "", photo: null },
  talks: [],
  metrics: {},
  music: null,
};

// Asset files are resolved by the host: staticFile() in Remotion, data URIs in the SVG export.
export const AssetUrl = createContext<(file: string) => string>((f) => f);
export const useAsset = () => useContext(AssetUrl);

// ---------------------------------------------------------------- text
export const Metrics = createContext<Record<string, number>>({});

// Greedy word wrap with Hagrid advance widths (unknown glyphs ≈ 0.55 em).
export const wrap = (
  metrics: Record<string, number>,
  text: string,
  size: number,
  maxWidth: number,
): string[] => {
  const lines: string[] = [];
  let line = "";
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const next = line ? `${line} ${word}` : word;
    if (line && width(metrics, next, size) > maxWidth) {
      lines.push(line);
      line = word;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);
  return lines;
};

// Largest size (from `sizes`) at which the text wraps into ≤ maxLines lines
// and no single word overflows.
export const fit = (
  metrics: Record<string, number>,
  text: string,
  maxWidth: number,
  maxLines: number,
  sizes: number[],
  maxHeight = Infinity, // of the whole block: lines × size × lineHeight
  lineHeight = 1.1,
): { size: number; lines: string[] } => {
  for (const size of sizes) {
    const lines = wrap(metrics, text, size, maxWidth);
    const longest = Math.max(...text.split(/\s+/).map((w) => width(metrics, w, size)));
    const fits = lines.length <= maxLines && longest <= maxWidth && lines.length * size * lineHeight <= maxHeight;
    if (fits) return { size, lines };
  }
  const size = sizes[sizes.length - 1];
  return { size, lines: wrap(metrics, text, size, maxWidth) };
};

// Text width in px; an empty metrics table means the monospace font (0.6 em, no tracking).
export const width = (metrics: Record<string, number>, s: string, size: number) =>
  Object.keys(metrics).length === 0
    ? s.length * 0.6 * size
    : [...s].reduce((w, ch) => w + ((metrics[ch] ?? 550) / 1000) * size + (TRACKING * size) / TEXT, 0);

export const useMetrics = () => useContext(Metrics);

export const Text: React.FC<{
  readonly x: number;
  readonly y: number; // baseline of the first line
  readonly children: string;
  readonly size?: number;
  readonly color?: string;
  readonly anchor?: "start" | "middle" | "end";
  readonly maxWidth?: number;
  readonly lineHeight?: number;
  readonly family?: string;
  readonly style?: React.CSSProperties;
}> = ({ x, y, children, size = TEXT, color = C.title, anchor = "start", maxWidth, lineHeight = 1.25, family = FAMILY, style }) => {
  const metrics = useContext(Metrics);
  const lines = maxWidth ? wrap(family === MONO ? {} : metrics, children, size, maxWidth) : children.split("\n");
  return (
    <text
      x={x}
      y={y}
      fontFamily={family}
      fontSize={size}
      fill={color}
      textAnchor={anchor}
      letterSpacing={family === FAMILY ? (TRACKING * size) / TEXT : 0}
      style={style}
    >
      {lines.map((l, i) => (
        <tspan key={i} x={x} dy={i === 0 ? 0 : size * lineHeight}>
          {l}
        </tspan>
      ))}
    </text>
  );
};

// ---------------------------------------------------------------- shapes
// The origami elephant, top-left of its artwork at (x, y).
export const Elephant: React.FC<{
  readonly x: number;
  readonly y: number;
  readonly scale?: number;
  readonly mirror?: boolean;
  readonly style?: React.CSSProperties;
}> = ({ x, y, scale = 1, mirror = false, style }) => {
  const [ox, oy] = ELEPHANT_ORIGIN;
  const [w] = ELEPHANT_SIZE;
  const flip = mirror ? `translate(${w * scale} 0) scale(-1 1)` : "";
  return (
    <g transform={`translate(${x} ${y}) ${flip} scale(${scale}) translate(${-ox} ${-oy})`} style={style}>
      {ELEPHANT_FACETS.map((d, i) => (
        <path
          key={i}
          d={d}
          fill={C.white}
          fillRule="evenodd"
          stroke={C.ink}
          strokeWidth={2}
          strokeMiterlimit={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}
      <path d={ELEPHANT_EYE} fill={C.ink} />
    </g>
  );
};
export const ELEPHANT_W = ELEPHANT_SIZE[0];
export const ELEPHANT_H = ELEPHANT_SIZE[1];

// Top and bottom brand bars with optional centered / custom text.
// `slide` 0 = in place, 1 = off-frame.
export const Bars: React.FC<{
  readonly w: number;
  readonly h: number;
  readonly top?: React.ReactNode;
  readonly bottom?: React.ReactNode;
  readonly slide?: number;
}> = ({ w, h, top, bottom, slide = 0 }) => (
  <>
    <g transform={`translate(0 ${-(BAR + 3) * slide})`}>
      <rect width={w} height={BAR} fill={C.bar} />
      {top}
    </g>
    <g transform={`translate(0 ${(BAR + 3) * slide})`}>
      <rect y={h - BAR} width={w} height={BAR} fill={C.bar} />
      {bottom}
    </g>
  </>
);

// Window crop of a photo: cover the window, keep the face in view.
// Face centre lands at 45 % of the window height, face height ≈ `faceShare` of it.
const crop = (p: Photo, ww: number, wh: number, faceShare: number) => {
  const f = p.face ?? { x: 0.35, y: 0.2, w: 0.3, h: 0.3 };
  let scale = Math.max(ww / p.w, wh / p.h); // cover
  scale = Math.max(scale, (faceShare * wh) / (f.h * p.h));
  const iw = p.w * scale;
  const ih = p.h * scale;
  const cx = (f.x + f.w / 2) * iw;
  const cy = (f.y + f.h / 2) * ih;
  const ix = Math.min(0, Math.max(ww - iw, ww / 2 - cx));
  const iy = Math.min(0, Math.max(wh - ih, wh * 0.45 - cy));
  return { ix, iy, iw, ih };
};

// Speaker photo in a rectangular (or round) window, tinted with the brand color
// the same way as in Figma (color blend over the photo).
export const SpeakerPhoto: React.FC<{
  readonly id: string;
  readonly photo: Photo | null;
  readonly x: number;
  readonly y: number;
  readonly w: number;
  readonly h: number;
  readonly round?: boolean;
  readonly faceShare?: number;
  readonly dx?: number; // slide offset of the content (animation)
}> = ({ id, photo, x, y, w, h, round = false, faceShare = 0.32, dx = 0 }) => {
  const url = useAsset();
  const c = photo ? crop(photo, w, h, faceShare) : null;
  return (
    <g>
      <clipPath id={`clip-${id}`}>
        {round ? <circle cx={x + w / 2} cy={y + h / 2} r={w / 2} /> : <rect x={x} y={y} width={w} height={h} />}
      </clipPath>
      <g clipPath={`url(#clip-${id})`} style={{ isolation: "isolate" }}>
        <g transform={`translate(${dx} 0)`}>
          {photo && c ? (
            <image
              href={url(photo.file)}
              x={x + c.ix}
              y={y + c.iy}
              width={c.iw}
              height={c.ih}
              preserveAspectRatio="none"
            />
          ) : (
            <rect x={x} y={y} width={w} height={h} fill={C.bar} />
          )}
          <rect x={x} y={y} width={w} height={h} fill={C.ink} style={{ mixBlendMode: "color" }} />
        </g>
      </g>
    </g>
  );
};

// Event illustration covering a box (optionally mirrored).
export const Cover: React.FC<{
  readonly file: string | null;
  readonly x?: number;
  readonly y?: number;
  readonly w: number;
  readonly h: number;
}> = ({ file, x = 0, y = 0, w, h }) => {
  const url = useAsset();
  return file ? (
    <image href={url(file)} x={x} y={y} width={w} height={h} preserveAspectRatio="xMidYMid slice" />
  ) : (
    <rect x={x} y={y} width={w} height={h} fill={C.panel} />
  );
};

// White circle with the partner logo inside.
export const PartnerBadge: React.FC<{
  readonly partner: Event["partner"];
  readonly cx: number;
  readonly cy: number;
  readonly r?: number;
  readonly logoW?: number;
  readonly logoH?: number;
  readonly logoDx?: number; // logo centre relative to the circle (the badge is cut by the frame)
  readonly logoDy?: number;
  readonly scale?: number;
}> = ({ partner, cx, cy, r = 178, logoW = 276, logoH = 65, logoDx = 0, logoDy = -7, scale = 1 }) => {
  const url = useAsset();
  if (!partner) return null;
  return (
    <g transform={`translate(${cx} ${cy}) scale(${scale}) translate(${-cx} ${-cy})`}>
      <circle cx={cx} cy={cy} r={r} fill={C.white} />
      {partner.logo ? (
        <image
          href={url(partner.logo)}
          x={cx + logoDx - logoW / 2}
          y={cy + logoDy - logoH / 2}
          width={logoW}
          height={logoH}
          preserveAspectRatio="xMidYMid meet"
        />
      ) : (
        <Text x={cx} y={cy + 20} anchor="middle" size={48} color={C.title}>
          {partner.name}
        </Text>
      )}
    </g>
  );
};

// Root <svg> of a card; children are positioned in its pixel coordinates.
export const Card: React.FC<{
  readonly w: number;
  readonly h: number;
  readonly props: BrandProps;
  readonly children: React.ReactNode;
}> = ({ w, h, props, children }) => (
  <Metrics.Provider value={props.metrics}>
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      xmlns="http://www.w3.org/2000/svg"
      xmlnsXlink="http://www.w3.org/1999/xlink"
      style={{ position: "absolute", left: 0, top: 0 }}
    >
      <rect width={w} height={h} fill={C.white} />
      {children}
    </svg>
  </Metrics.Provider>
);
