#pragma once
#include <Arduino.h>

// ESC PWM parameters (standard 50Hz, 1000-2000µs pulse width)
#define ESC_FREQ_HZ     50
#define ESC_MIN_US      1000   // Minimum throttle (armed, no spin)
#define ESC_MAX_US      2000   // Maximum throttle (full speed)
#define ESC_ARM_US      1000   // Arming pulse width

class ESCMotor {
public:
    ESCMotor(uint8_t pin, uint8_t ledc_channel)
        : _pin(pin), _channel(ledc_channel) {}

    void begin() {
        // ESP32 LEDC: 50Hz, 16-bit resolution
        ledcSetup(_channel, ESC_FREQ_HZ, 16);
        ledcAttachPin(_pin, _channel);
        writeMicroseconds(ESC_MIN_US);
    }

    // Arm the ESC (send min throttle for 2 seconds)
    void arm() {
        writeMicroseconds(ESC_ARM_US);
        delay(2000);
    }

    // Set throttle: 0.0 (off) to 1.0 (full)
    void setThrottle(float throttle) {
        throttle = constrain(throttle, 0.0f, 1.0f);
        int us = ESC_MIN_US + (int)(throttle * (ESC_MAX_US - ESC_MIN_US));
        writeMicroseconds(us);
    }

    // Direct microsecond control (1000–2000µs)
    void writeMicroseconds(int us) {
        us = constrain(us, ESC_MIN_US, ESC_MAX_US);
        // Convert µs to 16-bit duty cycle for 50Hz (period = 20000µs)
        uint32_t duty = (uint32_t)us * 65535 / 20000;
        ledcWrite(_channel, duty);
    }

private:
    uint8_t _pin;
    uint8_t _channel;
};
