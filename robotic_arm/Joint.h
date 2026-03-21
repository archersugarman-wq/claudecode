#pragma once
#include <SimpleFOC.h>
#include "AS5600_mux.h"

// PID controller (simple, no library dependency)
struct PID {
    float kp, ki, kd;
    float _integral = 0;
    float _prevErr  = 0;
    float _outMin, _outMax;

    PID(float kp, float ki, float kd, float outMin, float outMax)
        : kp(kp), ki(ki), kd(kd), _outMin(outMin), _outMax(outMax) {}

    float compute(float setpoint, float measured, float dt) {
        float err = setpoint - measured;
        _integral += err * dt;
        _integral = constrain(_integral, _outMin / ki, _outMax / ki);
        float deriv = (err - _prevErr) / dt;
        _prevErr = err;
        return constrain(kp * err + ki * _integral + kd * deriv, _outMin, _outMax);
    }

    void reset() { _integral = 0; _prevErr = 0; }
};

class Joint {
public:
    // pin_a/b/c: motor phase pins, pole_pairs: motor pole pairs, mux_ch: TCA9548A channel
    Joint(uint8_t pin_a, uint8_t pin_b, uint8_t pin_c,
          uint8_t pole_pairs, uint8_t mux_ch,
          float gear_ratio = 1.0f,
          float angle_min  = -180.0f,
          float angle_max  =  180.0f)
        : _motor(pole_pairs),
          _driver(pin_a, pin_b, pin_c),
          _sensor(mux_ch),
          _pid(2.0f, 0.1f, 0.05f, -12.0f, 12.0f),
          _gearRatio(gear_ratio),
          _angleMin(angle_min),
          _angleMax(angle_max),
          _targetDeg(0.0f),
          _enabled(false)
    {}

    bool begin(float supply_voltage) {
        if (!_sensor.begin()) return false;

        _driver.voltage_power_supply = supply_voltage;
        _driver.init();

        _motor.linkDriver(&_driver);
        _motor.foc_modulation = FOCModulationType::SpaceVectorPWM;
        _motor.controller     = MotionControlType::torque;  // We handle position via our PID
        _motor.voltage_limit  = supply_voltage * 0.5f;
        _motor.init();
        _motor.initFOC();

        _lastUs = micros();
        return true;
    }

    // Call as fast as possible in loop()
    void update() {
        _motor.loopFOC();

        if (!_enabled) {
            _motor.move(0);
            return;
        }

        unsigned long now = micros();
        float dt = (now - _lastUs) * 1e-6f;
        _lastUs = now;
        if (dt <= 0 || dt > 0.1f) return;

        float currentDeg = getAngleDeg();
        float torque = _pid.compute(_targetDeg, currentDeg, dt);
        _motor.move(torque);
    }

    void enable()  { _enabled = true;  _pid.reset(); }
    void disable() { _enabled = false; _motor.move(0); }

    // Set target joint angle in degrees (clamped to joint limits)
    void setTargetDeg(float deg) {
        _targetDeg = constrain(deg, _angleMin, _angleMax);
    }

    // Current joint angle in degrees (accounting for gear ratio)
    float getAngleDeg() {
        return _sensor.getAngleDeg() / _gearRatio;
    }

    bool magnetOk() { return _sensor.magnetOk(); }

    // Tune PID at runtime
    void setPID(float kp, float ki, float kd) {
        _pid.kp = kp; _pid.ki = ki; _pid.kd = kd;
        _pid.reset();
    }

private:
    BLDCMotor  _motor;
    BLDCDriver3PWM _driver;
    AS5600     _sensor;
    PID        _pid;
    float      _gearRatio;
    float      _angleMin, _angleMax;
    float      _targetDeg;
    bool       _enabled;
    unsigned long _lastUs;
};
