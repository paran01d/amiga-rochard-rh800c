/*
  Galdurino-BB.ino  --  UA6 black-box probe firmware  (MCP23S17 / SPI)
  --------------------------------------------------------------------
  Arduino Uno + 2x CJMCU-2317 (populated with MCP23S17 in SPI form).
  Not a fuse-map reader -- a static combinatorial pattern generator +
  output-latch reader used to reverse-engineer UA6 empirically.

  Wiring (perfboard-shield, Uno headers on rows V and C):
    Uno D13 = SCK  -> both MCP pin 12
    Uno D12 = MISO -> both MCP pin 14 (SO)
    Uno D11 = MOSI -> both MCP pin 13 (SI)
    Uno D10 = /CS  -> both MCP pin 11 (shared, HAEN differentiates)
    Uno A1  -> optional Q2 gate for UA6 VCC switch (skip on first bring-up)
    +5V -> both MCP VDD (pin 9), both /RESET (pin 18), UA6 pin 24
    GND -> both MCP VSS (pin 10), UA6 pin 12
    MCP #1 A0=A1=A2=GND      -> hardware address 0
    MCP #2 A0=+5V, A1=A2=GND -> hardware address 1

  Pin-to-UA6 mapping is identical to the I2C draft (only the bus differs):
    U1 GPA0..7 = UA6 pins 1..8  (AB1..AB6, STRB, CFG8M)   -- drives
    U1 GPB0..5 = UA6 pins 9,10,11,13,14,17                -- drives
    U1 GPB6..7 = UA6 pins 15,16                           -- reads (pull-ups on)
    U2 GPA0..5 = UA6 pins 18..23                          -- reads (pull-ups on)
    U2 GPA6..7, GPB0..7 = spare (breakout for scope hooks)

  Serial commands (case insensitive, newline terminated):
    HELP  or  ?         List commands
    INIT                Enable IOCON.HAEN and configure both MCPs
    POWER ON | OFF      Toggle A1 (UA6 VCC gate, optional)
    DRIVE  <hex14>      Apply 14-bit input pattern
    READ                Read 8-bit output word (hex)
    STEP   <hex14>      DRIVE, 1 ms settle, READ; print IN:xxxx OUT:xx
    SWEEP  <a> <b> [s]  Iterate over hex range [a..b] step s, CSV out
    STATUS              Dump VCC + init state + a live register readback

  Bit layouts unchanged from the I2C draft:
    INPUT  bit 0 = AB1 .. bit 13 = RST      (14 bits)
    OUTPUT bit 0 = BIN3 .. bit 7 = ACPHASE  (8 bits)
*/

#include <SPI.h>

#define VCC_CTRL  A1     // optional Q2 gate; HIGH = UA6 powered
#define CS_PIN    10     // both MCPs share this CS

// Hardware addresses (set by A0 solder-jumper on each CJMCU)
#define U1_HA     0      // MCP #1 : A2 A1 A0 = 0 0 0
#define U2_HA     1      // MCP #2 : A2 A1 A0 = 0 0 1

// SPI opcode: 0100 A2 A1 A0 R  -- bit 0 = R/W (0=write, 1=read)
#define OP_WRITE(a) (0x40 | ((a) << 1) | 0)
#define OP_READ(a)  (0x40 | ((a) << 1) | 1)

// MCP23S17 register map (IOCON.BANK = 0, factory default)
#define REG_IODIRA 0x00
#define REG_IODIRB 0x01
#define REG_IOCON  0x0A     // shared with 0x0B in BANK=0
#define REG_GPPUA  0x0C
#define REG_GPPUB  0x0D
#define REG_GPIOA  0x12
#define REG_GPIOB  0x13
#define REG_OLATA  0x14
#define REG_OLATB  0x15

// IOCON bits
#define IOCON_HAEN 0x08     // 1 = respond only to matching A2:A0 (required for shared bus)

static SPISettings SPI_MCP(8000000UL, MSBFIRST, SPI_MODE0);

static String inputString;
static bool   stringComplete = false;
static bool   vccOn          = false;
static bool   inited         = false;

// ---- low-level SPI helpers ---------------------------------------------
static void spiWrite(uint8_t ha, uint8_t reg, uint8_t val) {
    SPI.beginTransaction(SPI_MCP);
    digitalWrite(CS_PIN, LOW);
    SPI.transfer(OP_WRITE(ha));
    SPI.transfer(reg);
    SPI.transfer(val);
    digitalWrite(CS_PIN, HIGH);
    SPI.endTransaction();
}

static uint8_t spiRead(uint8_t ha, uint8_t reg) {
    SPI.beginTransaction(SPI_MCP);
    digitalWrite(CS_PIN, LOW);
    SPI.transfer(OP_READ(ha));
    SPI.transfer(reg);
    uint8_t v = SPI.transfer(0);
    digitalWrite(CS_PIN, HIGH);
    SPI.endTransaction();
    return v;
}

// ---- MCP configuration --------------------------------------------------
static void mcpInit() {
    // HAEN defaults to 0 => every chip on the bus responds to any address.
    // A single broadcast write with target address 0 will land on ALL chips
    // simultaneously; we use that one shot to turn HAEN on.  After this,
    // chips distinguish themselves by A2..A0 straps.
    spiWrite(0, REG_IOCON, IOCON_HAEN);

    // U1: 8 outputs on GPA (AB1..CFG8M); GPB[5:0] outputs (CFG4M..RST);
    //     GPB[7:6] inputs (NC1, ACPHASE) with pull-ups on.
    spiWrite(U1_HA, REG_IODIRA, 0x00);
    spiWrite(U1_HA, REG_IODIRB, 0xC0);
    spiWrite(U1_HA, REG_GPPUA,  0x00);
    spiWrite(U1_HA, REG_GPPUB,  0xC0);
    spiWrite(U1_HA, REG_OLATA,  0x00);
    spiWrite(U1_HA, REG_OLATB,  0x00);

    // U2: all inputs; pull-ups on the six UA6 output reads.
    spiWrite(U2_HA, REG_IODIRA, 0xFF);
    spiWrite(U2_HA, REG_IODIRB, 0xFF);
    spiWrite(U2_HA, REG_GPPUA,  0x3F);
    spiWrite(U2_HA, REG_GPPUB,  0x00);

    inited = true;
}

// ---- data-path helpers --------------------------------------------------
static void driveInputs(uint16_t pattern) {
    spiWrite(U1_HA, REG_OLATA,  pattern        & 0xFF);
    spiWrite(U1_HA, REG_OLATB, (pattern >> 8)  & 0x3F);   // preserve bits 6/7 (input pins)
}

static uint8_t readOutputs() {
    uint8_t u2a = spiRead(U2_HA, REG_GPIOA);   // bits 0..5 valid
    uint8_t u1b = spiRead(U1_HA, REG_GPIOB);   // bits 6..7 valid
    return (u2a & 0x3F) | (u1b & 0xC0);
}

// ---- serial output helpers ---------------------------------------------
static void printHex(uint32_t v, uint8_t width) {
    for (int i = (int)width - 1; i >= 0; --i) {
        uint8_t nib = (v >> (i * 4)) & 0xF;
        Serial.print((char)(nib < 10 ? '0' + nib : 'A' + nib - 10));
    }
}

static void doStep(uint16_t pattern) {
    driveInputs(pattern);
    delay(1);
    uint8_t out = readOutputs();
    Serial.print(F("IN:"));
    printHex(pattern, 4);
    Serial.print(F(" OUT:"));
    printHex(out, 2);
    Serial.println();
}

// ---- command dispatch ---------------------------------------------------
static bool warnUninited() {
    if (!inited) { Serial.println(F("ERR: run INIT first")); return true; }
    return false;
}

static void printHelp() {
    Serial.println(F("Commands (case insensitive):"));
    Serial.println(F("  HELP | ?             this text"));
    Serial.println(F("  INIT                 enable HAEN, configure both MCPs"));
    Serial.println(F("  POWER ON | OFF       toggle A1 (UA6 VCC via optional Q1/Q2)"));
    Serial.println(F("  DRIVE  <hex14>       apply input pattern"));
    Serial.println(F("  READ                 read 8-bit output word"));
    Serial.println(F("  STEP   <hex14>       drive + 1ms settle + read"));
    Serial.println(F("  SWEEP  <a> <b> [s]   iterate STEP over [a..b] step s"));
    Serial.println(F("  STATUS               VCC + init state + register readback"));
}

static void printStatus() {
    Serial.print(F("Galdurino-BB v0.2 (SPI/MCP23S17)  VCC="));
    Serial.print(vccOn ? F("ON") : F("OFF"));
    Serial.print(F("  INIT="));
    Serial.println(inited ? F("YES") : F("NO"));
    if (inited) {
        Serial.print(F("U1 IODIRA=")); printHex(spiRead(U1_HA, REG_IODIRA), 2);
        Serial.print(F(" IODIRB="));  printHex(spiRead(U1_HA, REG_IODIRB), 2);
        Serial.print(F(" GPIOA="));   printHex(spiRead(U1_HA, REG_GPIOA), 2);
        Serial.print(F(" GPIOB="));   printHex(spiRead(U1_HA, REG_GPIOB), 2);
        Serial.println();
        Serial.print(F("U2 IODIRA=")); printHex(spiRead(U2_HA, REG_IODIRA), 2);
        Serial.print(F(" GPIOA="));   printHex(spiRead(U2_HA, REG_GPIOA), 2);
        Serial.print(F(" IOCON="));   printHex(spiRead(U2_HA, REG_IOCON), 2);
        Serial.println();
    }
}

static uint32_t parseHex(const char *s, char **endp) {
    return strtoul(s, endp, 16);
}

static void handleCommand(String &line) {
    line.trim();
    line.toUpperCase();
    if (line.length() == 0) return;

    if (line == "HELP" || line == "?") { printHelp(); return; }
    if (line == "STATUS")               { printStatus(); return; }

    if (line == "INIT") {
        mcpInit();
        Serial.println(F("OK INIT"));
        return;
    }

    if (line == "POWER ON") {
        digitalWrite(VCC_CTRL, HIGH);
        vccOn = true;
        delay(20);
        Serial.println(F("OK POWER ON"));
        return;
    }
    if (line == "POWER OFF") {
        if (inited) driveInputs(0);
        digitalWrite(VCC_CTRL, LOW);
        vccOn = false;
        Serial.println(F("OK POWER OFF"));
        return;
    }

    if (line.startsWith("DRIVE ")) {
        if (warnUninited()) return;
        uint32_t p = parseHex(line.c_str() + 6, NULL);
        driveInputs((uint16_t)p);
        Serial.println(F("OK"));
        return;
    }

    if (line == "READ") {
        if (warnUninited()) return;
        uint8_t v = readOutputs();
        printHex(v, 2); Serial.println();
        return;
    }

    if (line.startsWith("STEP ")) {
        if (warnUninited()) return;
        uint32_t p = parseHex(line.c_str() + 5, NULL);
        doStep((uint16_t)p);
        return;
    }

    if (line.startsWith("SWEEP ")) {
        if (warnUninited()) return;
        char *cur;
        uint32_t a = parseHex(line.c_str() + 6, &cur);
        uint32_t b = parseHex(cur, &cur);
        uint32_t s = 1;
        while (*cur == ' ') cur++;
        if (*cur) s = parseHex(cur, NULL);
        if (s == 0) s = 1;
        if (b < a)  b = a;
        if (a > 0x3FFF) a = 0x3FFF;
        if (b > 0x3FFF) b = 0x3FFF;

        Serial.print(F("BEGIN "));
        printHex(a, 4); Serial.print(' ');
        printHex(b, 4); Serial.print(' ');
        printHex(s, 4); Serial.println();
        for (uint32_t p = a; p <= b; p += s) {
            driveInputs((uint16_t)p);
            delayMicroseconds(500);
            uint8_t out = readOutputs();
            printHex(p, 4); Serial.print(','); printHex(out, 2); Serial.println();
            if (p + s < p) break;   // overflow guard
        }
        Serial.println(F("END"));
        return;
    }

    Serial.print(F("? unknown: "));
    Serial.println(line);
}

// ---- Arduino boilerplate ------------------------------------------------
void setup() {
    pinMode(VCC_CTRL, OUTPUT);
    digitalWrite(VCC_CTRL, LOW);

    pinMode(CS_PIN, OUTPUT);
    digitalWrite(CS_PIN, HIGH);          // deassert /CS before SPI starts
    SPI.begin();

    Serial.begin(115200);
    inputString.reserve(64);
    Serial.println(F("Galdurino-BB v0.2 (SPI/MCP23S17) ready. Type HELP."));
}

void loop() {
    if (stringComplete) {
        stringComplete = false;
        String line = inputString;
        inputString = "";
        handleCommand(line);
    }
}

void serialEvent() {
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\r') continue;
        if (c == '\n') { stringComplete = true; return; }
        if (inputString.length() < 60) inputString += c;
    }
}
