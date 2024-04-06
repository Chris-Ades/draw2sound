// Referenced
// https://github.com/GitJer/Some_RPI-Pico_stuff/tree/main/button_matrix_4x4
// Referenced https://github.com/infovore/pico-example-midi

// fix pitch bend
// do custom settings
// rw_midi

#include <Adafruit_NeoPixel.h>
// #include <midi_device.h>
#include <stdio.h>

#include <cmath>
#include <cstdint>
#include <cstdio>

#include "bsp/board.h"
#include "hardware/adc.h"
#include "hardware/gpio.h"
#include "hardware/i2c.h"
#include "left.pio.h"
#include "pico/stdlib.h"
#include "tusb.h"

enum {
  BLINK_NOT_MOUNTED = 250,
  BLINK_MOUNTED = 1000,
  BLINK_SUSPENDED = 2500,
};

static const uint I2C_SLAVE_ADDRESS = 112;
static const uint I2C_BAUDRATE = 100000; // 100 kHz
static const uint I2C_MASTER_SDA_PIN = 0;
static const uint I2C_MASTER_SCL_PIN = 1;
static const uint LED_PIN = PICO_DEFAULT_LED_PIN;
static const uint SHIFT_PIN = 2;
static const uint base_output = 16;
static const uint base_input = 10;
static const uint historySize = 150;

// Places to store values from right
uint16_t right, oldRight;
uint32_t left, oldLeft;
uint8_t analog[6];
uint8_t oldAnalog[6];
// Rolling average history
uint16_t dial1History[historySize] = {0};
uint16_t dial2History[historySize] = {0};
uint16_t dial3History[historySize] = {0};
uint8_t historyIndex = 0;
long history1Sum = 0;
long history2Sum = 0;
long history3Sum = 0;
enum analogType { dial1, dial2, dial3, fader1, fader2, ctrl };
bool shift, ctrlMode, modMode;

// Translates matrix position (index) to key number (value)
uint8_t keyTranslation[24] = {20, 19, 18, 17, 16, 15, 21, 22, 23, 12, 13, 14,
                              8,  7,  6,  5,  4,  3,  9,  10, 11, 0,  1,  2};
uint8_t rwKeys = 12;

uint16_t baseFreq = 262; // C4
uint16_t rootFreq = 262;
uint8_t numKeys = 13;
union { // union type my beloved
  float f;
  unsigned char bytes[4];
} ratio = {.f = 1.05946309436};
uint16_t mask = 0x1FFF; // 13 bits

int8_t channels[16] = {-1};
uint8_t volume = 127; // This is encoded in the velocity

static uint32_t blink_interval_ms = BLINK_NOT_MOUNTED;

void led_blinking_task(void);
void midi_task(void);
void matrix_task(void);

// class that sets up and reads the 4x4 button matrix
/*class button_matrix {
public:
                // constructor
                // base_input is the starting gpio for the 4 input pins
                // base_output is the starting gpio for the 4 output pins
                button_matrix(uint base_input, uint base_output) {
                                pio = pio1;
                                sm = pio_claim_unused_sm(pio, true);
                                for (int i = 0; i < 4; i++) {
                                                pio_gpio_init(pio, base_output +
i);
                                }
                                for (int i = 0; i < 6; i++) {
                                                pio_gpio_init(pio, base_input +
i); gpio_pull_down(base_input + i);
                                }
                                // load the pio program into the pio memory
                                uint offset = pio_add_program(pio,
&button_matrix_program);
                                // make a sm config
                                pio_sm_config c =
button_matrix_program_get_default_config(offset); sm_config_set_in_pins(&c,
base_input); pio_sm_set_consecutive_pindirs(pio, sm, base_output, 4, true);
                                sm_config_set_set_pins(&c, base_output, 4);
                                // 6*4=24
                                sm_config_set_in_shift(&c, 1, 1, 24);
                                // init the pio sm with the config
                                pio_sm_init(pio, sm, offset, &c);
                                // enable the sm
                                pio_sm_set_enabled(pio, sm, true);
                }

                // read the 4x4 matrix
                int read(void) {
                                // value is used to read from the fifo
                                uint32_t value = 0;
                                // clear the FIFO, we only want a currently
pressed key pio_sm_clear_fifos(pio, sm);
                                // give the sm some time to fill the FIFO if a
key is being pressed sleep_ms(1);
                                // check that the FIFO isn't empty
                                if (pio_sm_is_rx_fifo_empty(pio, sm)) {
                                                return -1;
                                }
                                // read one data item from the FIFO
                                return pio_sm_get(pio, sm);
                }

private:
                // the pio instance
                PIO pio;
                // the state machine
                uint sm;
};
button_matrix *my_matrix;*/

void matrix_task() {
  // read the matrix of buttons
  oldLeft = left;
  left = 0;
  // left = my_matrix->read();
  for (int i = 0; i < 4; i++) {
    gpio_put(base_output + i, 1);
    sleep_us(10);
    uint8_t rawIn = (gpio_get_all() >> base_input) & 0b111111;
    left |= rawIn << (i * 6);
    gpio_put(base_output + i, 0);
  }
  if (left != 0) { // a key was pressed: print its number
    for (int i = 23; i >= 0; i--) {
      // printf("%d", (left >> i) & 1);
      if ((left >> i) & 1) {
        printf("%d\n", i);
      }
    }
    printf("\n");
  }
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

void setup_i2c() {
  gpio_init(I2C_MASTER_SDA_PIN);
  gpio_set_function(I2C_MASTER_SDA_PIN, GPIO_FUNC_I2C);
  // pull-ups are already active on slave side, this is just a fail-safe in case
  // the wiring is faulty
  gpio_pull_up(I2C_MASTER_SDA_PIN);

  gpio_init(I2C_MASTER_SCL_PIN);
  gpio_set_function(I2C_MASTER_SCL_PIN, GPIO_FUNC_I2C);
  gpio_pull_up(I2C_MASTER_SCL_PIN);

  i2c_init(i2c0, I2C_BAUDRATE);
}

void read_right() {
  uint8_t buf[5];
  buf[0] = 0; // Read from address zero
  int count = i2c_write_blocking(i2c0, I2C_SLAVE_ADDRESS, buf, 1, true);
  count = i2c_read_blocking(i2c0, I2C_SLAVE_ADDRESS, buf, 5, true);
  oldRight = right; // checkNote MUST be run after this to detect the changes
  right = buf[0] << 8 | buf[1];
  analog[fader1] = buf[2];
  analog[fader2] = buf[3];
  analog[ctrl] = buf[4];
}

void write_right() { // this name is vague on purpose. sorry not sorry :3
  uint8_t buf[10];
  buf[0] = 2;             // address we are writing to
  buf[1] = baseFreq >> 8; // Big endian uint16
  buf[2] = baseFreq & 0xFF;
  buf[3] = numKeys;
  for (int i = 0; i < 4; i++)
    buf[4 + i] = ratio.bytes[i];
  buf[8] = mask >> 8;
  buf[9] = mask & 0xFF;
  i2c_write_blocking(i2c0, I2C_SLAVE_ADDRESS, buf, 10, true);
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
  printf("Writing freq %f\n", freq);
  uint8_t msg[3];
  float note = 12 * log2(freq / 440) + 69; // Frequency to midi note
  int8_t baseNote = roundf(note);          // We encode the note as midi + bend
  // 4096 is no bend, 8192 is 2 semitones up, 0 is 2 semitones down
  uint16_t bendNote = roundf(((note - baseNote) * 4096.0) + 8192.0);

  channels[chan] = baseNote;

  msg[0] = 0b11100000 | chan;
  msg[1] = bendNote & 0x7F;
  msg[2] = bendNote >> 7;
  tud_midi_stream_write(0, msg, 3);

  msg[0] = 0b10010000 | chan;
  msg[1] = baseNote;
  msg[2] = volume;
  printf("%d %d %d \n", msg[0], msg[1], msg[2]);
  tud_midi_stream_write(0, msg, 3);
}

void off_freq(uint8_t chan) {
  uint8_t msg[3];

  msg[0] = 0b10000000 | chan;
  msg[1] = channels[chan];
  msg[2] = 127;
  tud_midi_n_stream_write(0, 0, msg, 3);

  channels[chan] = -1;
}

void check_notes() {
  // I'm assuming that bits 23-12 are the outside buttons starting from 9
  // o'clock and 11-0 are the inside with the same pattern
  if (oldLeft != left) {
    for (int i = 0; i < 24; i++) {
      bool oldbit = (oldLeft >> i) & 1;
      bool newbit = (left >> i) & 1;
      if (!oldbit && newbit) {
        rootFreq =
            baseFreq /
            pow(ratio.f, ((keyTranslation[i] * 5) %
                          12)); // 12 would be reduced. bounce around order
        if (i > 11) {
          rootFreq *= pow(ratio.f, 12);
        }
        for (int i = 0; i < 13; i++) {
          bool oldBit = (oldRight >> i) & 1;
          if (oldBit) {
            off_freq(i);
            write_freq(rootFreq * pow(ratio.f, i), i);
          }
        }
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
  if (!shift) {
    for (uint8_t i = 0; i < 6; i++) {
      if (analog[i] != oldAnalog[i]) {
        // printf("Analog %d: %d\n", i, analog[i]);
        if (i == ctrl && ctrlMode)
          continue;
        uint8_t msg[3];
        msg[0] = 0b10110000;
        msg[1] = i;
        msg[2] = analog[i];
        tud_midi_n_stream_write(0, 0, msg, 3);
        oldAnalog[i] = analog[i];
      }
    }
  } else {
    ctrlMode = analog[fader1] > 64;

    //Scales 0-127 to 0-13
	numKeys = roundf(analog[dial3] / 9.7692307692);
    //Simple LED mask for rn
	mask = 0x1FFF >> (13 - numKeys);
    //This is kinda bs, should we do it by multiplication?
	baseFreq = 262 + analog[dial2] * 2;
	// Scales 0-127 to 0-13
	rwKeys = roundf(analog[dial1] / 10.5833333333);
	modMode = (analog[fader2] > 64) && (numKeys == rwKeys);
	if (rwKeys == 13) {
		ratio.f = 1.05946309436;
    } else {
      ratio.f = pow(2, 1.0 / rwKeys);
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
  // needed for printf
  stdio_init_all();
  printf("Hewwo world!\n");
  board_init();
  tusb_init(); // i have no idea which one of these is actually needed
  tud_init(0);
  // stdio_usb_init();
  setup_i2c();

  adc_init();
  adc_gpio_init(26);
  adc_gpio_init(27);
  adc_gpio_init(28);
  gpio_init(SHIFT_PIN);
  gpio_set_dir(SHIFT_PIN, GPIO_IN);
  gpio_pull_up(SHIFT_PIN);
  // my_matrix = new button_matrix((uint)10, (uint)16);
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
    led_blinking_task();
    // tud_cdc_n_write_flush(0);
  }
}
