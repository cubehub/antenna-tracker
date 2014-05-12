
#include "Arduino.h"
#include "hdlc.h"

HDLC::HDLC(uint8_t* decoder_buf, uint8_t len){
	_dec_tail = NULL;

	_dec_checksum   = 0;
	_dec_prev_byte  = 0;

	_dec_buf = decoder_buf;
	_decoder_restart_receiving();
	_dec_end = decoder_buf + len + 1; // +1 is for checksum
}

uint8_t HDLC::decode(uint8_t data) {
	if (_dec_state.receiving) {
		// if packet end
		if (HDLC_DELIM == data) {
			_dec_state.receiving = 0;
			if (_dec_state.escaping) {
				// illegal byte sequence 7d 7e
				_decoder_reset();
			}
			// checksum ok?
			else if ((uint8_t)(_dec_checksum - *(_dec_tail-1)) == *(_dec_tail-1)) {
				uint8_t decoded_packet_len = _dec_tail - _dec_buf - 1;
				_decoder_reset();
				return decoded_packet_len;
			}
			else {
				// checksum error
				_decoder_reset();
			}
		}
		// if buffer full
		else if (_dec_tail == _dec_end) {
			_dec_state.receiving = 0;
			// buffer overflow
			_decoder_reset();
		}
		else if (_dec_state.escaping) {
			*_dec_tail++   = data ^ 0x20;
			_dec_checksum += data ^ 0x20;
			_dec_state.escaping = 0;
		}
		else {
			if (HDLC_ESC == data) {
				_dec_state.escaping = 1;
			}
			else {
				*_dec_tail++   = data;
				_dec_checksum += data;
			}
		}
	}
	else {
		// detect packet start. starts if prev byte was 7e and current byte not
		if (HDLC_DELIM == _dec_prev_byte && HDLC_DELIM != data) {
			_dec_state.receiving = 1;

			if (HDLC_ESC == data) {
				_dec_state.escaping = 1;
			}
			else{
				*_dec_tail++   = data;
				_dec_checksum += data;
			}
		}
	}

	_dec_prev_byte = data;

	return 0; // no packet yet received
}

void HDLC::_decoder_restart_receiving() {
	_dec_tail     = _dec_buf;
	_dec_checksum = 0;
	_dec_state.receiving = 0;
	_dec_state.escaping  = 0;
}

void HDLC::_decoder_reset() {
	_decoder_restart_receiving();
	_dec_prev_byte = 0;
}

bool HDLC::_needs_escaping(uint8_t byte) {
	return HDLC_ESC == byte || HDLC_DELIM == byte;
}

uint8_t HDLC::encode(uint8_t* source, uint8_t source_len, uint8_t* dest) {
	//
	// result in *dest:
	//  0x7e data checksum 0x7e
	//
	// return:
	//   dest_len. length of the resulting escaped/framed packet.
	//             guaranteed to be <= source_len * 2 + 4
	//

	uint8_t* sourcep  = source;
	uint8_t* destp    = dest;
	uint8_t* end      = sourcep + source_len;
	uint8_t  checksum = 0;

	*destp++ = HDLC_DELIM;

	while (sourcep != end)
	{
		checksum += *sourcep;
		if (_needs_escaping(*sourcep))
		{
			*destp++ = HDLC_ESC;
			*destp++ = *sourcep++ ^ 0x20;
		}
		else
			*destp++ = *sourcep++;
	}

	// append checksum to dest
	if (_needs_escaping(checksum))
	{
		*destp++ = HDLC_ESC;
		*destp++ = checksum ^ 0x20;
	}
	else
		*destp++ = checksum;

	*destp++ = HDLC_DELIM;

	return destp - dest; // how many bytes are in dest now
}