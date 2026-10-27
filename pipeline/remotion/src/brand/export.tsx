// Static SVG export of the cards (for editing in pen.dev / Figma):
//   esbuild-bundled and run by pipeline/11_brand.py svg
//   node export.cjs <props.json> <public dir> <out dir>
// Images and the Hagrid font are embedded, so every file is self-contained.
import fs from "node:fs";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import {
  BackgroundCard,
  EventCard,
  InstagramEvent,
  InstagramSpeaker,
  SpeakerCard,
  ThumbnailA,
  ThumbnailB,
} from "./cards";
import { AssetUrl, FONT, UNICODE_RANGE, type BrandProps } from "./kit";

const [propsFile, publicDir, outDir] = process.argv.slice(2);
const props = JSON.parse(fs.readFileSync(propsFile, "utf8")) as BrandProps;

const MIME: Record<string, string> = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ttf": "font/ttf",
};
const dataUri = (file: string) => {
  const p = path.join(publicDir, file);
  return `data:${MIME[path.extname(p).toLowerCase()]};base64,${fs.readFileSync(p).toString("base64")}`;
};
const font = `<defs><style>@font-face{font-family:"${FONT}";src:url(${dataUri("fonts/Hagrid-Regular.ttf")}) format("truetype");unicode-range:${UNICODE_RANGE};}</style></defs>`;

const CARDS = {
  "event-card": EventCard,
  "speaker-card": SpeakerCard,
  "video-background": BackgroundCard,
  "youtube-thumbnail-a": ThumbnailA,
  "youtube-thumbnail-b": ThumbnailB,
  "instagram-speaker": InstagramSpeaker,
  "instagram-event": InstagramEvent,
};

fs.mkdirSync(outDir, { recursive: true });
for (const [name, Card] of Object.entries(CARDS)) {
  const svg = renderToStaticMarkup(
    <AssetUrl.Provider value={dataUri}>
      <Card props={props} />
    </AssetUrl.Provider>,
  )
    .replace(/ style="position:absolute;left:0;top:0"/, "")
    .replace(/(<svg[^>]*>)/, `$1${font}`);
  fs.writeFileSync(path.join(outDir, `${name}.svg`), `<?xml version="1.0" encoding="UTF-8"?>\n${svg}\n`);
  console.log(`${name}.svg`);
}
