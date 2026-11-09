# Od záznamu k pipeline – osnova

Jak jsme za 11 dní (17.–28. 10. 2026) postupně naučili agenta stříhat přednášky
Péhápkařů: od jednoho promptu po Python pipeline, grafiku z dat a nástroj v Rustu.
Slajdy jsou v `presentation.html` (šipky ←→, F celá obrazovka, N poznámky).
Na plátně je jen symbol a slogan, zbytek se říká a ukazuje živě.

Ke každému slajdu: **na plátně** / co říct / co ukázat.

---

## 1. Úvod
**Na plátně:** 🎙 🖥 🎥 → ▶ · „Jak jsem naučil agenta stříhat“
- Kdo jsem, Péhápkaři, proč nahráváme přednášky.

## 2. Výchozí stav
**Na plátně:** 3 zdroje · 1 večer · 1 přednáška
- Mikrofon, záznam obrazovky, kamera. Každý jinak dlouhý, jinak posunutý.
- Ruční synchronizace a stříhání v DaVinci zabere večer na jednu přednášku.

## 3. Jeden prompt
**Na plátně:** „Jsi střihač a video inženýr.“
- První zadání: opakovatelná pipeline, Python + ffmpeg, každý krok zvlášť.
- Ukázat: původní prompt.

## 4. Pravidla, ne instrukce
**Na plátně:** Originály nikdy neupravuj · Odhadni čas · Nevratné konzultuj
- Tři věty, které platily celou dobu. Agent se jich držel lépe než jakéhokoli postupu.
- Výsledek: 0 změněných originálů.

## 5. Sync a přepis
**Na plátně:** 〰 ≈ 〰 · ± 1 snímek
- Zvuk kamery vs. mikrofon: korelace, drift hodin. Screen bez zvuku: vizuální sync přes projekci v kameře.
- Whisper large-v3 lokálně na Macu, časy po slovech.
- Ukázat: `work/offsets.json`, `transcript.md`.

## 6. Agent navrhne, člověk rozhodne
**Na plátně:** E001 ✓ · E002 ✓ · E026 ✗
- Střih jako seznam návrhů (ticha, opakované starty vět), schválení jedním příkazem.
- Do DaVinci jde FCPXML: nic se nemaže, každý střih má marker s důvodem.
- Q&A do záznamu nedáváme. Pravidlo vzniklo z jedné odpovědi a zapsalo se do README.
- Ukázat: `edit_plan.md` → DaVinci timeline.

## 7. Reels
**Na plátně:** 9 : 16 · 30–60 s · 29×
- Kamera se sledováním obličeje, pod ní slajd, titulky po slovech, klíčová slova žlutě.
- Automatická kontrola: obličej v záběru, řádky titulků, lip-sync.
- Ukázat: 2–3 reels.

## 8. Iterace na screenshotech
**Na plátně:** ◯ → ▢ · ostré hrany · just cut
- Kolečko → čtverec, kulaté rohy → ostré hrany, fade → střih. Detekce obličeje skočila na fotky na plátně.
- Nejrychlejší zpětná vazba: screenshot z DaVinci + jedna věta.
- Ukázat: před/po.

## 9. Grafika z dat
**Na plátně:** data → 🐘 → png · svg · mp4
- Žádné exporty z Figmy. `event.md` + `talk.md` + fotka a Remotion (React/SVG) vyrobí intro, outro, karty a náhledy.
- Remotion Studio jako živý náhled při ladění.
- SVG export pro ruční hraní v pen.dev, změny se vrací do kódu.
- Ukázat: Remotion Studio.

## 10. Prvních 5 sekund
**Na plátně:** ✂ teaser → 5 s znělka → přednáška
- Dlouhé znělky algoritmus trestá. Na začátek 5–6 vět z přednášky (cold open), znělka zkrácená na 5 s.
- Ukázat: začátek videa na YouTube.

## 11. 1 → 3
**Na plátně:** souki → matejka · grudl
- Pipeline přesunutá do sdíleného `agent-cut/`, přednášky vedle.
- Druhá a třetí přednáška odhalily, co první neukázala.

## 12. Realita > plán
**Na plátně:** 1 h limit · tichý screen · cache podle cesty
- Rekordér dělí nahrávky po hodině → krok 0 (spojení).
- Záznam obrazovky bez zvuku → vizuální sync.
- DaVinci si pamatuje soubor podle cesty → ve videu byl starý slajd. Řešení: kopie s hashem v názvu.

## 13. 1 záznam → 10+ výstupů
**Na plátně:** ▶ YouTube · ⏱ kapitoly · 📱 reels · 💬 social · 📝 článek
- Kapitoly s časy přepočtenými přes střih, teaser a intro.
- `social.html`: příspěvky s citáty a obrázky. `article.md`: převyprávění pro web.
- Hlas textů: „slon“ (`slon.md`).
- Ukázat: `social.html`.

## 14. Paměť je v repu
**Na plátně:** CLAUDE.md · README · STRUCTURE · git
- Kontext docházel a sezení se střídala. Co není zapsané, další agent neví.
- Dokumentace pro člověka i agenta, repo na GitHubu.

## 15. Od skriptů k nástroji
**Na plátně:** `pk` · ✓ ! · · Rust + ratatui
- Založení akce a řečníka, přehled stavu kroků, úpravy configů s kontrolou schématu.
- Stejné příkazy pro člověka (TUI) i agenta (`--json`).
- Ukázat: `pk` naživo, `pk status`.

## 16. Čísla
**Na plátně:** 11 dní · 14 kroků · 3 přednášky · 29 reels · ~5 600 řádků · 0 změněných originálů

## 17. Co si odnést
**Na plátně:** Pravidla hned zapsat · Reálná data od prvního dne · Screenshot > odstavec · Malé kroky
- Iterovat na skutečných nahrávkách, ne na ukázkách.
- Každé rozhodnutí hned do README / CLAUDE.md.
- Agent navrhuje, člověk schvaluje.

## 18. Díky
**Na plátně:** 🐘 · github.com/pehapkari/agent-cut
- Otázky.
