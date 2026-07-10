#ifndef __TinyBTPlus_h
#define __TinyBTPlus_h

#include "Arduino.h"
#include "HAL\HAL.h"

#define _BT_VERSION "1.0.0" // software version of this library

class TinyBTPlus
{
public:
  TinyBTPlus();
  bool encode(char c); // process one character received from BT
	bool OTA(); // OTA升级写flash
  static const char *libraryVersion() { return _BT_VERSION; }
	uint32_t charsProcessed()   const { return encodedCharCount; }
	
private:
	char Serial_RxPacket[256];				//定义接收数据包数组，数据包格式"+MSG\r\n"
	uint8_t Serial_RxFlag;					//定义接收数据包标志位
	uint8_t RxState;		//定义表示当前状态机状态的静态变量
	uint8_t pRxPacket;	//定义表示当前接收数据位置的静态变量
	// statistics
  uint32_t encodedCharCount;
};

#endif // def(__TinyBTPlus_h)
