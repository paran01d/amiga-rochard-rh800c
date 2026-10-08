# How generative AI was used in this project

**Short version:** this restoration was done by one person working with
**Claude**, Anthropic's AI model, through **Claude Code** (a command-line
assistant that can read files, run tools and write code on the owner's
machine). We are saying so up front for two reasons:

1. **It's a big part of why this worked.** A one-person hobby restoration of an
   undocumented 1990 expansion card, with read-protected logic chips, would
   normally stall out. Having a tireless collaborator to decode logic-analyser
   captures, write GAL equations, 68000 assembly and Python tools, and keep track
   of months of notes made it practical.
2. **Some people are (understandably) wary of AI-generated content.** You should
   be able to judge this repository knowing exactly how it was made, which parts
   a human verified, and where the AI was wrong.

## Who did what

**The human (owner) did all of the physical and judgement work:**
- every measurement: meter, scope and logic-analyser probing, captures, readings;
- all soldering, rework, chip pulling/seating, socket repairs, burning GALs on the TL866;
- running every test on the real Amigas (DiagROM, ATK, rhmon, rhstress, marchu, WHDLoad);
- deciding what to try next, rejecting bad ideas, and spotting a lot of the
  actual faults (e.g. it was the owner who found the bridging SIMM socket
  contact, the dirty edge connector, the unseated UA3 daughterboard and the pico PSU);
- drawing the KiCad schematic by hand from the board, and specifying, printing
  and test-fitting the faceplate (the AI turned the measurements into the model).

**Claude (the AI) mostly worked on analysis, code and documentation:**
- decoding logic-analyser and scope captures (e.g. finding that the 33 corrupted
  longwords in an overnight `rhstress` run held exactly the *previous* pass's
  pattern - i.e. writes were silently lost, pointing at a physical contact fault);
- reasoning from the netlist and cracked equations (e.g. inferring that "U9"
  had to be a 74LS374 latch, not the 74LS688 drawn, and that RN2 must be a
  pull-down to make the `$E8` decode work - both confirmed by the owner);
- writing the GAL designs (`gal/ua6/ua6_ram6.pld`, `gal/ua3b/ua3b_rebuild8.pld`
  and their history), the 68000 tools (`rhmon`, `rhstress`, `marchu`, `romdump`,
  `rhmemtest`), the TL866 black-box pipeline, the Galdurino host tools,
  `mkrochard.py`, `whdmem.py`, the OpenSCAD models and these documents;
- running emulator experiments (Amiberry) to separate software problems from hardware ones.

All code was assembled/compiled and, wherever possible, tested before use - in an
emulator for the Amiga tools (including deliberate fault-injection builds to
prove the RAM tests catch errors) and on the real hardware by the owner.

## Where the AI was wrong

In the interest of honesty, here are some of the AI's mistakes that cost time.
Every one was caught by real measurements, which is the point: **treat AI
output as a hypothesis, then measure.**

- **UA3b "rev 9"** - a timing "fix" for a refresh/precharge problem that had
  never actually been measured. It cut the DRAM row-address hold time to 10 ns
  and made things worse. Rev 8 was restored. Lesson: measure before changing timing.
- **"UA6 is probably broken"** and **"the RAM isn't autoconfig"** - both
  confidently stated, both wrong. (Our rebuilt UA6 presents the RAM as a second
  autoconfig board.)
- **"Replace U1"** - a logic-analyser trace looked like a dead 74LS245 output.
  The owner replaced it; nothing changed. The real cause was a SIMM socket
  contact bridging an address line onto the data bus. The AI had not considered
  that the LA's logic threshold hides a marginal voltage level.
- **"DB12 stuck high"** - read from DiagROM's one-line board summary; the full
  autoconfig dump showed the ID was perfect.
- **"Don't cut the rev 5 JP7A-equivalent trace"** for the 1 MB chip upgrade -
  wrong for a trapdoor card without its own chip/slow jumper (it caused a black
  screen until Gary pin 32 was isolated).
- Several 3D-model details (which side "right" was, leg direction) needed the
  owner's correction once parts were actually printed and test-fitted.

## About the documentation

The pages in `docs/` and the folder READMEs were **drafted by Claude** from the
project's working notes, captures and source files, and **reviewed by the
owner** before publishing. The [work log](worklog.md) keeps the dead ends in on
purpose. If you find something wrong, please open an issue - and if you are
restoring a RocHard yourself, the [troubleshooting guide](troubleshooting.md) is
the place to start.
