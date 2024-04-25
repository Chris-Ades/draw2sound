// Referenced
// https://github.com/GitJer/Some_RPI-Pico_stuff/tree/main/button_matrix_4x4
// Referenced
// https://github.com/vmilea/pico_i2c_slave/tree/master?tab=readme-ov-file

#include <array>
#include <cstdint>
#include <cstring>
#include <math.h>
#include <stdio.h>

#include "hardware/adc.h"
#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "pico/stdlib.h"
#include <PicoLed.hpp>

#include "hardware/uart.h"

// #include <Adafruit_NeoPixel.h>

#define UART_ID uart1
#define BAUD_RATE 38400
// We are using pins 0 and 1, but see the GPIO function select table in the
// datasheet for information on which other pins can be used.
#define UART_TX_PIN 4
#define UART_RX_PIN 5

static const uint base_output = 9;
static const uint base_input = 13;
int foobar = 0;

// Converts left to right LED index to logical address
static const uint8_t ledTrans[13] = {12, 5, 11, 4, 10, 3, 9, 2, 8, 1, 7, 0, 6};

static const uint historySize = 150;
uint16_t dial1History[historySize] = {0};
uint16_t dial2History[historySize] = {0};
uint16_t dial3History[historySize] = {0};
uint8_t historyIndex = 0;
long history1Sum = 0;
long history2Sum = 0;
long history3Sum = 0;

uint16_t key, oldKey;
uint8_t sendBuf[20];
char recvBuf[600];
uint16_t recvPtr = 0;

uint16_t baseFreq, mask;
uint8_t analog[3];
bool analog1, analog2, analog3, needLED;

float ratio = 1.05946309436;

bool ledUpdated = false;

#define LED_COUNT 13
#define LED_PIN 0

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

void uart_setup() {
  // Set up our UART with the required speed.
  uart_init(UART_ID, BAUD_RATE);

  // Set the TX and RX pins by using the function select on the GPIO
  // Set datasheet for more information on function select
  gpio_set_function(UART_TX_PIN, GPIO_FUNC_UART);
  gpio_set_function(UART_RX_PIN, GPIO_FUNC_UART);
}
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
uint32_t hexto32(char *hex) {
  uint32_t val = 0;
  for (int i = 0; i < 8; i++) {
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
PicoLed::Color freqToColor(uint64_t freq) {
  // while (freq < 400000000000000) { // 400 tHz
  //   freq *= freq;
  // }
  // Get the place value of the most significant bit in input:
  int input_msb_position = 63 ^ __builtin_clzll(freq);
  // We want the output to be >= 2^47,
  // so we need to shift input to the right until the MSB position is 47:
  float wavelength = 1e9 * 299792458.0 / (freq << (47 - input_msb_position));
  while(wavelength > 750) wavelength /= 2;

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
    //printf("%.9g\n", wavelength);
  }
  R = R * 255;
  G = G * 255;
  B = B * 255;
  // return (((uint8_t)R) << 16) | (((uint8_t)G) << 8) | ((uint8_t)B);
  //printf("%lld %.9g %d %d %d\n", freq, wavelength, (uint8_t)R, (uint8_t)G,
  //       (uint8_t)B);
  return PicoLed::RGB((uint8_t)R, (uint8_t)G, (uint8_t)B);
}

void led_task(auto strip) {
  if(needLED){
    needLED = false;
    strip.clear();
    for (int i = 0; i < 13; i++) {
      if (((1 << i) & mask) != 0) {
        float noteFreq = baseFreq * pow(ratio, i);
        strip.setPixelColor(ledTrans[i], freqToColor((uint64_t)noteFreq));
      }
    }
    /*strip.setPixelColor(ledTrans[foobar], PicoLed::RGB(255,0,0));
    foobar++;
    if(foobar == 13) foobar = 0;*/
    strip.show();
  }}

void uart_receive() {
  while (uart_is_readable(UART_ID)) {
    recvBuf[recvPtr] = uart_getc(UART_ID);
    printf("%c", recvBuf[recvPtr]);
    if (recvBuf[recvPtr] == '@') {
      if (recvPtr >= 5 && recvBuf[recvPtr - 5] == '!') {
        // Valid transaction
        baseFreq = hexto16(&recvBuf[recvPtr - 4]);
        printf("%d\n", baseFreq);
        needLED = true;
      }
      memset(recvBuf, 0, sizeof(recvBuf));
      recvPtr = 0;
    } else if (recvBuf[recvPtr] == '$') {
      if (recvPtr >= 3 && recvBuf[recvPtr - 3] == '#') {
        // Valid transaction
        uint8_t numKeys = hexto8(&recvBuf[recvPtr - 2]);
        mask = 0x1FFF >> (13 - numKeys);
        ratio = pow(2, 1.0 / (numKeys - 1));
        needLED = true;
      }
      memset(recvBuf, 0, sizeof(recvBuf));
      recvPtr = 0;
    } else {
      recvPtr++;
      if(recvPtr >= 600) recvPtr = 0;
    }
  }
}

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
  if (key != 0) { // a key was pressed: print its number
    for (int i = 15; i >= 0; i--) {
      printf("%d", (key >> i) & 1);
      // if ((key >> i) & 1) {
      // printf("%d", i);
      //}
    }
    printf("\n");
  }
  return key;
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
  uint8_t tmp;
  adc_select_input(0);
  tmp = 127 - (movingAvg(dial1History, &history1Sum, historyIndex, historySize,
                         adc_read()) >>
               5);
  analog1 = (tmp != analog[0]);
  analog[0] = tmp;

  adc_select_input(1);
  tmp = 127 - (movingAvg(dial2History, &history2Sum, historyIndex, historySize,
                         adc_read()) >>
               5);
  analog2 = (tmp != analog[1]);
  analog[1] = tmp;

  adc_select_input(2);
  tmp = 127 - ((movingAvg(dial3History, &history3Sum, historyIndex, historySize,
                          adc_read()) /
                2800.0) *
               127);

  if (tmp < 5)
    tmp = 0;

  analog3 = (tmp != analog[2]);
  analog[2] = tmp;

  // printf("dial1: %d \n", context.mem[2]);
  // printf("dial2: %d \n", context.mem[3]);
  // printf("dial3: %d \n", context.mem[4]);
  historyIndex++;
  if (historyIndex >= historySize) {
    historyIndex = 0;
  }
}

int main() {
  // needed for printf
  stdio_init_all();
  uart_setup();
  auto strip = PicoLed::addLeds<PicoLed::WS2812B>(
      pio1_hw, 3, LED_PIN, LED_COUNT, PicoLed::FORMAT_GRB);
  strip.setBrightness(255);
  strip.fill(PicoLed::RGB(255, 0, 0));
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
    oldKey = key;
    key = buttonLookup.values[matrix_task()];
    if (oldKey != key) {
      sprintf((char *)sendBuf, "!%04X@", key);
      uart_write_blocking(UART_ID, sendBuf, 6);
    }
    if (analog1) {
      sprintf((char *)sendBuf, "#%02X$", analog[0]);
      uart_write_blocking(UART_ID, sendBuf, 4);
      analog1 = false;
    }
    if (analog2) {
      sprintf((char *)sendBuf, "&%02X*", analog[1]);
      uart_write_blocking(UART_ID, sendBuf, 4);
      analog2 = false;
    }
    if (analog3) {
      sprintf((char *)sendBuf, "(%02X)", analog[2]);
      uart_write_blocking(UART_ID, sendBuf, 4);
      analog3 = false;
    }

    uart_receive();
    led_task(strip);
    /*if (key != 0) {
      for (int i = 0; i < 16; i++) {
        if ((key >> i) & 1) {
          printf("%d\n", i);
        }
      }
      }*/

    analog_task();
  }
}
