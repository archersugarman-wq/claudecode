#pragma once
#include <Arduino.h>
#include <Wire.h>

#define AS5600_ADDR     0x36
#define TCA9548A_ADDR   0x70  // A0=A1=A2=GND
#define REG_ANGLE_H     0x0E  // Raw angle high byte
#define REG_STATUS      0x0B
#define AS5600_MAX      4096  // 12-bit resolution

// Selects a channel on the TCA9548A I2C mux (channel 0-7, or 255 to disable all)
static void muxSelect(uint8_t channel) {
    Wire.beginTransmission(TCA9548A_ADDR);
    Wire.write(channel < 8 ? (1 << channel) : 0);
    Wire.endTransmission();
}

class AS5600 {
public:
    // mux_channel: TCA9548A channel this sensor is on (0-7)
    AS5600(uint8_t mux_channel) : _ch(mux_channel), _offset(0), _last(0), _turns(0) {}

    bool begin() {
        muxSelect(_ch);
        Wire.beginTransmission(AS5600_ADDR);
        bool ok = Wire.endTransmission() == 0;
        if (ok) zero();
        return ok;
    }

    // Set current position as zero reference
    void zero() {
        muxSelect(_ch);
        _offset = _readRaw();
        _last = 0;
        _turns = 0;
    }

    // Returns angle in degrees, continuous (unwrapped across multiple rotations)
    float getAngleDeg() {
        return getAngleRaw() * (360.0f / AS5600_MAX);
    }

    // Returns raw 12-bit count, continuous (unwrapped)
    int32_t getAngleRaw() {
        muxSelect(_ch);
        int32_t raw = ((int32_t)_readRaw() - _offset + AS5600_MAX) % AS5600_MAX;

        // Detect wrap-around for continuous tracking
        int32_t delta = raw - _last;
        if (delta > AS5600_MAX / 2)  _turns--;
        if (delta < -AS5600_MAX / 2) _turns++;
        _last = raw;

        return raw + _turns * AS5600_MAX;
    }

    // Returns true if magnet is detected and field strength is good
    bool magnetOk() {
        muxSelect(_ch);
        Wire.beginTransmission(AS5600_ADDR);
        Wire.write(REG_STATUS);
        Wire.endTransmission(false);
        Wire.requestFrom(AS5600_ADDR, (uint8_t)1);
        if (!Wire.available()) return false;
        uint8_t status = Wire.read();
        return (status & 0x20) != 0;  // MD bit: magnet detected
    }

private:
    uint8_t  _ch;
    int32_t  _offset;
    int32_t  _last;
    int32_t  _turns;

    uint16_t _readRaw() {
        Wire.beginTransmission(AS5600_ADDR);
        Wire.write(REG_ANGLE_H);
        Wire.endTransmission(false);
        Wire.requestFrom(AS5600_ADDR, (uint8_t)2);
        if (Wire.available() < 2) return 0;
        uint16_t hi = Wire.read();
        uint16_t lo = Wire.read();
        return ((hi << 8) | lo) & 0x0FFF;
    }
};
