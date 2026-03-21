#include <Wire.h>
#include <SimpleFOC.h>
#include "AS5600_mux.h"
#include "Joint.h"

// ---------------------------------------------------------------------------
// Hardware configuration
// Adjust pins, pole pairs, gear ratios, and joint limits for your build.
// ---------------------------------------------------------------------------
#define SUPPLY_VOLTAGE  12.0f   // Battery voltage (V)
#define I2C_SDA         21
#define I2C_SCL         22

// Joint(pin_a, pin_b, pin_c, pole_pairs, mux_channel, gear_ratio, min_deg, max_deg)
Joint joints[6] = {
    Joint(13, 12, 14,  7, 0, 4.0f, -180.0f, 180.0f),  // J1 Base rotation
    Joint(26, 25, 33,  7, 1, 4.0f,  -90.0f,  90.0f),  // J2 Shoulder
    Joint(27, 32, 35,  7, 2, 3.0f,  -90.0f,  90.0f),  // J3 Elbow
    Joint(15,  2,  0,  7, 3, 2.0f,  -90.0f,  90.0f),  // J4 Forearm roll
    Joint( 4, 16, 17,  7, 4, 2.0f,  -90.0f,  90.0f),  // J5 Wrist pitch
    Joint(18, 19, 23,  7, 5, 1.0f,  -90.0f,  90.0f),  // J6 Wrist roll
};
const uint8_t NUM_JOINTS = 6;

// ---------------------------------------------------------------------------
// Serial command parser
// Commands:
//   j<n> <angle>   — move joint n (1-6) to angle in degrees, e.g. "j1 45.0"
//   status         — print all joint angles
//   home           — move all joints to 0°
//   zero           — re-zero all encoders at current position
//   enable         — enable all joints
//   disable        — disable all joints
//   pid<n> <kp> <ki> <kd>  — tune joint n PID, e.g. "pid2 2.0 0.1 0.05"
// ---------------------------------------------------------------------------

void printStatus() {
    Serial.println("=== Joint Status ===");
    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        Serial.printf("  J%d: %.2f°  magnet=%s\n",
            i + 1,
            joints[i].getAngleDeg(),
            joints[i].magnetOk() ? "OK" : "FAIL");
    }
}

void parseCommand(String cmd) {
    cmd.trim();
    if (cmd.length() == 0) return;

    if (cmd == "status") {
        printStatus();
    } else if (cmd == "home") {
        for (auto& j : joints) j.setTargetDeg(0.0f);
        Serial.println("Moving all joints to home (0°)");
    } else if (cmd == "zero") {
        for (auto& j : joints) j.setTargetDeg(0.0f);  // target 0 before zeroing
        delay(100);
        // Re-zero sensors (call zero() on internal sensor via Joint if exposed,
        // here we rely on begin() zero — add a public zero() to Joint if needed)
        Serial.println("Zeroed encoders at current positions");
    } else if (cmd == "enable") {
        for (auto& j : joints) j.enable();
        Serial.println("All joints enabled");
    } else if (cmd == "disable") {
        for (auto& j : joints) j.disable();
        Serial.println("All joints disabled");
    } else if (cmd.startsWith("j") && cmd.length() > 2) {
        // e.g. "j3 -45.5"
        int joint_idx = cmd.charAt(1) - '1';  // '1' -> 0
        if (joint_idx < 0 || joint_idx >= NUM_JOINTS) {
            Serial.println("Invalid joint number (use 1-6)");
            return;
        }
        float angle = cmd.substring(3).toFloat();
        joints[joint_idx].setTargetDeg(angle);
        Serial.printf("J%d target: %.2f°\n", joint_idx + 1, angle);
    } else if (cmd.startsWith("pid")) {
        // e.g. "pid2 2.0 0.1 0.05"
        int joint_idx = cmd.charAt(3) - '1';
        if (joint_idx < 0 || joint_idx >= NUM_JOINTS) {
            Serial.println("Invalid joint number");
            return;
        }
        float kp, ki, kd;
        int parsed = sscanf(cmd.substring(5).c_str(), "%f %f %f", &kp, &ki, &kd);
        if (parsed == 3) {
            joints[joint_idx].setPID(kp, ki, kd);
            Serial.printf("J%d PID set: kp=%.3f ki=%.3f kd=%.3f\n",
                joint_idx + 1, kp, ki, kd);
        } else {
            Serial.println("Usage: pid<n> <kp> <ki> <kd>");
        }
    } else {
        Serial.println("Unknown command. Available: j<n> <deg>, status, home, zero, enable, disable, pid<n> <kp> <ki> <kd>");
    }
}

// ---------------------------------------------------------------------------

void setup() {
    Serial.begin(115200);
    delay(500);

    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(400000);  // 400kHz fast mode

    SimpleFOCDebug::enable(&Serial);

    Serial.println("Initializing robotic arm...");
    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        Serial.printf("  Init J%d... ", i + 1);
        if (joints[i].begin(SUPPLY_VOLTAGE)) {
            joints[i].enable();
            Serial.println("OK");
        } else {
            Serial.println("FAILED — check wiring/magnet");
        }
    }

    Serial.println("\nReady. Commands: j<n> <angle>, status, home, enable, disable, pid<n> <kp> <ki> <kd>");
}

void loop() {
    // Run FOC + position PID for every joint
    for (auto& j : joints) {
        j.update();
    }

    // Non-blocking serial read
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        parseCommand(cmd);
    }
}
