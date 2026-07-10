#include "DialplateModel.h"
#include "Common/HAL/HAL.h"
#include <string.h>

using namespace Page;

DialplateModel::DialplateModel()
    : account(nullptr)
{
    memset(&sportStatusInfo, 0, sizeof(sportStatusInfo));
}

void DialplateModel::Init()
{
    memset(&sportStatusInfo, 0, sizeof(sportStatusInfo));
    if (account != nullptr)
    {
        delete account;
        account = nullptr;
    }

    account = new Account("DialplateModel", DataProc::Center(), 0, this);
    if (account == nullptr)
    {
        return;
    }

    account->Subscribe("SportStatus");
    account->Subscribe("Recorder");
    account->Subscribe("StatusBar");
    account->Subscribe("GPS");
    account->Subscribe("Navigation");
    account->Subscribe("Power");
    account->Subscribe("MusicPlayer");
    account->SetEventCallback(onEvent);
}

void DialplateModel::Deinit()
{
    if (account)
    {
        delete account;
        account = nullptr;
    }
}

bool DialplateModel::GetGPSReady()
{
    if(account == nullptr)
    {
        return false;
    }

    HAL::GPS_Info_t gps;
    if(account->Pull("GPS", &gps, sizeof(gps)) != Account::RES_OK)
    {
        return false;
    }
    return (gps.satellites > 0);
}

bool DialplateModel::GetGPSInfo(HAL::GPS_Info_t* info)
{
    if(account == nullptr || info == nullptr)
    {
        return false;
    }

    return account->Pull("GPS", info, sizeof(HAL::GPS_Info_t)) == Account::RES_OK;
}

bool DialplateModel::GetNavigationInfo(DataProc::Navigation_Info_t* info)
{
    if(account == nullptr || info == nullptr)
    {
        return false;
    }

    return account->Pull("Navigation", info, sizeof(DataProc::Navigation_Info_t)) == Account::RES_OK;
}

bool DialplateModel::GetBluetoothConnected()
{
    return HAL::BT_IsConnected();
}

bool DialplateModel::GetPowerInfo(HAL::Power_Info_t* info)
{
    if(account == nullptr || info == nullptr)
    {
        return false;
    }

    return account->Pull("Power", info, sizeof(HAL::Power_Info_t)) == Account::RES_OK;
}

int DialplateModel::onEvent(Account* account, Account::EventParam_t* param)
{
    if (param->event != Account::EVENT_PUB_PUBLISH)
    {
        return Account::RES_UNSUPPORTED_REQUEST;
    }

    if (strcmp(param->tran->ID, "SportStatus") != 0)
    {
        return Account::RES_OK;
    }

    if (param->size != sizeof(HAL::SportStatus_Info_t))
    {
        return Account::RES_PARAM_ERROR;
    }

    DialplateModel* instance = (DialplateModel*)account->UserData;
    memcpy(&(instance->sportStatusInfo), param->data_p, param->size);

    return Account::RES_OK;
}

void DialplateModel::RecorderCommand(RecCmd_t cmd)
{
    if(account == nullptr)
    {
        return;
    }

    if (cmd != REC_READY_STOP)
    {
        DataProc::Recorder_Info_t recInfo;
        DATA_PROC_INIT_STRUCT(recInfo);
        recInfo.cmd = (DataProc::Recorder_Cmd_t)cmd;
        recInfo.time = 1000;
        account->Notify("Recorder", &recInfo, sizeof(recInfo));
    }

    DataProc::StatusBar_Info_t statInfo;
    DATA_PROC_INIT_STRUCT(statInfo);
    statInfo.cmd = DataProc::STATUS_BAR_CMD_SET_LABEL_REC;

    switch (cmd)
    {
    case REC_START:
    case REC_CONTINUE:
        statInfo.param.labelRec.show = true;
        statInfo.param.labelRec.str = "REC";
        break;
    case REC_PAUSE:
        statInfo.param.labelRec.show = true;
        statInfo.param.labelRec.str = "PAUSE";
        break;  
    case REC_READY_STOP:
        statInfo.param.labelRec.show = true;
        statInfo.param.labelRec.str = "STOP";
        break;
    case REC_STOP:
        statInfo.param.labelRec.show = false;
        break;
    default:
        break;
    }

    account->Notify("StatusBar", &statInfo, sizeof(statInfo));
}

void DialplateModel::PlayMusic(const char* music)
{
    if(account == nullptr)
    {
        return;
    }

    DataProc::MusicPlayer_Info_t info;
    DATA_PROC_INIT_STRUCT(info);

    info.music = music;
    account->Notify("MusicPlayer", &info, sizeof(info));
}

void DialplateModel::SetStatusBarStyle(DataProc::StatusBar_Style_t style)
{
    if(account == nullptr)
    {
        return;
    }

    DataProc::StatusBar_Info_t info;
    DATA_PROC_INIT_STRUCT(info);

    info.cmd = DataProc::STATUS_BAR_CMD_SET_STYLE;
    info.param.style = style;

    account->Notify("StatusBar", &info, sizeof(info));
}

void DialplateModel::SetStatusBarAppear(bool en)
{
    if(account == nullptr)
    {
        return;
    }

    /* 隐藏/显示全局状态栏。Dialplate 皮肤自带状态行（GPS/心率/海拔/坡度），
       进入本页隐藏全局栏以避免顶部重叠，离开时恢复供其他页面使用。 */
    DataProc::StatusBar_Info_t info;
    DATA_PROC_INIT_STRUCT(info);

    info.cmd = DataProc::STATUS_BAR_CMD_APPEAR;
    info.param.appear = en;

    account->Notify("StatusBar", &info, sizeof(info));
}
