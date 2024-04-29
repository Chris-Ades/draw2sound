// Referenced
// https://github.com/GitJer/Some_RPI-Pico_stuff/tree/main/button_matrix_4x4
// Referenced https://github.com/infovore/pico-example-midi

// fix pitch bend
// do custom settings
// rw_midi

#include <cstring>
#include <stdio.h>

#include <cmath>
#include <cstdint>
#include <cstdio>

#include "bsp/board.h"
#include "hardware/adc.h"
#include "hardware/gpio.h"
#include "hardware/uart.h"
#include "pico/stdlib.h"
#include "tusb.h"
#include <PicoLed.hpp>

enum {
  BLINK_NOT_MOUNTED = 250,
  BLINK_MOUNTED = 1000,
  BLINK_SUSPENDED = 2500,
};

#define UART_ID uart0
#define BAUD_RATE 38400
#define UART_TX_PIN 0
#define UART_RX_PIN 1

#define LED_COUNT 24
#define LED_PIN 9

static const uint SHIFT_PIN = 2;
static const uint base_output = 16;
static const uint base_input = 10;

// Places to store values from right
uint16_t right, oldRight;
uint32_t left, oldLeft;
uint8_t analog[6];
uint8_t oldAnalog[6];
// Rolling average history to get around ADC noise
static const uint historySize = 150;
uint16_t dial1History[historySize] = {0};
uint16_t dial2History[historySize] = {0};
uint16_t dial3History[historySize] = {0};
uint8_t historyIndex = 0;
long history1Sum = 0;
long history2Sum = 0;
long history3Sum = 0;

enum analogType { dial1, dial2, dial3, fader1, fader2, ctrl };
bool shift, ctrlMode, modMode, rw_midi, needLEDUpdate;

char recvBuf[60];
uint8_t recvPtr = 0;

// Translates matrix position (index) to key number (value)
static const uint8_t keyTranslation[24] = {20, 19, 18, 17, 16, 15, 21, 22,
                                           23, 12, 13, 14, 8,  7,  6,  5,
                                           4,  3,  9,  10, 11, 0,  1,  2};
// Translates LED position into logical number
static const uint8_t ledTrans[24] = {20, 19, 18, 17, 16, 15, 14, 13,
                                     12, 23, 22, 21, 8,  7,  6,  5,
                                     4,  3,  2,  1,  0,  11, 10, 9};
// modify dissonance when not in 12edo
static const uint8_t rwDisTrans[13] = {1, 1, 1, 2, 3, 3, 4, 4, 5, 7, 6, 9, 7};
// another translation table bc i kinda screwed up ledTrans, don't even worry
// about it
static const uint8_t rwLEDCCW[12] = {9, 10, 11, 5, 4, 3, 2, 1, 0, 6, 7, 8};
uint8_t rwKeys = 12; // how many keys the root wheel has
// last index of rootwheel, so when baseFreq is changed,
// rootFreq can be changed without pressing the rw button again
uint8_t last_rw = 0;

float baseFreq = 261.626; // what is set by dial2
float rootFreq = 261.626; // root of chord set by rootwheel
uint8_t numKeys = 13;     // how many keys are active on right
union {                   // union type my beloved
  float f;                // this was necessary when using i2c
  uint32_t num; // but on uart it probably just makes more sense to use stof
} ratio = {.f = 1.05946309436};
uint16_t mask = 0x1FFF; // what bits are active for modmode

int8_t channels[16] = {-1}; // each button on shaper is assigned a channel
static const uint8_t volume = 127; // volume is changed in synth

// for USB status
static uint32_t blink_interval_ms = BLINK_NOT_MOUNTED;

int miaMap(float input, int input_start, int input_end, int output_start,
           int output_end) {
  float slope = 1.0 * (output_end - output_start) / (input_end - input_start);
  return output_start + roundf(slope * (input - input_start));
}

void matrix_task() {
  oldLeft = left;
  left = 0;
  // tried to be clever and do this on pio
  // didn't work :(
  for (int i = 0; i < 4; i++) {
    gpio_put(base_output + i, 1);
    sleep_us(10);
    uint8_t rawIn = (gpio_get_all() >> base_input) & 0b111111;
    left |= rawIn << (i * 6);
    gpio_put(base_output + i, 0);
  }
  /*
  if (left != 0) { // a key was pressed: print its number
    for (int i = 23; i >= 0; i--) {
      printf("%d", (left >> i) & 1);
      if ((left >> i) & 1) {
        printf("%d\n", i);
      }
    }
    printf("\n");
  }*/
}

//--------------------------------------------------------------------+
// Device callbacks
//--------------------------------------------------------------------+

// Invoked when device is mounted
void tud_mount_cb(void) { blink_interval_ms = BLINK_MOUNTED; }

// Invoked when device is unmounted
void tud_umount_cb(void) { blink_interval_ms = BLINK_NOT_MOUNTED; }

// Invoked when usb bus is suspended
// remote_wakeup_en : if host allow us  to perform remote wakeup
// Within 7ms, device must draw an average of current less than 2.5 mA from bus
void tud_suspend_cb(bool remote_wakeup_en) {
  (void)remote_wakeup_en;
  blink_interval_ms = BLINK_SUSPENDED;
}

// Invoked when usb bus is resumed
void tud_resume_cb(void) { blink_interval_ms = BLINK_MOUNTED; }

void uart_setup() {
  // Set up our UART with the required speed.
  uart_init(UART_ID, BAUD_RATE);

  // Set the TX and RX pins by using the function select on the GPIO
  // Set datasheet for more information on function select
  gpio_set_function(UART_TX_PIN, GPIO_FUNC_UART);
  gpio_set_function(UART_RX_PIN, GPIO_FUNC_UART);
  uart_set_hw_flow(UART_ID, false, false);
}

/*void print_sysex(int len) {
  if (len > 61)
    return;
  uint8_t msg[64];
  msg[0] = 0b11110000;
  msg[1] = 0b01010101;
  memcpy(&msg[2], sendStr, len);
  msg[len + 2] = 0b11110111;
  tud_midi_stream_write(0, msg, len + 3);
}*/

// these is used instead of stol since substrings aren't null terminated
// probably faster too, but eh
uint16_t hexto16(char *hex) {
  uint16_t val = 0;
  for (int i = 0; i < 4; i++) {
    // get current character then increment
    uint8_t byte = *hex++;
    // transform hex character to the 4bit equivalent number, using the ascii
    // table indexes
    if (byte >= '0' && byte <= '9')
      byte = byte - '0';
    else if (byte >= 'A' && byte <= 'F')
      byte = byte - 'A' + 10;
    else if (byte >= 'a' && byte <= 'f')
      byte = byte - 'a' + 10;
    // shift 4 to make space for new digit, and add the 4 bits of the new digit
    val = (val << 4) | (byte & 0xF);
  }
  return val;
}
uint8_t hexto8(char *hex) {
  uint8_t val = 0;
  for (int i = 0; i < 2; i++) {
    // get current character then increment
    uint8_t byte = *hex++;
    // transform hex character to the 4bit equivalent number, using the ascii
    // table indexes
    if (byte >= '0' && byte <= '9')
      byte = byte - '0';
    else if (byte >= 'A' && byte <= 'F')
      byte = byte - 'A' + 10;
    else if (byte >= 'a' && byte <= 'f')
      byte = byte - 'a' + 10;
    // shift 4 to make space for new digit, and add the 4 bits of the new digit
    val = (val << 4) | (byte & 0xF);
  }
  return val;
}

void read_right() {
  oldRight = right;
  while (uart_is_readable(UART_ID)) { // most of the time this will be false
    recvBuf[recvPtr] = uart_getc(UART_ID);
    // if we see the end of a message
    if (recvBuf[recvPtr] == '@') {
      // Check if we have the beginning marker where we expect
      // there were so many off by one errors in this :(
      if (recvPtr >= 5 && recvBuf[recvPtr - 5] == '!') {
        // Valid transaction
        right = hexto16(&recvBuf[recvPtr - 4]);
      }
      // clear buffer
      memset(recvBuf, 0, sizeof(recvBuf));
      recvPtr = 0;
      // analog events are marked by other begin/end markers
    } else if (recvBuf[recvPtr] == '$') {
      if (recvPtr >= 3 && recvBuf[recvPtr - 3] == '#') {
        analog[fader1] = hexto8(&recvBuf[recvPtr - 2]);
      }
      memset(recvBuf, 0, sizeof(recvBuf));
      recvPtr = 0;
    } else if (recvBuf[recvPtr] == '*') {
      if (recvPtr >= 3 && recvBuf[recvPtr - 3] == '&') {
        analog[fader2] = hexto8(&recvBuf[recvPtr - 2]);
      }
      memset(recvBuf, 0, sizeof(recvBuf));
      recvPtr = 0;
    } else if (recvBuf[recvPtr] == ')') {
      if (recvPtr >= 3 && recvBuf[recvPtr - 3] == '(') {

        analog[ctrl] = hexto8(&recvBuf[recvPtr - 2]);
      }
      memset(recvBuf, 0, sizeof(recvBuf));
      recvPtr = 0;
    } else {
      recvPtr++;
      if (recvPtr >= 60) // im not gonna use modulo, you can't make me!!
        recvPtr = 0;
    }
  }
}

// this name is vague on purpose. sorry not sorry :3
void write_right(uint8_t i) {
  uint8_t sendBuf[6];
  if (i == dial2) {
    uint16_t roundBaseFreq = roundf(rootFreq);
    sprintf((char *)sendBuf, "!%04X@", roundBaseFreq);
    uart_write_blocking(UART_ID, sendBuf, 6);
  } else if (i == dial3) {
    sprintf((char *)sendBuf, "#%02X$", numKeys);
    uart_write_blocking(UART_ID, sendBuf, 4);
  }
}

PicoLed::Color freqToColor(uint64_t freq) {
  // Get the place value of the most significant bit in input:
  int input_msb_position = 63 ^ __builtin_clzll(freq);
  // We want the output to be >= 2^47,
  // so we need to shift input to the right until the MSB position is 47:
  // then convert from m to nm for below function
  float wavelength = 1e9 * 299792458.0 / (freq << (47 - input_msb_position));
  while (wavelength > 750) // lets try to eliminate this
    wavelength /= 2;

  // https://gist.github.com/friendly/67a7df339aa999e2bcfcfec88311abfc
  float R, G, B;
#define gamma 0.8
  if (wavelength >= 375 & wavelength <= 440) {
    float attenuation = 0.3 + 0.7 * (wavelength - 380) / (440 - 380);
    R = pow(((-(wavelength - 440) / (440 - 380)) * attenuation), gamma);
    G = 0.0;
    B = pow((1.0 * attenuation), gamma);
  } else if (wavelength >= 440 & wavelength <= 490) {
    R = 0.0;
    G = pow(((wavelength - 440) / (490 - 440)), gamma);
    B = 1.0;
  } else if (wavelength >= 490 & wavelength <= 510) {
    R = 0.0;
    G = 1.0;
    B = pow((-(wavelength - 510) / (510 - 490)), gamma);
  } else if (wavelength >= 510 & wavelength <= 580) {
    R = pow(((wavelength - 510) / (580 - 510)), gamma);
    G = 1.0;
    B = 0.0;
  } else if (wavelength >= 580 & wavelength <= 645) {
    R = 1.0;
    G = pow((-(wavelength - 645) / (645 - 580)), gamma);
    B = 0.0;
  } else if (wavelength >= 645 & wavelength <= 750) {
    float attenuation = 0.3 + 0.7 * (750 - wavelength) / (750 - 645);
    R = pow((1.0 * attenuation), gamma);
    G = 0.0;
    B = 0.0;
  } else {
    R = 1.0;
    G = 1.0;
    B = 1.0;
  }
  // floating point begone
  R = R * 255;
  G = G * 255;
  B = B * 255;
  // return (((uint8_t)R) << 16) | (((uint8_t)G) << 8) | ((uint8_t)B);
  // printf("%lld %.9g %d %d %d\n", freq, wavelength, (uint8_t)R, (uint8_t)G,
  //       (uint8_t)B);
  // these casts are probably not necessary but had problems
  return PicoLed::RGB((uint8_t)R, (uint8_t)G, (uint8_t)B);
}

float keyToFreq(uint8_t key) {
  return baseFreq *
         pow(ratio.f, ((keyTranslation[key] * rwDisTrans[rwKeys]) % rwKeys));
}

void write_led(auto strip) {
  // needLEDUpdate is just so strip isn't global bc i couldn't
  // figure out the typing lmao
  if (needLEDUpdate) {
    needLEDUpdate = false;
    strip.clear();
    // this shouldn't need keyTranslation, but i don't want to remake the table
    for (int i = 0; i < rwKeys; i++) {
      strip.setPixelColor(ledTrans[keyTranslation[rwLEDCCW[i]]],
                          freqToColor(keyToFreq(rwLEDCCW[i])));
      strip.setPixelColor(ledTrans[keyTranslation[rwLEDCCW[i] + 12]],
                          freqToColor(keyToFreq(rwLEDCCW[i])));
    }
    strip.show();
  }
}

// https://gist.github.com/bmccormack/d12f4bf0c96423d03f82
uint16_t movingAvg(uint16_t *ptrArrNumbers, long *ptrSum, int pos, int len,
                   int nextNum) {
  // Subtract the oldest number from the prev sum, add the new number
  *ptrSum = *ptrSum - ptrArrNumbers[pos] + nextNum;
  // Assign the nextNum to the position in the array
  ptrArrNumbers[pos] = nextNum;
  // return the average
  return *ptrSum / len;
}

void read_local() {
  adc_select_input(0);
  analog[dial1] = movingAvg(dial1History, &history1Sum, historyIndex,
                            historySize, adc_read()) >>
                  5;
  adc_select_input(1);
  analog[dial2] = movingAvg(dial2History, &history2Sum, historyIndex,
                            historySize, adc_read()) >>
                  5;
  adc_select_input(2);
  analog[dial3] = movingAvg(dial3History, &history3Sum, historyIndex,
                            historySize, adc_read()) >>
                  5;

  shift = !gpio_get(SHIFT_PIN);

  historyIndex++;
  if (historyIndex >= historySize) {
    historyIndex = 0;
  }
}

void write_freq(float freq, uint8_t chan) {
  // printf("Writing freq %f\n", freq);
  // print_sysex(sprintf(sendStr, "%.15f", freq));
  uint8_t msg[3];
  float note = 12 * log2(freq / 440) + 69; // Frequency to midi notex
  int8_t baseNote = roundf(note);          // We encode the note as midi + bend
  // 8192 is no bend, 16383 is 2 semitones up, 0 is 2 semitones down
  // this is done in midi note, not freq, since that's by semitone
  uint16_t bendNote = miaMap(note - baseNote, -2, 2, 0, 16383);

  channels[chan] = baseNote;

  msg[0] = 0b11100000 | chan;
  msg[1] = bendNote & 0x7F;
  msg[2] = bendNote >> 7;
  tud_midi_stream_write(0, msg, 3);

  msg[0] = 0b10010000 | chan;
  msg[1] = baseNote;
  msg[2] = volume;
  tud_midi_stream_write(0, msg, 3);
}

void off_freq(uint8_t chan) {
  // note off is by note, but button change is by channel, so chan[] translates
  uint8_t msg[3];

  msg[0] = 0b10000000 | chan;
  msg[1] = channels[chan];
  msg[2] = 127;
  tud_midi_n_stream_write(0, 0, msg, 3);

  channels[chan] = -1;
}

void change_freq(int rw_index) {
  // if called with -1, we are changing frequency for something other that
  // pressing the rootwheel (like changing a dial), so don't clobber which root
  // we're on
  if (rw_index >= 0) {
    last_rw = rw_index;
  }
  rootFreq = keyToFreq(last_rw);
  // uint8_t sendBuf[18];
  // sprintf((char *)sendBuf, "%d\n", keyTranslation[last_rw]);
  // uart_write_blocking(UART_ID, sendBuf, 3);
  if (last_rw > 11) {
    rootFreq *= 2;
  }
  needLEDUpdate = true;
  for (int i = 0; i < 13; i++) {
    bool oldBit = (oldRight >> i) & 1;
    if (oldBit) {
      // print_sysex(sprintf(sendStr, "%d", i));
      off_freq(i);
      write_freq(rootFreq * pow(ratio.f, i), i);
    }
  }
  if (rw_index >= 0) {
    write_right(dial2);
  }
}

void check_notes() {
  if (oldLeft != left) {
    for (int i = 0; i < 24; i++) {
      bool oldbit = (oldLeft >> i) & 1;
      bool newbit = (left >> i) & 1;
      if (shift && (i == 20)) {
        rw_midi = newbit;
      }
      if (!oldbit && newbit && (keyTranslation[i] % 12 < rwKeys)) {
        // print_sysex(sprintf(sendStr, "%d", i));
        change_freq(i);
        if (rw_midi) {
          write_freq(rootFreq, 15);
        }
      }
      if (oldbit && !newbit) {
        off_freq(15);
      }
    }
  }
  if (oldRight != right) {
    for (int i = 0; i < 13; i++) {
      bool oldBit = (oldRight >> i) & 1;
      bool newBit = (right >> i) & 1;
      if (oldBit & !newBit) { // note has turned off
        off_freq(i);
        continue;
      }
      if (!oldBit & newBit) {
        write_freq(rootFreq * pow(ratio.f, i), i);
        continue;
      }
    }
  }
}

void check_analog() {
  for (uint8_t i = 0; i < 6; i++) {
    if (analog[i] != oldAnalog[i]) {
      if (!shift) {
        // printf("Analog %d: %d\n", i, analog[i]);
        if (i == ctrl && ctrlMode)
          continue;
        uint8_t msg[3];
        msg[0] = 0b10110000;
        msg[1] = i;
        msg[2] = analog[i];
        tud_midi_n_stream_write(0, 0, msg, 3);
      } else {
        ctrlMode = analog[fader1] > 64;
        // Scales 0-127 to 1-13
        numKeys = miaMap(analog[dial3], 0, 127, 2, 13);
        // Simple LED mask for rn
        mask = 0x1FFF >> (13 - numKeys);
        // 16.0 is arbituary, corresponds to 128/16=8 semitones
        baseFreq = 261.626 / pow(ratio.f, analog[dial2] / 16.0);
        change_freq(-1);
        // Scales 0-127 to 0-11
        rwKeys = miaMap(analog[dial1], 0, 127, 1, 12);
        modMode = (analog[fader2] > 64) && (numKeys == rwKeys);
        ratio.f = pow(2, 1.0 / (numKeys-1));
        /*if (numKeys == 13) {
          ratio.f = 1.05946309436;
        } else {
          ratio.f = pow(2, 1.0 / numKeys);
        }*/
        if (i == dial2 || i == dial3) {
          write_right(i);
        }
      }
      oldAnalog[i] = analog[i];
    }
  }
}

//--------------------------------------------------------------------+
// BLINKING TASK
//--------------------------------------------------------------------+
void led_blinking_task(void) {
  static uint32_t start_ms = 0;
  static bool led_state = false;

  // Blink every interval ms
  if (board_millis() - start_ms < blink_interval_ms)
    return; // not enough time
  start_ms += blink_interval_ms;

  board_led_write(led_state);
  led_state = 1 - led_state; // toggle
}

int main() {
  board_init();
  tud_init(0);
  uart_setup();

  adc_init();
  adc_gpio_init(26);
  adc_gpio_init(27);
  adc_gpio_init(28);

  gpio_init(SHIFT_PIN);
  gpio_set_dir(SHIFT_PIN, GPIO_IN);
  gpio_pull_up(SHIFT_PIN);

  for (int i = 0; i < 4; i++) {
    // output pins
    gpio_init(base_output + i);
    gpio_set_dir(base_output + i, GPIO_OUT);
  }
  for (int i = 0; i < 6; i++) {
    // input pins with pull down
    gpio_init(base_input + i);
    gpio_set_dir(base_input + i, GPIO_IN);
    gpio_pull_down(base_input + i);
  }

  auto strip = PicoLed::addLeds<PicoLed::WS2812B>(
      pio1_hw, 3, LED_PIN, LED_COUNT, PicoLed::FORMAT_GRB);
  strip.setBrightness(255);
  strip.fill(PicoLed::RGB(255, 0, 0));
  strip.show();

  while (true) { // MRTOS (Mia's Real Time Operating System)
    read_local();
    read_right();
    check_analog();
    matrix_task();
    check_notes();

    uint8_t packet[4];
    while (tud_midi_available())
      tud_midi_packet_read(packet);
    tud_task(); // tinyusb device task
    write_led(strip);
    led_blinking_task();
  }
}
