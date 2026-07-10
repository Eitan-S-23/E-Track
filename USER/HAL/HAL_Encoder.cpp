#include "HAL.h"
#include "ButtonEvent/ButtonEvent.h"

static ButtonEvent EncoderPush(CONFIG_POWER_SHUTDOWM_DELAY);
static ButtonEvent EncoderA(CONFIG_KEY_LONG_PRESS);
static ButtonEvent EncoderB(CONFIG_KEY_LONG_PRESS);

static bool EncoderEnable = true;
static volatile int32_t EncoderDiff = 0;
static bool EncoderDiffDisable = false;

static void Buzz_Handler(int dir)
{
    static const uint16_t freqStart = 2000;
    static uint16_t freq = freqStart;
    static uint32_t lastRotateTime;

    if(millis() - lastRotateTime > 1000)
    {
        freq = freqStart;
    }
    else
    {
        if(dir > 0)
        {
            freq += 100;
        }

        if(dir < 0)
        {
            freq -= 100;
        }

        freq = constrain(freq, 100, 20 * 1000);
    }

    lastRotateTime = millis();
    HAL::Buzz_Tone(freq, 5);
}

static void Encoder_AHandler(ButtonEvent* btn, int event)
{
    if(!EncoderEnable || EncoderDiffDisable)
    {
        return;
    }
		
		if(event == ButtonEvent::EVENT_PRESSED)
    {
        EncoderDiff += 1;
				Buzz_Handler(1);
    }
		else if(event == ButtonEvent::EVENT_LONG_PRESSED_REPEAT)
    {
        EncoderDiff += 1;
				Buzz_Handler(1);
    }
}

static void Encoder_BHandler(ButtonEvent* btn, int event)
{
    if(!EncoderEnable || EncoderDiffDisable)
    {
        return;
    }

    if(event == ButtonEvent::EVENT_PRESSED)
    {
        EncoderDiff += -1;
				Buzz_Handler(-1);
    }
		else if(event == ButtonEvent::EVENT_LONG_PRESSED_REPEAT)
    {
        EncoderDiff += -1;
				Buzz_Handler(-1);
    }
}

static void Encoder_PushHandler(ButtonEvent* btn, int event)
{
    if(event == ButtonEvent::EVENT_PRESSED)
    {
        EncoderDiffDisable = true;
    }
    else if(event == ButtonEvent::EVENT_RELEASED)
    {
        EncoderDiffDisable = false;
    }
    else if(event == ButtonEvent::EVENT_LONG_PRESSED)
    {
        HAL::Power_Shutdown();
        HAL::Audio_PlayMusic("Shutdown");
    }
}

void HAL::Encoder_Init()
{
    pinMode(CONFIG_ENCODER_A_PIN, INPUT_PULLUP);
    pinMode(CONFIG_ENCODER_B_PIN, INPUT_PULLUP);
    pinMode(CONFIG_ENCODER_PUSH_PIN, INPUT_PULLUP);

    EncoderA.EventAttach(Encoder_AHandler);
		EncoderB.EventAttach(Encoder_BHandler);

    EncoderPush.EventAttach(Encoder_PushHandler);
}

void HAL::Encoder_Update()
{
    EncoderPush.EventMonitor(Encoder_GetIsPush());
		EncoderA.EventMonitor(Encoder_GetIsA());
		EncoderB.EventMonitor(Encoder_GetIsB());
}

int32_t HAL::Encoder_GetDiff()
{
    int32_t diff = EncoderDiff;
    EncoderDiff = 0;
    return diff;
}

bool HAL::Encoder_GetIsA()
{
    if(!EncoderEnable)
    {
        return false;
    }
    
    return (digitalRead(CONFIG_ENCODER_A_PIN) == LOW);
}

bool HAL::Encoder_GetIsB()
{
    if(!EncoderEnable)
    {
        return false;
    }
    
    return (digitalRead(CONFIG_ENCODER_B_PIN) == LOW);
}

bool HAL::Encoder_GetIsPush()
{
    if(!EncoderEnable)
    {
        return false;
    }
    
    return (digitalRead(CONFIG_ENCODER_PUSH_PIN) == LOW);
}

void HAL::Encoder_SetEnable(bool en)
{
    EncoderEnable = en;
}
