#include "Bluetooth.h"
#include <string.h>
#include <ctype.h>
#include <stdlib.h>
#include <math.h>

#define BT_SERIAL             CONFIG_BT_SERIAL
#define DEBUG_SERIAL          CONFIG_DEBUG_SERIAL
#define BT_USE_TRANSPARENT    CONFIG_BT_USE_TRANSPARENT

TinyBTPlus::TinyBTPlus()
  : Serial_RxFlag(0)
	,RxState(0)
	,pRxPacket(0)
	,encodedCharCount(0)
{
  Serial_RxPacket[0] = '\0';;
}

bool TinyBTPlus::encode(char c)
{
  ++encodedCharCount;
	
	if (RxState == 0)
	{
		if (c == '+' && Serial_RxFlag == 0)		//如果数据确实是包头，并且上一个数据包已处理完毕
		{
			RxState = 1;			//置下一个状态
			pRxPacket = 0;			//数据包的位置归零
		}
	}
	/*当前状态为1，接收数据包数据，同时判断是否接收到了第一个包尾*/
	else if (RxState == 1)
	{
		if (c == '\r')			//如果收到第一个包尾
		{
			RxState = 2;			//置下一个状态
		}
		else						//接收到了正常的数据
		{
			Serial_RxPacket[pRxPacket] = c;		//将数据存入数据包数组的指定位置
			pRxPacket ++;			//数据包的位置自增
		}
	}
	/*当前状态为2，接收数据包第二个包尾*/
	else if (RxState == 2)
	{
		if (c == '\n')			//如果收到第二个包尾
		{
			RxState = 0;			//状态归0
			Serial_RxPacket[pRxPacket] = '\0';			//将收到的字符数据包添加一个字符串结束标志
			Serial_RxFlag = 1;		//接收数据包标志位置1，成功接收一个数据包
			OTA();
			BT_SERIAL.printf("%s\r\n",Serial_RxPacket);
		}
	}
	return true;
}

bool TinyBTPlus::OTA()
{
	if(Serial_RxFlag == 1)
  {
		CONFIG_DEBUG_SERIAL.print(Serial_RxPacket);
		Serial_RxFlag = 0;			//处理完成后，需要将接收数据包标志位清零，否则将无法接收后续数据包
	}
	return true;
}
