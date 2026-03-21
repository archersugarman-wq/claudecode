#include <Wire.h>
#include <SimpleFOC.h>
#include "AS5600_mux.h"
#include "Joint.h"

#define SUPPLY_VOLTAGE  12.0f
#define I2C_SDA         21
#define I2C_SCL         22

// Joint(pin_a, pin_b, pin_c, pole_pairs, mux_channel, gear_ratio, min_deg, max_deg)
Joint joints[6] = {
    Joint(13, 12, 14,  7, 0, 4.0f, -180.0f, 180.0f),  // J1 Base
    Joint(26, 25, 33,  7, 1, 4.0f,  -90.0f,  90.0f),  // J2 Shoulder
    Joint(27, 32, 35,  7, 2, 3.0f,  -90.0f,  90.0f),  // J3 Elbow
    Joint(15,  2,  0,  7, 3, 2.0f,  -90.0f,  90.0f),  // J4 Forearm
    Joint( 4, 16, 17,  7, 4, 2.0f,  -90.0f,  90.0f),  // J5 Wrist pitch
    Joint(18, 19, 23,  7, 5, 1.0f,  -90.0f,  90.0f),  // J6 Wrist roll
};
const uint8_t NUM_JOINTS = 6;

void printStatus() {
    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        Serial.printf("J%d: %.2f deg  magnet=%s\n",
            i + 1, joints[i].getAngleDeg(),
            joints[i].magnetOk() ? "OK" : "FAIL");
    }
}

void parseCommand(char* cmd) {
    if (!cmd || cmd[0] == '\0') return;

    if (strcmp(cmd, "status") == 0) {
        printStatus();
    } else if (strcmp(cmd, "home") == 0) {
        for (auto& j : joints) j.setTargetDeg(0.0f);
        Serial.println("Homing");
    } else if (strcmp(cmd, "zero") == 0) {
        for (auto& j : joints) j.zero();
        Serial.println("Encoders zeroed");
    } else if (strcmp(cmd, "enable") == 0) {
        for (auto& j : joints) j.enable();
        Serial.println("Enabled");
    } else if (strcmp(cmd, "disable") == 0) {
        for (auto& j : joints) j.disable();
        Serial.println("Disabled");
    } else if (cmd[0] == 'j' && cmd[1] >= '1' && cmd[1] <= '6') {
        int idx = cmd[1] - '1';
        float angle = atof(cmd + 3);
        joints[idx].setTargetDeg(angle);
        Serial.printf("J%d -> %.2f deg\n", idx + 1, angle);
    } else if (strncmp(cmd, "pid", 3) == 0 && cmd[3] >= '1' && cmd[3] <= '6') {
        int idx = cmd[3] - '1';
        float kp, ki, kd;
        if (sscanf(cmd + 5, "%f %f %f", &kp, &ki, &kd) == 3) {
            joints[idx].setPID(kp, ki, kd);
            Serial.printf("J%d PID: %.3f %.3f %.3f\n", idx + 1, kp, ki, kd);
        } else {
            Serial.println("Usage: pid<n> <kp> <ki> <kd>");
        }
    } else {
        Serial.println("Commands: j<n> <deg>, status, home, zero, enable, disable, pid<n> <kp> <ki> <kd>");
    }
}

void setup() {
    Serial.begin(115200);
    delay(500);

    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(400000);

    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        Serial.printf("Init J%d... ", i + 1);
        if (joints[i].begin(SUPPLY_VOLTAGE)) {
            joints[i].enable();
            Serial.println("OK");
        } else {
            Serial.println("FAILED");
        }
    }
    Serial.println("Ready.");
}

static char buf[64];
static uint8_t pos = 0;

void loop() {
    for (auto& j : joints) j.update();

    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            buf[pos] = '\0';
            parseCommand(buf);
            pos = 0;
        } else if (pos < sizeof(buf) - 1) {
            buf[pos++] = c;
        }
    }
}
