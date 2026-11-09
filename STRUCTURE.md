# Struktura složek

```
pehapkari/
  CLAUDE.md               jen odkaz na agent-cut/CLAUDE.md (načte se z každé podsložky)
  agent-cut/              nástroj – sdílený pro všechny akce, žádná data přednášek
    CLAUDE.md             kontext pro agenta
    README.md             návod: jak pipeline pustit, co dělají kroky
    STRUCTURE.md          tento soubor
    slon.md               hlas textů pro web a sociální sítě
    pipeline/             00_join.py … 14_index.py, common.py, run.sh
      remotion/           šablony grafiky (React/SVG), node_modules
    pk/                   Rust CLI + TUI: zakládání akcí a řečníků, stav, úpravy configů
    schema/               JSON Schema pro event.md, talk.md, lecture.json (sdílené)
    tools/                ffmpeg s libass, fonty, model detekce obličeje
    .venv/                Python 3.12 (vytvoří `run.sh . setup`)
  resources/              sdílené podklady napříč akcemi (zatím resources-poc/)
    bgr/01–12.png         ilustrace slona podle měsíce
    logo/<partner>.svg    loga partnerů
  sraz-79/                jedna akce = sraz-<číslo>
    event.md              data akce: číslo, datum, místo, partner, ilustrace
    promo.json            nepovinné ruční texty upoutávek → krok 14
    index.html            rozcestník akce: obrázky a texty ke sdílení (generovaný, krok 14)
    <řečník>/             jedna přednáška, složka podle příjmení nebo přezdívky
  render/                 hotové exporty z DaVinci (<řečník>.mp4), mimo pipeline
  poc-before-event/       archiv: ruční SVG z doby před pipeline, nepoužívá se
  souki, matejka, grudl → symlinky na sraz-79/… pro rychlý přístup
```

## Složka přednášky

Tři druhy souborů. Pipeline z první skupiny jen čte, druhou nepřepisuje
a třetí kdykoli vyrobí znovu.

**1. Originály a konfigurace** (ručně, nikdy se neupravují skriptem)
```
<řečník>/
  *.WAV                   hlavní mikrofon (může být víc částí)
  *.mkv / *.mov / *.mp4   záznam obrazovky (OBS, Screen Recording)
  IMG_*.MOV               kamera
  <řečník>.jpg            fotka řečníka
  talk.md                 speaker, title, bio, photo, order, youtube + anotace
  lecture.json            zdroje a technika (vznikne autodetekcí, pak ruční kontrola)
```
`event-79*.svg/png` a `video-background*` jsou podklady z doby před Remotion.
Pipeline je čte jen jako záložní, když chybí grafika z kroku 11.

**2. Redakční vstupy ve `work/`** (píše agent nebo člověk, skript je nepřepíše)
```
work/
  edit_manual.json        ořez začátku/konce, Q&A, přeřeky   → krok 6
  teaser.json             věty do cold openu                → krok 11
  highlights.json         pasáže na reels + "selected"      → kroky 7–8
  subs_fixes.json         opravy titulků                    → krok 8
  youtube.json            popis + kapitoly                  → krok 12
  social.json             claim, pointy, citáty             → krok 13
  article.json            perex, sekce, „Co si odnést“      → krok 13
```

**3. Generované** (smazatelné, vznikne znovu)
```
work/                     mezivýsledky: probe, proxy/, joined/, audio_clean.wav,
                          offsets.json, transcript.*, edit_plan.*, sentences*.md,
                          layout/, brand/, reels/, check/, social/, sync_cache/, *.log
out/                      výstupy pro člověka:
  lecture.fcpxml          střih pro DaVinci
  edit_plan.html          návrh střihu ke čtení (stav, vystřižený text přeškrtnutý)
  highlights.html         pasáže na reels + věty teaseru ke čtení (popisky s Kopírovat)
  opening.mp4             náhled začátku videa: teaser + znělka (krok 11)
  reels/NN_slug.mp4       reels
  reels/preview/H{n}_*.mp4 náhledy všech kandidátů 540×960 (run.sh preview)
  brand/                  karty, náhledy, Instagram (+ svg/ k úpravám)
  youtube.md (+ .html)    popis a kapitoly
  social.html, social/    příspěvky + obrázky 1080×1080
  article.md              článek pro web
  article.html            náhled článku (přehrávač, kapitoly)
  index.html              stránka řečníka v rozcestníku akce (krok 14)
```
Pozor: `work/brand/edit/*` jsou kopie, na které odkazuje otevřený projekt
v DaVinci. I když jsou generované, nemaž je, dokud je projekt rozpracovaný.

## Nová akce
```
sraz-80/
  event.md                pk event new 80 --date … (nebo zkopíruj ze sraz-79)
  novak/talk.md + fotka   pk speaker add 80 --name "Jan Novák" --title … --photo …
```
Pak postup v README („Nová přednáška“).
