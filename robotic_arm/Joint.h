#pragma once
#include <SimpleFOC.h>
#include "AS5600_mux.h"

class Joint {
public:
    Joint(uint8_t pin_a, uint8_t pin_b, uint8_t pin_c,
          uint8_t pole_pairs, uint8_t mux_ch,
          float gear_ratio = 1.0f,
          float angle_min  = -180.0f,
          float angle_max  =  180.0f)
        : _motor(pole_pairs),
          _driver(pin_a, pin_b, pin_c),
          _sensor(mux_ch),
          _pid(2.0f, 0.1f, 0.05f, 1e6f, 12.0f),
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
        _motor.controller     = MotionControlType::torque;
        _motor.voltage_limit  = supply_voltage * 0.5f;
        _motor.init();
        _motor.initFOC();
        return true;
    }

    void update() {
        _motor.loopFOC();
        if (_enabled) {
            _motor.move(_pid(_targetDeg - getAngleDeg()));
        }
    }

    void enable()  { _motor.enable();  _enabled = true;  _pid.reset(); }
    void disable() { _motor.disable(); _enabled = false; }

    void zero() { _sensor.zero(); }

    void setTargetDeg(float deg) {
        _targetDeg = constrain(deg, _angleMin, _angleMax);
    }

    float getAngleDeg()  { return _sensor.getAngleDeg() / _gearRatio; }
    bool  magnetOk()     { return _sensor.magnetOk(); }

    void setPID(float kp, float ki, float kd) {
        _pid.P = kp; _pid.I = ki; _pid.D = kd;
        _pid.reset();
    }

private:
    BLDCMotor      _motor;
    BLDCDriver3PWM _driver;
    AS5600         _sensor;
    PIDController  _pid;
    float          _gearRatio;
    float          _angleMin, _angleMax;
    float          _targetDeg;
    bool           _enabled;
};
