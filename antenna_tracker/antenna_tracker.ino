/*
 * Andres Vahter
 *
 * This program can be used for driving StepStick stepper controllers
 */

#include "hdlc.h"
#include <AccelStepper.h>

#define LED			13

#define ELEVATION_STEPPER_ENABLE	2
#define ELEVATION_STEPPER_RESET		4
#define ELEVATION_STEPPER_SLEEP		5
#define ELEVATION_STEPPER_STEP		6
#define ELEVATION_STEPPER_DIR		7

#define AZIMUTH_STEPPER_ENABLE		A5
#define AZIMUTH_STEPPER_RESET		A4
#define AZIMUTH_STEPPER_SLEEP		A3
#define AZIMUTH_STEPPER_STEP		A2
#define AZIMUTH_STEPPER_DIR			A1

#define ACCELSTEPPER_USE_DRIVER		1 // AccelStepper driver chip mode

#define ELEVATION_STEPPER 			0
#define AZIMUTH_STEPPER 			1

AccelStepper ElevationStepper(ACCELSTEPPER_USE_DRIVER, ELEVATION_STEPPER_STEP, ELEVATION_STEPPER_DIR);
AccelStepper AzimuthStepper(ACCELSTEPPER_USE_DRIVER, AZIMUTH_STEPPER_STEP, AZIMUTH_STEPPER_DIR);

uint8_t m_rx_buffer[20];
uint8_t m_rx_len = 0;
uint8_t m_tx_buffer[20];
uint8_t m_tx_len = 0;
HDLC hdlc(m_rx_buffer, 20);

// define packages
// TC means from tracker to controller
// CT means from controller [PC] to tracker
enum {
	TC_ACK = 0x00,

	CT_SET_CONFIG = 0x01,
	CT_SET_POSITION = 0x02,

	CT_GET_CONFIG = 0x03,
	TC_CONFIG = 0x30
};

enum {
	ACK_STATUS_SUCCESS = 0,
	ACK_STATUS_FAIL
};
typedef struct {
	uint8_t type; // TC_ACK
	uint8_t status;
	uint16_t line;
} ack_packet_t __attribute__((packed));

typedef struct {
	uint8_t type; // CT_SET_POSITION
	uint8_t motor; // 0 - elevation, 1 - azimuth
	int16_t degrees;
} set_position_packet_t __attribute__((packed));

typedef struct {
	uint8_t type; // CT_SET_CONFIG
	uint8_t motor; // 0 - elevation, 1 - azimuth
	bool	motor_state; // 0 off, 1 on
	uint16_t max_speed;
	uint16_t acceleration;
	int16_t current_steps;
} set_config_packet_t __attribute__((packed));

typedef struct {
	uint8_t type; // CT_GET_CONFIG
	uint8_t motor; // 0 - elevation, 1 - azimuth
} get_config_packet_t __attribute__((packed));

typedef struct {
	uint8_t type; // TC_CONFIG
	uint8_t motor; // 0 - elevation, 1 - azimuth
	uint16_t max_speed;
	uint16_t acceleration;
	int16_t current_steps;
	int16_t current_degrees;
} config_packet_t __attribute__((packed));

ack_packet_t ack_packet;

void send_ack(uint8_t status, uint16_t line_nr) {
	ack_packet.type = TC_ACK;
	ack_packet.status = status;
	ack_packet.line = line_nr;
	m_tx_len = hdlc.encode((uint8_t*)&ack_packet, sizeof(ack_packet_t), m_tx_buffer);
	Serial.write(m_tx_buffer, m_tx_len);
}

int16_t degrees_to_elevation_steps(int16_t degrees) {
	return ((int16_t)degrees * 10000L) / 938L; // 1.8/19.19 = 0.0938 degrees per step
}

int16_t degrees_to_azimuth_steps(int16_t degrees) {
	return ((int16_t)degrees * 10000L) / 3475L; // 1.8/5.18 = 0.3475 degrees per step
}

void toggle_led() {
	static bool led_on = false;
	if (led_on) {
		led_on = false;
		digitalWrite(LED, HIGH);
	}
	else {
		led_on = true;
		digitalWrite(LED, LOW);
	}
}

void setup() {
	// setup elevation stepper
	pinMode(ELEVATION_STEPPER_ENABLE, OUTPUT);
	pinMode(ELEVATION_STEPPER_RESET, OUTPUT);
	pinMode(ELEVATION_STEPPER_SLEEP, OUTPUT);
	pinMode(ELEVATION_STEPPER_STEP, OUTPUT);
	pinMode(ELEVATION_STEPPER_DIR, OUTPUT);

	digitalWrite(ELEVATION_STEPPER_ENABLE, LOW);
	digitalWrite(ELEVATION_STEPPER_SLEEP, HIGH);
	digitalWrite(ELEVATION_STEPPER_RESET, HIGH);

	ElevationStepper.setMaxSpeed(400.0);
	ElevationStepper.setAcceleration(2000.0);

	// setup azimuth stepper
	pinMode(AZIMUTH_STEPPER_ENABLE, OUTPUT);
	pinMode(AZIMUTH_STEPPER_RESET, OUTPUT);
	pinMode(AZIMUTH_STEPPER_SLEEP, OUTPUT);
	pinMode(AZIMUTH_STEPPER_STEP, OUTPUT);
	pinMode(AZIMUTH_STEPPER_DIR, OUTPUT);

	digitalWrite(AZIMUTH_STEPPER_ENABLE, LOW);
	digitalWrite(AZIMUTH_STEPPER_SLEEP, HIGH);
	digitalWrite(AZIMUTH_STEPPER_RESET, HIGH);

	AzimuthStepper.setMaxSpeed(8000.0);
	AzimuthStepper.setAcceleration(2000.0);

	Serial.begin(115200);
	Serial.println("reset");
}

void loop() {
	toggle_led();

	while (Serial.available() > 0) {
		m_rx_len = hdlc.decode(Serial.read());

		// check if HDLC packet is received
		if (m_rx_len > 0) {
			uint8_t type = ((uint8_t*)m_rx_buffer)[0];

			if (CT_SET_CONFIG == type) {

			}
			else if (CT_SET_POSITION == type) {
				set_position_packet_t* set_position_p = (set_position_packet_t*)m_rx_buffer;
				if (set_position_p->motor == ELEVATION_STEPPER) {
					ElevationStepper.moveTo(degrees_to_elevation_steps(set_position_p->degrees));
					send_ack(ACK_STATUS_SUCCESS, __LINE__);
				}
				else if (set_position_p->motor == AZIMUTH_STEPPER) {
					AzimuthStepper.moveTo(degrees_to_azimuth_steps(set_position_p->degrees));
					send_ack(ACK_STATUS_SUCCESS, __LINE__);
				}
				else {
					send_ack(ACK_STATUS_FAIL, __LINE__);
				}
			}
			else {
				send_ack(ACK_STATUS_FAIL, __LINE__);
			}
		}
	}

	//ElevationStepper.moveTo(degrees_to_steps(m_degrees));
	ElevationStepper.run(); // for accel/deccel
	//ElevationStepper.runSpeed(); // for const speed
	AzimuthStepper.run();
}
