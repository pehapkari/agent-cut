import React, { useState } from "react";
import { cancelRender, continueRender, delayRender, getInputProps, staticFile } from "remotion";
import { AssetUrl, FONT, sampleProps, UNICODE_RANGE, type BrandProps } from "./brand/kit";

// Data come from --props=work/brand/props.json (pipeline/11_brand.py) and files
// from --public-dir=work/brand/public, so one project serves every lecture.
export const brandProps = (): BrandProps => {
  const p = getInputProps() as Partial<BrandProps>;
  return p.event ? (p as BrandProps) : sampleProps;
};

const useHagrid = () => {
  const [handle] = useState(() => delayRender("Loading Hagrid"));
  useState(() => {
    const face = new FontFace(FONT, `url(${staticFile("fonts/Hagrid-Regular.ttf")})`, {
      unicodeRange: UNICODE_RANGE,
    });
    face
      .load()
      .then((f) => {
        document.fonts.add(f);
        continueRender(handle);
      })
      .catch((err) => cancelRender(err));
    return null;
  });
};

// Wraps a scene: fonts loaded, asset files served from the public dir.
export const BrandRoot: React.FC<{ readonly children: React.ReactNode }> = ({ children }) => {
  useHagrid();
  return <AssetUrl.Provider value={(f) => staticFile(f)}>{children}</AssetUrl.Provider>;
};

// A static card as a one-frame composition (PNG stills).
export const still = (Card: React.FC<{ readonly props: BrandProps }>) => {
  const Still: React.FC = () => (
    <BrandRoot>
      <Card props={brandProps()} />
    </BrandRoot>
  );
  return Still;
};
