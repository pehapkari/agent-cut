Jsi střihač a video inženýr. Ve složce máš záznam přednášky:
- audio - hlavní zvuk z mikrofonu (mono)
- screen - záznam obrazovky (mozna ma zvuk pro sync)
- camera - záznam kamery (má vlastní zvuk)
- intro obrazek v png i svg pro mozne animovani
- recnik screen v png i svg pro mozne animovani

Cíl: postav opakovatelnou pipeline ve skriptech (Python + ffmpeg). Každý krok ukládá výstup do work/ a dá se pustit znovu samostatně. Na začátku zkontroluj nástroje (ffmpeg, python, mlx-whisper nebo whisper.cpp) a co chybí, doinstaluj. Originály nikdy neupravuj.

KROKY
1. probe: ffprobe všech souborů → work/probe.json (délky, fps, rozlišení, audio stopy).
2. proxy: 720p proxy obou videí → work/proxy/. Analýzu dělej na proxy, finální render z originálů.
3. audio: mono → stereo (pan=stereo|c0=c0|c1=c0), lehký denoise (afftdn), loudnorm −14 LUFS, true peak −1 dB → work/audio_clean.wav.
4. sync: najdi časový posun kamery i screenu vůči hlavnímu zvuku křížovou korelací (scipy, na prvních ~5 min, 16 kHz mono). Pokud screen nemá zvuk, navrhni jinou metodu (tlesknutí, vizuální cue, časová razítka) a zeptej se mě. Výsledek → work/offsets.json. Ověř ho na dvou dalších místech v nahrávce.
5. transcript: přepis audio_clean.wav, jazyk čeština, časy po slovech → work/transcript.json + čitelný work/transcript.md s časovými značkami po odstavcích.
6. edit: z přepisu navrhni základní střih: ořez začátku a konce, pauzy nad 1,5 s, přeřeky, opakované starty vět, technické zdržení. Ve videu nic neodstraňuj natvrdo. Návrh dej do work/edit_plan.md (co, kde, proč) a počkej na moje schválení. Po schválení vygeneruj FCPXML timeline pro DaVinci Resolve: 3 stopy (kamera, screen, audio_clean), synchronizované podle offsets.json, se střihy → out/lecture.fcpxml.
7. highlights: najdi 5–10 pasáží o délce 30–60 s vhodných na reels. Každá musí mít hook v první větě, uzavřenou myšlenku a dávat smysl bez kontextu. → work/highlights.md (čas, délka, hook, proč funguje, návrh titulku/popisku). Počkej na můj výběr.
8. reels: vybrané pasáže vyrenderuj 1080×1920. Kamera nahoře (ořez na obličej), screen dole. Pokud na screenu není nic důležitého, dej kameru přes celou plochu. Vypálené titulky (ASS, max 2 řádky, velké, čitelné, zvýraznění klíčových slov). Audio z audio_clean. → out/reels/NN_nazev.mp4.
9. kontrola: z každého reelsu vytáhni 3 snímky (začátek, střed, konec), prohlédni si je a ověř ořez, titulky a sync rtů. Problémy oprav, ve finálním shrnutí vypiš jen to, co je potřeba zkontrolovat ručně.

PRAVIDLA
- Před dlouhými operacemi odhadni čas.
- Rozhodnutí, která nejdou snadno vrátit, nejdřív konzultuj.
- Kód drž přehledný: pipeline/01_probe.py … 09_check.py + run.sh.
- README.md s popisem, jak pipeline pustit na další přednášku.