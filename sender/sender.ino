// SENDER
// Sits idle (sending nothing) until the computer sends the letter 'g'.
// Then it broadcasts a small packet 100 times per second for SEND_SECONDS,
// and goes back to idle. It answers '?' with its role so the computer can
// tell which board is which.

#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

#define CHANNEL 6
#define SEND_SECONDS 35   // a bit longer than the receiver's 30 seconds

uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

int counter = 0;
bool running = false;
unsigned long startTime = 0;

void setup() {
  Serial.begin(921600);

  // slower CPU = less heat (Wi-Fi still works fine at 160 MHz)
  setCpuFrequencyMhz(160);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  // lower the transmit power (units are 0.25 dBm, so 40 = 10 dBm)
  esp_wifi_set_max_tx_power(40);

  // put the radio on our channel (20 MHz wide)
  esp_wifi_set_channel(CHANNEL, WIFI_SECOND_CHAN_NONE);

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW failed to start");
    return;
  }

  // add the broadcast address as a "peer" so we can send to everyone
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, broadcastAddress, 6);
  peer.channel = CHANNEL;
  peer.ifidx = WIFI_IF_STA;
  peer.encrypt = false;
  esp_now_add_peer(&peer);

  // use an 802.11n rate (the default slow rate gives no CSI)
  esp_now_rate_config_t rate = {};
  rate.phymode = WIFI_PHY_MODE_HT20;
  rate.rate = WIFI_PHY_RATE_MCS0_LGI;
  esp_now_set_peer_rate_config(broadcastAddress, &rate);

  Serial.print("Sender ready. My MAC: ");
  Serial.println(WiFi.macAddress());
}

void loop() {
  // idle: wait for a command from the computer
  if (!running) {
    if (Serial.available()) {
      char c = Serial.read();
      if (c == '?') {
        Serial.println("ROLE:SENDER");
      }
      if (c == 'g') {
        counter = 0;
        startTime = millis();
        running = true;
        Serial.println("Sender started");
      }
    }
    delay(20);
    return;
  }

  // running: send one packet (the packet is just a counter)
  counter++;
  esp_now_send(broadcastAddress, (uint8_t *)&counter, sizeof(counter));

  // stop after SEND_SECONDS
  if (millis() - startTime >= SEND_SECONDS * 1000UL) {
    running = false;
    Serial.print("Sender done. Packets sent: ");
    Serial.println(counter);
    return;
  }

  delay(10);  // 10 ms = about 100 packets per second
}
