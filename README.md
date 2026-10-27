# Pipeline: přednáška → střih pro Resolve + reels

Opakovatelná pipeline (Python + ffmpeg) pro záznam přednášky ze tří zdrojů:
hlavní mikrofon, záznam obrazovky (OBS) a kamera. Originály se jen čtou,
vše vzniká ve `work/` (mezivýsledky) a `out/` (výstupy) **ve složce přednášky**.
Každý krok jde pustit znovu samostatně.

Pipeline je sdílená ve složce `agent-cut/`, akce a přednášky leží vedle ní:
```
pehapkari/
  agent-cut/        pipeline/, tools/, .venv/, README.md, CLAUDE.md (kontext pro agenta),
                    STRUCTURE.md (rozložení složek), slon.md (hlas textů pro web)
  resources/        sdílené podklady: bgr/01–12.png (slon podle měsíce), logo/<partner>.svg
  sraz-79/          jedna akce
    event.md        data akce (viz Grafika)
    souki/          talk.md + fotka řečníka + originály + lecture.json + work/ + out/
    matejka/        …
```
Spouští se z kterékoli složky přednášky: `../../agent-cut/pipeline/run.sh .`

```
pipeline/
  common.py          sdílené cesty, config, ffmpeg wrapper
  00_join.py         spojení rozdělených nahrávek       → work/joined/{audio.wav,screen.mp4}
  01_probe.py        ffprobe zdrojů                    → work/probe.json
  02_proxy.py        720p/30fps CFR proxy pro analýzu   → work/proxy/{camera,screen}.mp4
  03_audio.py        mono→stereo, denoise, −14 LUFS     → work/audio_clean.wav
  04_sync.py         offsety kamery a screenu           → work/offsets.json
  05_transcript.py   přepis (mlx-whisper, časy slov)    → work/transcript.{json,md}
  06_edit.py         návrh střihu → schválení → FCPXML  → work/edit_plan.md, out/lecture.fcpxml
  07_highlights.py   kandidáti na reels                 → work/highlights.md
  08_reels.py        render 1080×1920 reels             → out/reels/NN_slug.mp4
  09_check.py        automatická kontrola reels         → work/check/report.md
  10_layout.py       rozvržení: pozadí + screen + hlava → work/layout/program.mp4
  11_brand.py        grafika z dat: intro, outro, karty  → work/brand/{intro,outro}.mp4, out/brand/
  12_youtube.py      popis a kapitoly pro YouTube       → out/youtube.md
  13_publish.py      sociální sítě + článek na web      → out/social.html, out/article.md
  remotion/          Remotion šablony grafiky (src/brand/), sdílené pro všechny akce
  run.sh             spouštěč
tools/               ffmpeg s libass, font, model detekce obličeje (sdílené)
```

## Požadavky

macOS na Apple Silicon (mlx-whisper, VideoToolbox), Homebrew, `uv`.
`pipeline/run.sh <dir> setup` doinstaluje vše potřebné:

- `.venv` (Python 3.12): numpy, scipy, mlx-whisper, opencv-python-headless, pillow, svgpathtools, pyyaml, fonttools
- `pipeline/remotion/node_modules` (Node ≥ 20, `npm ci`); Remotion si při prvním
  renderu stáhne headless Chrome
- `tools/ffmpeg` – statický arm64 build **s libass** (martin-riedl.de, ověřený
  SHA-256 a podpis Developer ID). Homebrew ffmpeg 9 libass nemá a bez něj nejdou
  vypálit ASS titulky. Systémový ffmpeg zůstává beze změny.
- `tools/fonts/Montserrat-ExtraBold.ttf` (OFL), `tools/models/face_detection_yunet_2023mar.onnx`
- `tools/fonts/hagrid/Hagrid-Regular*.ttf` – písmo grafiky (vlož ručně; trial verze
  nemá číslice, ty se pak kreslí náhradním Avenir Next)

### Co není v gitu
Stažené nástroje a licencovaná písma se neverzují (`.gitignore`). Po naklonování
je doplní `pipeline/run.sh . setup`, kromě písma Hagrid:

| Co | Kam | Odkud |
|---|---|---|
| Python balíčky | `.venv/` | `setup` přes `uv` (PyPI) |
| Remotion a závislosti | `pipeline/remotion/node_modules/` | `setup` přes `npm ci` (podle `package-lock.json`) |
| headless Chrome pro Remotion | cache Remotion | sám při prvním renderu |
| ffmpeg s libass (arm64) | `tools/ffmpeg` | `setup`, ffmpeg.martin-riedl.de (kontrola SHA-256) |
| Montserrat ExtraBold (OFL) | `tools/fonts/` | `setup`, github.com/JulietaUla/Montserrat |
| YuNet (detekce obličeje) | `tools/models/` | `setup`, github.com/opencv/opencv_zoo |
| Whisper large-v3 (~3 GB) | `~/.cache/huggingface/` | sám při prvním přepisu (krok 5), huggingface.co/mlx-community |
| **Hagrid** (písmo grafiky) | `tools/fonts/hagrid/Hagrid-*.ttf` | **ručně**: Personal verze zdarma na 1001fonts.com/hagrid-font.html (jen nekomerční použití), komerční licence u Zetafonts (zetafonts.com). Trial nemá číslice |

Podklady akcí (`resources/`, `sraz-XX/`) a nahrávky leží mimo `agent-cut/` a do gitu nepatří.

## Nová přednáška

0. Před akcí: `sraz-XX/event.md` + pro každou přednášku `sraz-XX/<řečník>/talk.md`
   a fotka → `run.sh <dir> brand` → upoutávky v `out/brand/` (viz Grafika).
1. Nahraj nahrávky do složky přednášky (`sraz-XX/novak/`).
2. Spusť automatické kroky 0–5:
   ```sh
   cd ~/Movies/pehapkari/sraz-80/novak && ../../agent-cut/pipeline/run.sh .
   ```
   První běh vytvoří `lecture.json` autodetekcí (WAV = audio, MKV = screen,
   MOV/MP4 = kamera). **Zkontroluj ho** a doplň případně `whisper_prompt` (jména, technologie)
   a `projection_crop` (viz níže). Pak pusť znovu kroky, kterých se změna týká.
   Rozdělené nahrávky: `audio` nebo `screen` může být **seznam souborů**
   (viz krok 0).
3. Střih: do `work/edit_manual.json` zapiš ořez začátku, konce a **Q&A
   (do záznamu nedáváme)** → `run.sh <dir> plan` → přečti `work/edit_plan.md` → `run.sh <dir> approve`
   (nebo `python pipeline/06_edit.py approve --reject=E004,E017`) → `run.sh <dir> brand layout` → teaser (`work/teaser.json`) → `run.sh <dir> brand fcpxml`.
4. Reels: vyber pasáže (viz níže) → `run.sh <dir> 7 8 9`.
5. YouTube: `run.sh <dir> ytsentences` (věty v časech výsledného videa, tj. včetně
   intra a po střihu) → napiš `work/youtube.json` (popis + kapitoly v čase hlavního
   audia) → `run.sh <dir> youtube` → `out/youtube.md`. Časy kapitol sedí na video
   vyexportované z `out/lecture.fcpxml`; při ručních změnách střihu v Resolve pusť znovu.
6. Po nahrání na YouTube: odkaz do `talk.md` (`youtube:`) → napiš `work/social.json`
   a `work/article.json` → `run.sh <dir> publish` → `out/social.html` + `out/article.md`
   (viz Publikace).

Časový odhad pro 45min přednášku na M1 Pro: probe 1 s, proxy ~7 min,
audio ~4 min, sync ~1,5 min, přepis (large-v3) ~15–20 min, každý reel ~1 min.

## Jak fungují jednotlivé kroky

**Spojení (00).** Rekordér dělí dlouhé nahrávky (Wireless PRO po hodině) →
`"audio": ["00025…WAV", "00026…WAV"]` se spojí bezeztrátově za sebe. Záznam
obrazovky přerušený pauzou → `"screen": ["část1.mov", "část2.mov"]`: každá
část se umístí na osu hlavního audia korelací zvuku, mezera drží poslední
snímek a vše se uloží jako jedno 30fps video `work/joined/screen.mp4`.
Ostatní kroky pak berou spojené soubory automaticky.

**Sync (04).** Konvence: `čas_hlavního_audia = čas_zdroje + offset`.
Kamera se hledá křížovou korelací zvuku (16 kHz, pásmo 200–4000 Hz, prvních
5 min proti celému hlavnímu audiu) a ověřuje na dvou dalších místech; z toho
vychází i drift hodin (ppm). Pokud má zdroj tichou stopu (OBS bez zvuku),
použije se **vizuální sync**: signál „změny obrazu“ screenu se koreluje
s výřezem projekce v kameře (`projection_crop` v `lecture.json`, souřadnice
ve 720p proxy `w:h:x:y`; když je `null`, bere se celý obraz). Kamera musí
projekci vidět. Mezivýsledky se cachují do `work/sync_cache/`.

**Audio (03).** Změří hlasitost → zesílí → limiter −2 dBFS → loudnorm
v *lineárním* režimu (−14 LUFS, −1 dBTP). Lineární režim nepumpuje v pauzách;
pokud by loudnorm přesto přešel do dynamického, skript to vypíše. Filtry
(afftdn, look-ahead limiteru) zpozdí výstup o ~27 ms – skript latenci změří
korelací s originálem a vyrovná na vzorek přesně, takže `audio_clean.wav`
má stejnou časovou osu jako originál a offsety ze syncu platí i pro něj.

**Přepis (05).** `mlx-community/whisper-large-v3-mlx`, čeština, časy po
slovech. `--force` přepíše znovu, jinak se jen přegeneruje `transcript.md`.

**Střih (06).** Automaticky: ticho > 1,5 s (zkrátí se na 0,6 s) a opakované
starty vět (2–4 slova; jednoslovná zdvojení jsou v češtině většinou důraz).
Práh ticha je adaptivní (šum místnosti + 12 dB) a pauza nesmí obsahovat
přepsané slovo. Pauza, ve které **mikrofon kamery slyší sál** (dotaz publika
mimo mikrofon, smích, potlesk), se nestřihá. Redakční položky (ořez
začátku/konce, přeřeky, technická zdržení) patří do `work/edit_manual.json`:
```json
[{"type": "trim", "start": 0, "end": 152.4, "why": "příprava před začátkem"},
 {"type": "slip", "start": 812.3, "end": 814.1, "why": "přeřek, opraveno hned potom"},
 {"type": "keep", "start": 2184, "end": 2192, "why": "pointa – pauzu nezkracovat"}]
```
**Q&A do záznamu nedáváme:** dotazy publika od první otázky po konec vždy
vystřihni jako `trim` (i když řečník odpovídá do mikrofonu). Stejně tak vše
po přednášce (kvíz, oznámení organizátorů); závěrečné poděkování řečníka zůstává.
Typy: `trim`, `tech`, `slip`, `repeat`, `pause`, `other`; `keep` zruší
automatické návrhy, které se rozsahu dotýkají. Schválení: `06_edit.py approve`
(`--reject=E004,E017`); stavy se při novém `plan` zachovají. FCPXML (1.10)
má 30 fps 1080p timeline a 3 stopy: V1 kamera, V2 screen, A1 audio_clean.
Nic není smazané – každý střih má marker s ID a důvodem a plná média zůstávají
napojená, takže se střih vrátí roztažením klipu. Kamera používá offset ze
středu souboru, takže drift hodin se rozdělí na ± polovinu.

**Highlights (07).** `run.sh <dir> sentences` vypíše věty s časy do
`work/sentences.md`. Výběr se zapíše do `work/highlights.json`
(`id, slug, start, end, hook, why, title, caption, keywords`) a krok 7 ho
přichytí na hranice slov, ověří 30–60 s a vygeneruje `highlights.md`.
Ke zvoleným pasážím doplň `"selected": true` (volitelně `"layout": "split"|"full"`,
`"zoom"`).

**Reels (08).** Kamera nahoře 1080×960 (sledování obličeje YuNet, plynulý
pohyb, při malém pohybu statický ořez), pod ní screen (černé okraje OBS se
oříznou automaticky přes cropdetect → `work/screen_crop.json`), dole pruh
v barvě akce se jménem řečníka. Když screen pro danou pasáž chybí nebo je
prázdný (málo hran na slajdu), kamera jde přes celou plochu (ořez 80 % výšky, `"zoom"`). Titulky ASS: Montserrat ExtraBold 76 px,
max. 2 řádky lámané podle skutečné šířky textu, klíčová slova (`keywords`)
a čísla žlutě. Audio z `audio_clean.wav`, offset kamery se počítá pro střed
reelu včetně driftu.

Opravy chyb přepisu v titulcích jdou do `work/subs_fixes.json`
(`{"začátek_slova_v_s": "nový text"}`, `""` slovo vypustí; časy jsou ve
`work/transcript.json`). Rozdělené tokeny Whisperu („e“ + „-shop“) se spojí
samy. Jednotlivý reel: `python pipeline/08_reels.py 3`.

**Kontrola (09).** 3 snímky + kontaktní arch na reel, kontrola obličeje
v boxu, šířky a počtu řádků titulků a **lip-sync** (zvuk kamery vs. audio
reelu, tolerance ±1 snímek). Výsledek v `work/check/report.md`.

**Rozvržení (10).** „Program“ video v časové ose hlavního audia (stejná osa
jako `audio_clean.wav`, takže střihy z FCPXML sedí 1:1): pozadí akce
(`work/brand/video-background@2x.png` z kroku 11, jinak `background_png`), vlevo screen v rámečku (ořez černých okrajů OBS), vpravo
nahoře hlava řečníka sledovaná detekcí obličeje (`head_shape`: `circle` /
`square`). Screen a hlava se plynule objeví na začátku prvního ponechaného
úseku, takže střih z intra na pozadí je neviditelný. Sledování obličeje se
cachuje (`work/layout/head_track.npz`); `10_layout.py preview 400 1200` udělá
rychlé náhledové snímky bez renderu. Render 45min přednášky trvá ~10–15 min.

**Grafika (11, Remotion).** Všechny obrázky a animace se skládají z dat,
žádné exporty z Figmy. Šablony jsou React komponenty s čistým SVG
v `pipeline/remotion/src/brand/` (`kit.tsx` barvy, slon, pruhy, fotka, texty;
`cards.tsx` jednotlivé karty), animace v `src/Intro.tsx`.

`sraz-XX/event.md` (cesty relativně k souboru):
```markdown
---
number: 79
name: pražský sraz přátel PHP
date: 2026-09-30
time: "18:00"
venue: Impact Hub
url: pehapkari.cz
image: ../resources/bgr/09.png
partner:
  name: Simplia
  logo: ../resources/logo/simplia.svg
---
```
`sraz-XX/<řečník>/talk.md`: `speaker`, `title`, `photo` (běžná fotka – obličej se
najde sám a drží se v každém ořezu), `order` (pořadí v programu), `youtube`
(odkaz na nahrané video, pro krok 13); text pod
hlavičkou = anotace. `speaker`/`title` odtud bere i zbytek pipeline (přednost
před `lecture.json`).

`run.sh <dir> brand` vyrobí (~30 s):
- `work/brand/intro.mp4` (5,5 s): fialový panel se slonem, názvem akce a logem partnera
  se rozjede do karty řečníka → pozadí přednášky (poslední snímek = začátek rozvržení).
  Znělka je schválně krátká – algoritmy trestají pomalý začátek.
- `work/brand/teaser.mp4` (cold open před intrem): 5–6 vět po 2–3 s, lišty 2× vyšší
  než v přednášce: nahoře „V této epizodě uvidíte“ + ukazatel postupu přes celou šířku,
  dole věta (až 2 řádky); mezi nimi slide a řečník stejně vysocí (564 px), velký slon
  v popředí; mezi větami rychlý střih přes fialový pruh.
  Na konci se lišty zavřou do panelu se slonem = první snímek intra (plynule navazuje).
  Výběr do `work/teaser.json` (`[{"start", "end", "text"}]`, čas hlavního audia,
  `end` = konec posledního slova; věty, které zaujmou a donutí dokoukat celé
  video). Skládá se přímo ze zdrojů (screen + kamera se sledováním obličeje z kroku 10).
  Kamera 720p: velké okno snese řečníka, který je v záběru blízko; vzdálený řečník
  (malý obličej) bude měkčí.
- `work/brand/outro.mp4` (10,5 s): pruhy se zatáhnou, slon + „Díky za sledování“
  + logo partnera, pak prázdné pozadí na 5,7 s pro koncové karty YouTube
- `work/brand/video-background@2x.png` – pozadí pro rozvržení (10)
- `out/brand/*.png`: karta akce (jen pro sociální sítě, ve videu není), karta řečníka, pozadí, YouTube náhled A a B
  (A/B test), Instagram řečník, Instagram akce (všichni řečníci akce)
- `out/brand/svg/*.svg` – samostatná SVG (vložené obrázky i písmo) k úpravám
  v pen.dev / Figmě; upravené SVG se pak ručně přenese zpět do `cards.tsx`

Práce přímo v `pipeline/remotion/` (Node ≥ 20): `npm run lint` (ESLint + TypeScript),
`npx remotion upgrade` (všechny balíčky `@remotion/*` musí mít stejnou verzi),
dokumentace na remotion.dev/docs. Licence Remotion: pro jednotlivce, neziskovky
a firmy do 3 lidí zdarma, jinak je potřeba firemní licence
(github.com/remotion-dev/remotion/blob/main/LICENSE.md).

Dílčí kroky: `python pipeline/11_brand.py assets|stills|intro|outro|teaser|svg`.
FCPXML odkazuje na kopie `work/brand/edit/<název>-<hash>.mp4` – DaVinci si soubor
pamatuje podle cesty, nový render se stejným názvem by ukázal starou verzi.
Živý náhled s daty přednášky: `run.sh <dir> studio`. Zvuk intra: žádný, nebo
`intro_music` v `lecture.json`.

**FCPXML** po krocích 10 a 11 obsahuje: teaser + intro na začátku, outro na konci, V1 kamera,
V2 screen (surové úhly pro ruční úpravy), V4 hotové rozvržení navrchu, A1 audio_clean.

**Publikace (13).** Texty píše „slon“ – hlas a pravidla jsou v `slon.md`.
Časy se píšou v čase hlavního audia (jako u YouTube kapitol) a skript je
převede na čas ve videu na YouTube (odkazy `youtu.be/<id>?t=…`).
- `work/social.json` → `out/social.html`: hlavní příspěvek (`claim` + `summary`,
  obrázky z `out/brand/`) a jedna pointa na každý reel (`posts[].id` = id
  z `highlights.json`; `quote` jde na obrázek, `text` je příspěvek, volitelně `frame`
  = čas snímku řečníka). Obrázek `out/social/NN_slug.png` (1080×1080, karta
  `instagram-quote`): snímek z kamery s nejčistším obličejem v prvních sekundách
  pointy, citát, řečník a akce. Stránka má u každého textu tlačítko Kopírovat
  a přehrávač reelsu. Potřebuje krok 11 (`work/brand/props.json`).
- `work/article.json` → `out/article.md`: front matter pro web (`title`, `speaker`,
  `event`, `date`, `youtube`, `youtube_id`, `duration`, `description`, `chapters`
  s časy pro přehrávač), perex, sekce s odkazem na čas ve videu, „Co si odnést“.
  Sekce volně spojují kapitoly z `youtube.json`.

Dílčí kroky: `python pipeline/13_publish.py social|social-text|article`
(`social-text` = jen texty, obrázky zůstanou). Render obrázků ~10 s na pointu.
