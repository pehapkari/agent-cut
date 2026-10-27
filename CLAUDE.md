# agent-cut – kontext pro agenta

Péhápkaři (pražský sraz přátel PHP) nahrávají přednášky. Tahle složka je
opakovatelná pipeline, která z nahrávek jedné přednášky udělá:

- střih pro DaVinci Resolve (`out/lecture.fcpxml`: teaser + znělka + rozvržení + outro),
- reels 1080×1920 s titulky (`out/reels/`),
- grafiku z dat přes Remotion (`out/brand/`: karty, YouTube náhledy, Instagram),
- popis a kapitoly pro YouTube (`out/youtube.md`),
- příspěvky na sociální sítě (`out/social.html`) a článek na web (`out/article.md`).

Uživatel (Honza, organizátor) finální video skládá a exportuje v DaVinci
a nahrává na YouTube. Agent připravuje podklady a navrhuje redakční výběry.
Komunikace i všechny texty pro veřejnost jsou **česky**.

## Co číst
1. `README.md` – jak pipeline pustit, co dělá každý krok, formáty vstupních JSONů.
2. `STRUCTURE.md` – rozložení složek, co je originál, co ruční vstup a co výstup.
3. `slon.md` – hlas a pravidla pro texty na web a sociální sítě (krok 13).

## Závazná pravidla
- **Originály nikdy neupravuj.** Nahrávky, fotky a `talk.md` / `event.md` jsou
  vstupy. Vše generované jde do `work/` a `out/` ve složce přednášky.
- **Před dlouhými operacemi odhadni čas** (proxy ~7 min, přepis ~15–20 min,
  rozvržení ~10–15 min, reel ~1 min, viz README).
- **Rozhodnutí, která nejdou snadno vrátit, nejdřív konzultuj** (mazání,
  přejmenování složek, přepis ručně psaných JSONů, nové závislosti).
- Kód drž přehledný: kroky `pipeline/00_join.py … 13_publish.py` + `run.sh`.
  Nový krok = nové číslo, záznam v `run.sh` a v README.
- README.md musí vždy popisovat, jak pipeline pustit na další přednášku.
  Když měníš chování, aktualizuj ho ve stejném kroku.
- Redakční pravidla:
  - **Q&A do záznamu nedáváme** (od první otázky publika po konec, i oznámení
    po přednášce; poděkování řečníka zůstává).
  - Video začíná **teaserem** (5–6 vět po 2–3 s) a krátkou znělkou (~5 s). Žádné
    dlouhé intro ani zvukové efekty, střihy jsou ostré.
  - Logo partnera je na fialovém panelu se slonem (začátek) a v poděkování (outro).
  - Ilustrovaná karta akce je jen pro sociální sítě, ve videu není.

## Klíčové konvence
- **Jedna časová osa:** všechny časy v ručních JSONech (`edit_manual`, `teaser`,
  `highlights`, `youtube`, `social`, `article`) jsou v čase hlavního audia
  (`audio_clean.wav` = originál WAV). `čas_hlavního_audia = čas_zdroje + offset`
  (`work/offsets.json`). Na čas výsledného videa (po střihu, s teaserem a intrem)
  převádí `12_youtube.timeline()`.
- Skript se dá pustit samostatně:
  `LECTURE_DIR=$PWD ../../agent-cut/.venv/bin/python ../../agent-cut/pipeline/NN_xxx.py …`
  nebo `../../agent-cut/pipeline/run.sh . <krok>`, vždy ze složky přednášky.
- Konfigurace: `talk.md` (řečník, název, fotka, pořadí, youtube, anotace) má
  přednost před `lecture.json` (zdroje, whisper prompt, ořezy). Data akce jsou
  v `../event.md`.
- Grafika je **jen z dat** (React/SVG v `pipeline/remotion/src/brand/`), žádné
  exporty z Figmy. `cards.tsx` = karty, `kit.tsx` = barvy, slon, fotka, texty.
- DaVinci si média pamatuje podle cesty, proto FCPXML odkazuje na kopie
  `work/brand/edit/<název>-<hash>.mp4`. Nikdy nepřepisuj soubor, na který už
  FCPXML ukazuje.
- Kód: krátké Python skripty, sdílené věci v `common.py`, komentáře anglicky,
  dokumentace česky. Shell je zsh (pozor na word splitting v cyklech).

## Ruční (redakční) vstupy ve `work/`
Píše je agent nebo uživatel a skripty je nepřepisují:
`edit_manual.json` (ořezy, Q&A), `teaser.json`, `highlights.json` (`selected`),
`subs_fixes.json`, `youtube.json`, `social.json`, `article.json`.
Před přepsáním existujícího se zeptej. Uživatel v nich mohl něco opravit.

## Stav (2026-10-27)
- **sraz-79** (30. 9. 2026): souki (Petr Soukup), matejka (David Matějka), grudl
  (David Grudl). Všechny kroky 0–13 jsou hotové, videa jsou exportovaná
  v `../render/` a nahraná na YouTube (odkazy v `talk.md`).
- Otevřené věci:
  - Jméno a tón slona (`slon.md`) nejsou potvrzené. Texty jsou zatím neutrální.
  - Web, na který půjde `article.md`, zatím neexistuje. Předpoklad je engine
    nad md soubory, front matter se mu přizpůsobí.
  - Písmo Hagrid je jen trial bez číslic, licencovaná verze chybí
    (`tools/fonts/hagrid/`).
  - `event.md` má neověřený čas a místo (`# TODO`).
  - Složku `resources-poc/` přejmenovat na `resources/` (README už počítá
    s `resources/`). Před přejmenováním se zeptej, `event.md` na ni odkazuje.
  - Ladění reels (výběr, ořez).
