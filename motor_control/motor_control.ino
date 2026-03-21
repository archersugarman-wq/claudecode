#include "motor_esc.h"

// --- Pin & channel config ---
// Change these to match your wiring.
// ESP32 has 16 LEDC channels (0–15).
#define MOTOR1_PIN      18
#define MOTOR2_PIN      19
#define MOTOR3_PIN      21
#define MOTOR4_PIN      22

ESCMotor motors[4] = {
    ESCMotor(MOTOR1_PIN, 0),
    ESCMotor(MOTOR2_PIN, 1),
    ESCMotor(MOTOR3_PIN, 2),
    ESCMotor(MOTOR4_PIN, 3),
};

void setup() {
    Serial.begin(115200);
    Serial.println("Initializing ESCs...");

    for (auto& m : motors) {
        m.begin();
    }

    Serial.println("Arming ESCs (keep throttle at 0 for 2s)...");
    for (auto& m : motors) {
        m.arm();
    }

    Serial.println("Armed. Send throttle via Serial (0–100).");
}

void loop() {
    // Simple serial control: type a number 0-100 and press Enter
    if (Serial.available()) {
        int val = Serial.parseInt();
        if (val >= 0 && val <= 100) {
            float throttle = val / 100.0f;
            Serial.printf("Setting throttle: %d%%\n", val);
            for (auto& m : motors) {
                m.setThrottle(throttle);
            }
        }
    }
}
