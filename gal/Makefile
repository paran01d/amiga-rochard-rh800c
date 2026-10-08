# RocHard RH800C - GAL builds (run from this gal/ directory)
#
#   make             - build the two GALs that go on the card (ua6, ua3b)
#   make ua6         - ua6/ua6_ram6.jed      (UA6, expected fuse checksum 0x9365)
#   make ua6-hd      - ua6/ua6_hd_b001d.jed  (UA6 HD-only diagnostic build, 0x670D)
#   make ua3b        - ua3b/ua3b_rebuild8.jed (UA3b DRAM controller, 0xC824)
#   make history     - rebuild every historical revision under */history/
#   make lgc         - TL866 logic-test vectors (ua4/*.toml -> .lgc)
#   make checksums   - print the fuse checksum of every committed .jed
#   make clean       - remove galasm's .fus/.chp/.pin side files
#                      (the .jed files are committed deliverables and are kept)
#
# Any source can also be built directly:  make ua6/ua6_ram4.jed
#
# Tools (on PATH):
#   galasm       https://github.com/daveho/GALasm
#   xgpro-logic  https://github.com/evolutional/xgpro-logic   (only for `make lgc`)

GALASM     ?= galasm
XGPROLOGIC ?= xgpro-logic

HISTORY_PLD := $(wildcard ua6/history/*.pld ua3b/history/*.pld)
TOML_SRCS   := $(wildcard ua4/*.toml)

.PHONY: all ua6 ua6-hd ua3b history lgc checksums clean
all: ua6 ua3b

ua6:    ua6/ua6_ram6.jed
ua6-hd: ua6/ua6_hd_b001d.jed
ua3b:   ua3b/ua3b_rebuild8.jed
history: $(HISTORY_PLD:.pld=.jed)
lgc:    $(TOML_SRCS:.toml=.lgc)

# galasm writes .jed/.fus/.chp/.pin next to the source
%.jed: %.pld
	$(GALASM) $<

%.lgc: %.toml
	$(XGPROLOGIC) lgc $< $@

checksums:
	@for f in $$(find . -name '*.jed' | sort); do \
	  printf '%-40s %s\n' "$$f" "$$(tr -d '\r' < $$f | grep -o -E '(^|\*)C[0-9A-Fa-f]{4}' | head -1 | grep -o -E '[0-9A-Fa-f]{4}$$')"; \
	done

clean:
	find . \( -name '*.fus' -o -name '*.chp' -o -name '*.pin' \) -delete
