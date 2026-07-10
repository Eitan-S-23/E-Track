#include "StartUp.h"

using namespace Page;

Startup::Startup()
{
}

Startup::~Startup()
{

}

void Startup::onCustomAttrConfig()
{
    SetCustomCacheEnable(false);
    SetCustomLoadAnimType(PageManager::LOAD_ANIM_NONE);
}

void Startup::onViewLoad()
{
    Model.Init();
    Model.SetEncoderEnable(false);
    View.Create(_root);
    lv_timer_t* timer = lv_timer_create(onTimer, STARTUP_PLAY_MS, this);
    lv_timer_set_repeat_count(timer, 1);
}

void Startup::onViewDidLoad()
{
}

void Startup::onViewWillAppear()
{
#if !defined(_WIN32)
    Model.PlayMusic("Startup");
#endif
    if(View.ui.anim_timeline)
    {
        lv_anim_timeline_start(View.ui.anim_timeline);
    }
}

void Startup::onViewDidAppear()
{
#if !defined(_WIN32)
    lv_obj_fade_out(_root, STARTUP_FADE_MS, STARTUP_ANIM_TOTAL);
#endif
}

void Startup::onViewWillDisappear()
{

}

void Startup::onViewDidDisappear()
{
    /* 不再在此强制显示全局状态栏：状态栏可见性改由目的页面自行决定
       （Dialplate 皮肤自带状态行、需隐藏全局栏；离开 Dialplate 时再恢复）。
       原先在此 appear(true) 会与 Dialplate 进入时的 appear(false) 竞态，导致顶部重叠。 */
}

void Startup::onViewUnload()
{
    View.Delete();
    Model.SetEncoderEnable(true);
    Model.Deinit();
}

void Startup::onViewDidUnload()
{
}

void Startup::onTimer(lv_timer_t* timer)
{
    Startup* instance = (Startup*)timer->user_data;

    instance->View.Delete();
    if(instance->_root)
    {
        lv_anim_del(instance->_root, nullptr);
    }

    instance->_Manager->Replace("Pages/Dialplate");
}

void Startup::onEvent(lv_event_t* event)
{
    Startup* instance = (Startup*)lv_event_get_user_data(event);
    LV_ASSERT_NULL(instance);

    lv_obj_t* obj = lv_event_get_current_target(event);
    lv_event_code_t code = lv_event_get_code(event);

    if (obj == instance->_root)
    {
        if (code == LV_EVENT_LEAVE)
        {
            //instance->Manager->Pop();
        }
    }
}
