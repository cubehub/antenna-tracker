/*
 * Andres Vahter
 *
 * This program can be used for driving StepStick stepper controllers
 */

#define LED			13

#define S1_ENABLE	0
#define S1_RESET	4
#define S1_SLEEP	5
#define S1_STEP		6
#define S1_DIR		7

#define STEP_COUNT	600


bool led_state = false;

bool cv = true;

void enable_outputs() {
	digitalWrite(S1_ENABLE, LOW);
}

void sleep(bool enable) {
	if (enable) {
		digitalWrite(S1_SLEEP, LOW);
	}
	else {
		digitalWrite(S1_SLEEP, HIGH);
	}
	delay(1);
}

void start() {
	digitalWrite(S1_STEP, LOW);
	digitalWrite(S1_RESET, HIGH);
}

void step(uint16_t steps) {
	for (int i = 0; i < steps; i++) {
        digitalWrite(S1_STEP, LOW);
		digitalWrite(S1_STEP, HIGH);
        delayMicroseconds(1200);
    }
}

void direction(bool cv) {
	if (cv) {
		digitalWrite(S1_DIR, LOW);
	}
	else {
		digitalWrite(S1_DIR, HIGH);
	}
	delay(1);
}

void setup() {
	//Serial.begin(9600); // conflicts with enable pin

	pinMode(LED, OUTPUT);

	pinMode(S1_ENABLE, OUTPUT);
	pinMode(S1_RESET, OUTPUT);
	pinMode(S1_SLEEP, OUTPUT);
	pinMode(S1_STEP, OUTPUT);
	pinMode(S1_DIR, OUTPUT);

	enable_outputs();
	sleep(false);
	direction(cv);
	start();
}

void loop() {
	if (led_state == false) {
		digitalWrite(LED, HIGH);
		led_state = true;
	}
	else {
		digitalWrite(LED, LOW);
		led_state = false;
	}

	step(STEP_COUNT);

	if (cv) {
		cv = false;
	}
	else {
		cv = true;
	}

	direction(cv);
	delay(2048);
}
