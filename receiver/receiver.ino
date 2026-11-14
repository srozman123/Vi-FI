// RECEIVER
// Sits idle until the computer sends the letter 'g'. Then for RUN_SECONDS it
// measures CSI on every packet from the sender and prints one CSV line per packet:
//   D,<time in microseconds>,<rssi>,<amp0>,<amp1>,...
// Then it prints END and goes back to idle. It answers '?' with its role so
// the computer can tell which board is which.
// Serial speed is 921600 because there is a lot of data.

#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <math.h>

#define CHANNEL 6
#define RUN_SECONDS 30
#define BUF_SIZE 64     // how many packets we can hold before printing
#define MAX_CSI 384     // max CSI bytes per packet

// MAC address of the SENDER board
uint8_t senderMac[] = {0x58, 0x2a, 0xbd, 0x77, 0x73, 0x20};

// one saved packet
struct Row {
  uint32_t time;
  int rssi;
  int len;
  int8_t data[MAX_CSI];
};

Row rows[BUF_SIZE];
volatile int head = 0;      // where the callback writes next
volatile int tail = 0;      // where loop() prints next
volatile int dropped = 0;   // packets we had no room for
volatile bool running = false;
unsigned long startTime = 0;
int totalPackets = 0;

// ESP-NOW needs a receive function, but we only care about CSI
void onReceive(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
}

// This runs every time CSI is measured on a packet.
// It only saves the numbers. loop() does the printing.
void csiCallback(void *ctx, wifi_csi_info_t *info) {
  if (!running) {
    return;
  }

  // ignore packets that are not from our sender
  if (memcmp(info->mac, senderMac, 6) != 0) {
    return;
  }

  int next = (head + 1) % BUF_SIZE;
  if (next == tail) {
    dropped++;      // buffer is full
    return;
  }

  int len = info->len;
  if (len > MAX_CSI) {
    len = MAX_CSI;
  }

  rows[head].time = info->rx_ctrl.timestamp;
  rows[head].rssi = info->rx_ctrl.rssi;
  rows[head].len = len;
  memcpy(rows[head].data, info->buf, len);
  head = next;
}

void printRow(Row &r) {
  Serial.print("D,");
  Serial.print(r.time);
  Serial.print(",");
  Serial.print(r.rssi);

  // data is pairs of numbers: imaginary, real, imaginary, real, ...
  // amplitude = square root of (real^2 + imag^2)
  int pairs = r.len / 2;
  for (int i = 0; i < pairs; i++) {
    float imag = r.data[2 * i];
    float real = r.data[2 * i + 1];
    int amp = (int)(sqrt(real * real + imag * imag) + 0.5);
    Serial.print(",");
    Serial.print(amp);
  }
  Serial.println();
}

void setup() {
  Serial.begin(921600);

  // slower CPU = less heat (Wi-Fi still works fine at 160 MHz)
  setCpuFrequencyMhz(160);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  esp_wifi_set_channel(CHANNEL, WIFI_SECOND_CHAN_NONE);

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW failed to start");
    return;
  }
  esp_now_register_recv_cb(onReceive);

  // CSI settings (CSI is turned on when 'g' arrives)
  wifi_csi_config_t csiConfig = {};
  csiConfig.lltf_en = true;            // legacy long training field
  csiConfig.htltf_en = true;           // 802.11n training field
  csiConfig.stbc_htltf2_en = true;
  csiConfig.ltf_merge_en = true;
  csiConfig.channel_filter_en = false;
  csiConfig.manu_scale = false;
  esp_wifi_set_csi_config(&csiConfig);
  esp_wifi_set_csi_rx_cb(csiCallback, NULL);

  Serial.print("Receiver ready. My MAC: ");
  Serial.println(WiFi.macAddress());
}

void loop() {
  // idle: wait for a command from the computer
  if (!running) {
    if (Serial.available()) {
      char c = Serial.read();
      if (c == '?') {
        Serial.println("ROLE:RECEIVER");
      }
      if (c == 'g') {
        head = 0;
        tail = 0;
        dropped = 0;
        totalPackets = 0;
        startTime = millis();
        running = true;
        esp_wifi_set_csi(true);
        Serial.println("START");
      }
    }
    delay(20);
    return;
  }

  // running: print every saved packet
  while (tail != head) {
    printRow(rows[tail]);
    tail = (tail + 1) % BUF_SIZE;
    totalPackets++;
  }

  // stop after RUN_SECONDS
  if (millis() - startTime >= RUN_SECONDS * 1000UL) {
    running = false;
    esp_wifi_set_csi(false);
    Serial.print("END,packets=");
    Serial.print(totalPackets);
    Serial.print(",dropped=");
    Serial.println(dropped);
  }
}
