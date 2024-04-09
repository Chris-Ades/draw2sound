// Referenced
// https://github.com/GitJer/Some_RPI-Pico_stuff/tree/main/button_matrix_4x4
// Referenced
// https://github.com/vmilea/pico_i2c_slave/tree/master?tab=readme-ov-file

#include <array>
#include <cstdint>
#include <math.h>
#include <stdio.h>

#include "hardware/adc.h"
#include "hardware/gpio.h"
#include "pico/stdlib.h"
#include "right.pio.h"

#include "i2c_slave/include/i2c_fifo.h"
#include "i2c_slave/include/i2c_slave.h"

#include <Adafruit_NeoPixel.h>

static const uint I2C_SLAVE_ADDRESS = 112; // we address in decimal
static const uint I2C_BAUDRATE = 100000;   // 100 kHz

static const uint I2C_SLAVE_SDA_PIN = 20;
static const uint I2C_SLAVE_SCL_PIN = 21;

static const uint base_output = 9;
static const uint base_input = 13;

// Converts left to right LED index to logical address
static const uint8_t ledTrans[13] = {6, 5, 7, 4, 8, 3, 9, 2, 10, 1, 11, 0, 12};

static const uint historySize = 150;
uint16_t dial1History[historySize] = {0};
uint16_t dial2History[historySize] = {0};
uint16_t dial3History[historySize] = {0};
uint8_t historyIndex = 0;
long history1Sum = 0;
long history2Sum = 0;
long history3Sum = 0;

bool ledUpdated = false;

#define LED_COUNT 13
#define LED_PIN 0
Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

// this is where i2c writes go. Doesn't neeed to be 256 bytes but
// i don't want addresses to rollover
static struct {
  uint8_t mem[256];
  uint8_t mem_address;
  bool mem_address_written;
} context;

template <int N> struct LUT {
  constexpr LUT() : values() {
    // int map[13] = {11, 7, 2, 1, 12, 9, 5, 3, 8, 4, 10, 0, 10, 6, 14, 2};
    int map[13] = {11, 3, 15, 7, 9, 6, 13, 1, 8, 5, 12, 0, 4};
    for (auto arrayPos = 0; arrayPos < N; ++arrayPos) {
      for (int bitPos = 0; bitPos < 13; bitPos++) {
        // values[arrayPos] =
        // values[arrayPos] | (((arrayPos >> bitPos) & 1) << map[bitPos]);
        values[arrayPos] |= (((arrayPos >> map[bitPos]) & 1) << bitPos);
      }
    }
  }
  uint16_t values[N];
};

constexpr auto buttonLookup = LUT<65535>();

static void i2c_slave_handler(i2c_inst_t *i2c, i2c_slave_event_t event) {
  switch (event) {
  case I2C_SLAVE_RECEIVE: // master has written some data
    if (!context.mem_address_written) {
      // writes always start with the memory address
      context.mem_address = i2c_read_byte(i2c);
      context.mem_address_written = true;
    } else {
      // save into memory
      context.mem[context.mem_address] = i2c_read_byte(i2c);
      context.mem_address++;
      ledUpdated = true;
    }
    break;
  case I2C_SLAVE_REQUEST: // master is requesting data
    // load from memory
    i2c_write_byte(i2c, context.mem[context.mem_address]);
    context.mem_address++;
    break;
  case I2C_SLAVE_FINISH: // master has signalled Stop / Restart
    context.mem_address_written = false;
    break;
  default:
    break;
  }
}

static void setup_slave() {
  gpio_init(I2C_SLAVE_SDA_PIN);
  gpio_set_function(I2C_SLAVE_SDA_PIN, GPIO_FUNC_I2C);
  gpio_pull_up(I2C_SLAVE_SDA_PIN);

  gpio_init(I2C_SLAVE_SCL_PIN);
  gpio_set_function(I2C_SLAVE_SCL_PIN, GPIO_FUNC_I2C);
  gpio_pull_up(I2C_SLAVE_SCL_PIN);

  i2c_init(i2c0, I2C_BAUDRATE);
  // configure I2C0 for slave mode
  i2c_slave_init(i2c0, I2C_SLAVE_ADDRESS, &i2c_slave_handler);
}

// class that sets up and reads the 4x4 button matrix
class button_matrix {
public:
  // constructor
  // base_input is the starting gpio for the 4 input pins
  // base_output is the starting gpio for the 4 output pins
  button_matrix(uint base_input, uint base_output) {
    // pio 0 is used
    pio = pio0;
    // state machine 0
    sm = 0;
    // configure the used pins
    for (int i = 0; i < 4; i++) {
      // output pins
      pio_gpio_init(pio, base_output + i);
    }
    for (int i = 0; i < 4; i++) {
      // input pins with pull down
      pio_gpio_init(pio, base_input + i);
      gpio_pull_down(base_input + i);
    }
    // load the pio program into the pio memory
    uint offset = pio_add_program(pio, &button_matrix_program);
    // make a sm config
    pio_sm_config c = button_matrix_program_get_default_config(offset);
    // set the 'in' pins
    sm_config_set_in_pins(&c, base_input);
    // set the 4 output pins to output
    pio_sm_set_consecutive_pindirs(pio, sm, base_output, 4, true);
    // set the 'set' pins
    sm_config_set_set_pins(&c, base_output, 4);
    // set shift such that bits shifted by 'in' end up in the lower 16 bits
    sm_config_set_in_shift(&c, 0, 0, 0);
    // init the pio sm with the config
    pio_sm_init(pio, sm, offset, &c);
    // enable the sm
    pio_sm_set_enabled(pio, sm, true);
  }

  // read the 4x4 matrix
  int read(void) {
    // value is used to read from the fifo
    uint32_t value = 0;
    // clear the FIFO, we only want a currently pressed key
    pio_sm_clear_fifos(pio, sm);
    // give the sm some time to fill the FIFO if a key is being pressed
    sleep_ms(1);
    // check that the FIFO isn't empty
    if (pio_sm_is_rx_fifo_empty(pio, sm)) {
      return -1;
    }
    // read one data item from the FIFO
    value = pio_sm_get(pio, sm);
    return value;
  }

private:
  // the pio instance
  PIO pio;
  // the state machine
  uint sm;
};
button_matrix *my_matrix;

uint16_t matrix_task() {
  // read the matrix of buttons
  // int key = my_matrix->read();
  uint16_t key = 0;
  for (int i = 0; i < 4; i++) {
    gpio_put(base_output + i, 1);
    sleep_us(10);
    uint8_t rawIn = (gpio_get_all() >> base_input) & 0b1111;
    key |= rawIn << (i * 4);
    gpio_put(base_output + i, 0);
  }
  /*if (key != 0) { // a key was pressed: print its number
    for (int i = 15; i >= 0; i--) {
      printf("%d", (key >> i) & 1);
      /*if ((key >> i) & 1) {
        printf("%d", i);
        }
}
printf("\n");
}*/
  return key;
}

uint32_t freqToColor(uint64_t freq) {
  // while (freq < 400000000000000) { // 400 tHz
  //   freq *= freq;
  // }
  // Get the place value of the most significant bit in input:
  int input_msb_position = 63 ^ __builtin_clzll(freq);
  // We want the output to be >= 2^47,
  // so we need to shift input to the right until the MSB position is 47:
  float wavelength = 299792458.0 / (freq << (47 - input_msb_position));

  // https://gist.github.com/friendly/67a7df339aa999e2bcfcfec88311abfc
  float R, G, B;
#define gamma 0.8
  if (wavelength >= 380 & wavelength <= 440) {
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
  R = R * 255;
  G = G * 255;
  B = B * 255;
  return (((uint8_t)R) << 16) | (((uint8_t)G) << 8) | ((uint8_t)B);
}

void led_task() {
  union {
    float f;
    unsigned char bytes[4];
  } ratio;
  if (ledUpdated && !context.mem_address_written) {
    ledUpdated = false;
    uint16_t baseFreq = (context.mem[5] << 8) | context.mem[6];
    uint8_t numKeys = context.mem[7];
    for (int i = 0; i < 4; i++)
      ratio.bytes[i] = context.mem[8 + i];
    uint16_t mask = (context.mem[12] << 8) | context.mem[13];
    for (int i = 0; i < numKeys; i++) {
      if (((1 << i) & mask) != 0) {
        strip.setPixelColor(ledTrans[i], freqToColor(baseFreq + (ratio.f * i)));
      }
    }
    strip.show();
  }
}

uint16_t movingAvg(uint16_t *ptrArrNumbers, long *ptrSum, int pos, int len,
                   int nextNum) {
  // Subtract the oldest number from the prev sum, add the new number
  *ptrSum = *ptrSum - ptrArrNumbers[pos] + nextNum;
  // Assign the nextNum to the position in the array
  ptrArrNumbers[pos] = nextNum;
  // return the average
  return *ptrSum / len;
}

void analog_task() {
  adc_select_input(0);
  context.mem[2] = 127 - (movingAvg(dial1History, &history1Sum, historyIndex,
                                    historySize, adc_read()) >>
                          5);
  adc_select_input(1);
  context.mem[3] = 127 - (movingAvg(dial2History, &history2Sum, historyIndex,
                                    historySize, adc_read()) >>
                          5);
  adc_select_input(2);

  context.mem[4] = 127 - ((movingAvg(dial3History, &history3Sum, historyIndex,
                                     historySize, adc_read()) /
                           2800.0) *
                          127);
  if (context.mem[4] < 5)
    context.mem[4] = 0;
  printf("dial1: %d \n", context.mem[2]);
  printf("dial2: %d \n", context.mem[3]);
  printf("dial3: %d \n", context.mem[4]);
  historyIndex++;
  if (historyIndex >= historySize) {
    historyIndex = 0;
  }
}

int main() {
  // needed for printf
  stdio_init_all();
  setup_slave();
  strip.begin();
  strip.show();

  adc_init();
  adc_gpio_init(26);
  adc_gpio_init(27);
  adc_gpio_init(28);

  for (int i = 0; i < 4; i++) {
    // output pins
    gpio_init(base_output + i);
    gpio_set_dir(base_output + i, GPIO_OUT);

    gpio_init(base_input + i);
    gpio_set_dir(base_input + i, GPIO_IN);
    gpio_pull_down(base_input + i);
  }

  // my_matrix = new button_matrix((uint)9, (uint)13);
  while (true) {
    uint16_t key = buttonLookup.values[matrix_task()];
    /*if (key != 0) {
      for (int i = 0; i < 16; i++) {
        if ((key >> i) & 1) {
          printf("%d\n", i);
        }
      }
      }*/

    context.mem[1] = key & 0xFF; // I guess we're little endian
    context.mem[0] = (key & 0xFF00) >> 8;
    analog_task();
    led_task();
  }
}
