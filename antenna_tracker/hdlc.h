#ifndef HDLC_H
#define HDLC_H

#include "Arduino.h"

enum {
	HDLC_DELIM = 0x7e,
	HDLC_ESC   = 0x7d
};

enum {
	ST_IDLE = 1,
	ST_START,
	ST_SENT_ESC,
	ST_SENT_DATA,
	ST_SENT_END,
	ST_SENT_CRC_ESC,
	ST_SENT_CRC_DATA
};

class HDLC {
	public:
		HDLC(uint8_t* decoder_buf, uint8_t len);
		uint8_t decode(uint8_t byte);
		uint8_t encode(uint8_t* source, uint8_t source_len, uint8_t* dest);
	private:
		void _init_hdlc();
		void _decoder_reset();
		void _decoder_restart_receiving();
		bool _needs_escaping(uint8_t byte);

		uint8_t* _dec_buf;
		uint8_t* _dec_tail;
		uint8_t* _dec_end;

		uint8_t _dec_checksum;
		uint8_t _dec_prev_byte;

		struct {
			unsigned receiving:1;
			unsigned escaping:1;
		} _dec_state;
};

#endif