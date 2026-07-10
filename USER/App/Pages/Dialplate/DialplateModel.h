#ifndef __DIALPLATE_MODEL_H
#define __DIALPLATE_MODEL_H

#include "Common/DataProc/DataProc.h"

namespace Page
{

class DialplateModel
{
public:
    typedef enum
    {
        REC_START    = DataProc::RECORDER_CMD_START,
        REC_PAUSE    = DataProc::RECORDER_CMD_PAUSE,
        REC_CONTINUE = DataProc::RECORDER_CMD_CONTINUE,
        REC_STOP     = DataProc::RECORDER_CMD_STOP,
        REC_READY_STOP
    } RecCmd_t;

public:
    HAL::SportStatus_Info_t sportStatusInfo;

public:
    DialplateModel();

    void Init();
    void Deinit();

    bool GetGPSReady();

    float GetSpeed()
    {
        return sportStatusInfo.speedKph;
    }

    float GetAvgSpeed()
    {
        return sportStatusInfo.speedAvgKph;
    }

    float GetMaxSpeed()
    {
        return sportStatusInfo.speedMaxKph;
    }

    /* 拉取最新 GPS 信息（海拔/航向等）；成功返回 true */
    bool GetGPSInfo(HAL::GPS_Info_t* info);
    bool GetNavigationInfo(DataProc::Navigation_Info_t* info);
    bool GetBluetoothConnected();
    bool GetPowerInfo(HAL::Power_Info_t* info);

    void RecorderCommand(RecCmd_t cmd);
    void PlayMusic(const char* music);
    void SetStatusBarStyle(DataProc::StatusBar_Style_t style);
    void SetStatusBarAppear(bool en);

private:
    Account* account;

private:
    static int onEvent(Account* account, Account::EventParam_t* param);
};

}

#endif
