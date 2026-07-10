/*
 * MIT License
 * Copyright (c) 2021 _VIFEXTech
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
#include "PageManager.h"
#include "PM_Log.h"
#include "HAL/HAL.h"
#include <string.h>

static bool IsLiveMapBlockedByUsbMsc(const char* name)
{
    return (strcmp(name, "Pages/LiveMap") == 0)
        && HAL::USB_IsMassStorageOnSD()
        && HAL::USB_IsPlugged();
}

/*------------------------------------------------------------------------------
 * USB 模拟 U 盘期间，进入地图被拒时的解释性提示弹窗
 *
 * 背景：SD 卡被模拟成 U 盘供 PC 访问时，SDIO 被 USB MSC 独占，地图无法读取
 * 瓦片，故 LiveMap 入口被 IsLiveMapBlockedByUsbMsc 拦截。原实现仅静默返回，
 * 用户无从知晓原因，这里补一个带淡入淡出动画的轻量提示。
 *
 * 注意：本设备字库仅含拉丁字体（无中文字库），弹窗文案使用英文，与工程既有
 * UI（如 FileBrowser）保持一致；中文仅用于代码注释。
 *----------------------------------------------------------------------------*/

/* 中文子集字库（USER/App/Resource/Font/font_cn_16.c，由 SimHei 生成，
 * 仅含本提示用到的汉字与 ASCII，16px/bpp4）。
 * 用 extern "C" 声明以匹配字库 .c 的 C linkage 符号：MSVC(模拟器)对 C++ 全局 const
 * 变量做名称修饰，裸 LV_FONT_DECLARE 会找不到 C 符号而链接失败；armcc 不区分，故硬件
 * 原本即可链接。与 ResourcePool 中 extern "C" 引用字体的方式保持一致。 */
extern "C" {
    LV_FONT_DECLARE(font_cn_16);
}

/* 弹窗单例指针，避免重复弹出 */
static lv_obj_t* UsbMscNoticeBox = nullptr;
/* 淡入/淡出时长与完全显示后的停留时长（毫秒） */
static const uint32_t USB_MSC_NOTICE_FADE_MS = 250;
static const uint32_t USB_MSC_NOTICE_HOLD_MS = 2600;

/* 透明度动画执行回调：驱动整框（含子标签）淡入淡出 */
static void UsbMscNotice_OpaAnimCb(void* obj, int32_t opa)
{
    lv_obj_set_style_opa((lv_obj_t*)obj, (lv_opa_t)opa, 0);
}

/* 框删除事件：复位单例指针（点击关闭/淡出自毁/屏幕清理均会触发） */
static void UsbMscNotice_DeleteEventCb(lv_event_t* e)
{
    LV_UNUSED(e);
    UsbMscNoticeBox = nullptr;
}

/* 淡出动画结束：销毁弹窗本体 */
static void UsbMscNotice_FadeOutDoneCb(lv_anim_t* a)
{
    lv_obj_t* box = (lv_obj_t*)lv_anim_get_user_data(a);
    if (box != nullptr)
    {
        lv_obj_del(box);
    }
}

/* 点击弹窗：立即关闭（删除对象会自动取消其上的动画，安全） */
static void UsbMscNotice_ClickEventCb(lv_event_t* e)
{
    lv_obj_del(lv_event_get_target(e));
}

/* 显示“地图不可用”提示：淡入 -> 停留 -> 淡出自毁；单例防重复 */
static void ShowUsbMscBlockNotice(void)
{
    if (UsbMscNoticeBox != nullptr)
    {
        return;
    }

    /* 置于顶层，覆盖当前页面，且不随页面切换被销毁 */
    lv_obj_t* box = lv_obj_create(lv_layer_top());
    UsbMscNoticeBox = box;

    /* 卡片外观：居中、深色底白字，高度随内容自适应，确保任意主题下均清晰可见 */
    lv_obj_set_width(box, 220);
    lv_obj_set_height(box, LV_SIZE_CONTENT);
    lv_obj_set_style_max_height(box, LV_VER_RES - 24, 0);
    lv_obj_align(box, LV_ALIGN_CENTER, 0, 0);
    lv_obj_clear_flag(box, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(box, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_radius(box, 8, 0);
    lv_obj_set_style_border_width(box, 0, 0);
    lv_obj_set_style_bg_color(box, lv_color_hex(0x2B2B2B), 0);
    lv_obj_set_style_bg_opa(box, LV_OPA_COVER, 0);
    lv_obj_set_style_pad_all(box, 12, 0);
    lv_obj_set_style_text_color(box, lv_color_white(), 0);

    /* 纵向流式布局，标题与正文居中堆叠 */
    lv_obj_set_flex_flow(box, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(box, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

    /* 标题：无法进入地图 */
    lv_obj_t* title = lv_label_create(box);
    lv_obj_set_style_text_font(title, &font_cn_16, 0);
    lv_label_set_text(title, "\xE6\x97\xA0" "\xE6\xB3\x95" "\xE8\xBF\x9B" "\xE5\x85\xA5" "\xE5\x9C\xB0" "\xE5\x9B\xBE");
    lv_obj_set_style_text_align(title, LV_TEXT_ALIGN_CENTER, 0);

    /* 正文：SD卡正作为U盘，拔出USB后可进入。 */
    lv_obj_t* body = lv_label_create(box);
    lv_obj_set_style_text_font(body, &font_cn_16, 0);
    lv_label_set_long_mode(body, LV_LABEL_LONG_WRAP);
    lv_obj_set_width(body, lv_pct(100));
    lv_label_set_text(body,
        "S" "D" "\xE5\x8D\xA1" "\xE6\xAD\xA3" "\xE4\xBD\x9C" "\xE4\xB8\xBA" "U" "\xE7\x9B\x98" "\xEF\xBC\x8C" "\xE6\x8B\x94" "\xE5\x87\xBA" "U" "S" "B" "\xE5\x90\x8E" "\xE5\x8F\xAF" "\xE8\xBF\x9B" "\xE5\x85\xA5" "\xE3\x80\x82");
    lv_obj_set_style_text_align(body, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_pad_top(body, 8, 0);

    /* 单例复位与点击关闭 */
    lv_obj_add_event_cb(box, UsbMscNotice_DeleteEventCb, LV_EVENT_DELETE, nullptr);
    lv_obj_add_event_cb(box, UsbMscNotice_ClickEventCb, LV_EVENT_CLICKED, nullptr);

    /* 淡入：透明 -> 不透明 */
    lv_obj_fade_in(box, USB_MSC_NOTICE_FADE_MS, 0);

    /* 自动关闭：停留后淡出，结束即自毁。
     * 关闭 early_apply，避免淡出动画在延迟期间抢先把透明度拉到起始值而打断淡入。 */
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, box);
    lv_anim_set_user_data(&a, box);
    lv_anim_set_values(&a, LV_OPA_COVER, LV_OPA_TRANSP);
    lv_anim_set_time(&a, USB_MSC_NOTICE_FADE_MS);
    lv_anim_set_delay(&a, USB_MSC_NOTICE_FADE_MS + USB_MSC_NOTICE_HOLD_MS);
    lv_anim_set_early_apply(&a, false);
    lv_anim_set_exec_cb(&a, UsbMscNotice_OpaAnimCb);
    lv_anim_set_ready_cb(&a, UsbMscNotice_FadeOutDoneCb);
    lv_anim_start(&a);
}

 /**
   * @brief  Enter a new page, replace the old page
   * @param  name: The name of the page to enter
   * @param  stash: Parameters passed to the new page
   * @retval Return true if successful
   */
bool PageManager::Replace(const char* name, const PageBase::Stash_t* stash)
{
    /* Check whether the animation of switching pages is being executed */
    if (!SwitchAnimStateCheck())
    {
        return false;
    }

    if (IsLiveMapBlockedByUsbMsc(name))
    {
        PM_LOG_WARN("LiveMap is blocked: USB MSC is using SD card storage");
        ShowUsbMscBlockNotice();
        return false;
    }

    /* Check whether the stack is repeatedly pushed  */
    if (FindPageInStack(name) != nullptr)
    {
        PM_LOG_ERROR("Page(%s) was multi push", name);
        return false;
    }

    /* Check if the page is registered in the page pool */
    PageBase* base = FindPageInPool(name);

    if (base == nullptr)
    {
        PM_LOG_ERROR("Page(%s) was not install", name);
        return false;
    }

    /* Get the top page of the stack */
    PageBase* top = GetStackTop();

    if (top == nullptr)
    {
        PM_LOG_ERROR("Stack top is NULL");
        return false;
    }

    /* Force disable cache */
    top->priv.IsCached = false;

    /* Synchronous automatic cache configuration */
    base->priv.IsDisableAutoCache = base->priv.ReqDisableAutoCache;

    /* Remove current page */
    _PageStack.pop();

    /* Push into the stack */
    _PageStack.push(base);

    PM_LOG_INFO("Page(%s) replace Page(%s) (stash = 0x%p)", name, top->_Name, stash);
    /* Page switching execution */
    return SwitchTo(base, true, stash);
}

/**
  * @brief  Enter a new page, the old page is pushed onto the stack
  * @param  name: The name of the page to enter
  * @param  stash: Parameters passed to the new page
  * @retval Return true if successful
  */
bool PageManager::Push(const char* name, const PageBase::Stash_t* stash)
{
    if (IsLiveMapBlockedByUsbMsc(name))
    {
        PM_LOG_WARN("LiveMap is blocked: USB MSC is using SD card storage");
        ShowUsbMscBlockNotice();
        return false;
    }

    /* Check whether the animation of switching pages is being executed */
    if (!SwitchAnimStateCheck())
    {
        return false;
    }

    /* Check whether the stack is repeatedly pushed  */
    if (FindPageInStack(name) != nullptr)
    {
        PM_LOG_ERROR("Page(%s) was multi push", name);
        return false;
    }

    /* Check if the page is registered in the page pool */
    PageBase* base = FindPageInPool(name);

    if (base == nullptr)
    {
        PM_LOG_ERROR("Page(%s) was not install", name);
        return false;
    }

    /* Synchronous automatic cache configuration */
    base->priv.IsDisableAutoCache = base->priv.ReqDisableAutoCache;

    /* Push into the stack */
    _PageStack.push(base);

    PM_LOG_INFO("Page(%s) push >> [Screen] (stash = 0x%p)", name, stash);

    /* Page switching execution */
    return SwitchTo(base, true, stash);
}

/**
  * @brief  Pop the current page
  * @param  None
  * @retval Return true if successful
  */
bool PageManager::Pop()
{
    /* Check whether the animation of switching pages is being executed */
    if (!SwitchAnimStateCheck())
    {
        return false;
    }

    /* Get the top page of the stack */
    PageBase* top = GetStackTop();

    if (top == nullptr)
    {
        PM_LOG_WARN("Page stack is empty, cat't pop");
        return false;
    }

    /* Whether to turn off automatic cache */
    if (!top->priv.IsDisableAutoCache)
    {
        PM_LOG_INFO("Page(%s) has auto cache, cache disabled", top->_Name);
        top->priv.IsCached = false;
    }

    PM_LOG_INFO("Page(%s) pop << [Screen]", top->_Name);
    /* Page popup */
    _PageStack.pop();

    /* Get the next page */
    top = GetStackTop();

    /* Page switching execution */
    return SwitchTo(top, false, nullptr);;
}

/**
  * @brief  Page switching
  * @param  newNode: Pointer to new page
  * @param  isEnterAct: Whether it is a ENTER action
  * @param  stash: Parameters passed to the new page
  * @retval Return true if successful
  */
bool PageManager::SwitchTo(PageBase* newNode, bool isEnterAct, const PageBase::Stash_t* stash)
{
    if (newNode == nullptr)
    {
        PM_LOG_ERROR("newNode is nullptr");
        return false;
    }

    /* Whether page switching has been requested */
    if (_AnimState.IsSwitchReq)
    {
        PM_LOG_WARN("Page switch busy, reqire(%s) is ignore", newNode->_Name);
        return false;
    }

    _AnimState.IsSwitchReq = true;

    /* Is there a parameter to pass */
    if (stash != nullptr)
    {
        PM_LOG_INFO("stash is detect, %s >> stash(0x%p) >> %s", GetPagePrevName(), stash, newNode->_Name);

        void* buffer = nullptr;

        if (newNode->priv.Stash.ptr == nullptr)
        {
            buffer = lv_mem_alloc(stash->size);
            if (buffer == nullptr)
            {
                PM_LOG_ERROR("stash malloc failed");
            }
            else
            {
                PM_LOG_INFO("stash(0x%p) malloc[%d]", buffer, stash->size);
            }
        }
        else if(newNode->priv.Stash.size == stash->size)
        {
            buffer = newNode->priv.Stash.ptr;
            PM_LOG_INFO("stash(0x%p) is exist", buffer);
        }

        if (buffer != nullptr)
        {
            memcpy(buffer, stash->ptr, stash->size);
            PM_LOG_INFO("stash memcpy[%d] 0x%p >> 0x%p", stash->size, stash->ptr, buffer);
            newNode->priv.Stash.ptr = buffer;
            newNode->priv.Stash.size = stash->size;
        }
    }

    /* Record current page */
    _PageCurrent = newNode;

    /* If the current page has a cache */
    if (_PageCurrent->priv.IsCached)
    {
        /* Direct display, no need to load */
        PM_LOG_INFO("Page(%s) has cached, appear driectly", _PageCurrent->_Name);
        _PageCurrent->priv.State = PageBase::PAGE_STATE_WILL_APPEAR;
    }
    else
    {
        /* Load page */
        _PageCurrent->priv.State = PageBase::PAGE_STATE_LOAD;
    }

    if (_PagePrev != nullptr)
    {
        _PagePrev->priv.Anim.IsEnter = false;
    }

    _PageCurrent->priv.Anim.IsEnter = true;

    _AnimState.IsEntering = isEnterAct;

    if (_AnimState.IsEntering)
    {
        /* Update the animation configuration according to the current page */
        SwitchAnimTypeUpdate(_PageCurrent);
    }

    /* Update the state machine of the previous page */
    StateUpdate(_PagePrev);

    /* Update the state machine of the current page */
    StateUpdate(_PageCurrent);

    /* Move the layer, move the new page to the front */
    if (_AnimState.IsEntering)
    {
        PM_LOG_INFO("Page ENTER is detect, move Page(%s) to foreground", _PageCurrent->_Name);
        if (_PagePrev)lv_obj_move_foreground(_PagePrev->_root);
        lv_obj_move_foreground(_PageCurrent->_root);
    }
    else
    {
        PM_LOG_INFO("Page EXIT is detect, move Page(%s) to foreground", GetPagePrevName());
        lv_obj_move_foreground(_PageCurrent->_root);
        if (_PagePrev)lv_obj_move_foreground(_PagePrev->_root);
    }
    return true;
}

/**
  * @brief  Force the end of the life cycle of the page without animation 
  * @param  base: Pointer to the page being executed
  * @retval Return true if successful
  */
bool PageManager::FourceUnload(PageBase* base)
{
    if (base == nullptr)
    {
        PM_LOG_ERROR("Page is nullptr, Unload failed");
        return false;
    }

    PM_LOG_INFO("Page(%s) Fource unloading...", base->_Name);

    if (base->priv.State == PageBase::PAGE_STATE_ACTIVITY)
    {
        PM_LOG_INFO("Page state is ACTIVITY, Disappearing...");
        base->onViewWillDisappear();
        base->onViewDidDisappear();
    }

    base->priv.State = StateUnloadExecute(base);

    return true;
}

/**
  * @brief  Back to the main page (the page at the bottom of the stack) 
  * @param  None
  * @retval Return true if successful
  */
bool PageManager::BackHome()
{
    /* Check whether the animation of switching pages is being executed */
    if (!SwitchAnimStateCheck())
    {
        return false;
    }

    SetStackClear(true);

    _PagePrev = nullptr;

    PageBase* home = GetStackTop();

    SwitchTo(home, false);

    return true;
}

/**
  * @brief  Check if the page switching animation is being executed
  * @param  None
  * @retval Return true if it is executing
  */
bool PageManager::SwitchAnimStateCheck()
{
    if (_AnimState.IsSwitchReq || _AnimState.IsBusy)
    {
        PM_LOG_WARN(
            "Page switch busy[AnimState.IsSwitchReq = %d,"
            "AnimState.IsBusy = %d],"
            "request ignored",
            _AnimState.IsSwitchReq,
            _AnimState.IsBusy
        );
        return false;
    }

    return true;
}

/**
  * @brief  Page switching request check 
  * @param  None
  * @retval Return true if all pages are executed
  */
bool PageManager::SwitchReqCheck()
{
    bool ret = false;
    bool lastNodeBusy = _PagePrev && _PagePrev->priv.Anim.IsBusy;

    if (!_PageCurrent->priv.Anim.IsBusy && !lastNodeBusy)
    {
        PM_LOG_INFO("----Page switch was all finished----");
        
        _AnimState.IsSwitchReq = false;
        ret = true;
        _PagePrev = _PageCurrent;
    }
    else
    {
        if (_PageCurrent->priv.Anim.IsBusy)
        {
            PM_LOG_WARN("Page PageCurrent(%s) is busy", _PageCurrent->_Name);
        }
        else
        {
            PM_LOG_WARN("Page PagePrev(%s) is busy", GetPagePrevName());
        }
    }

    return ret;
}

/**
  * @brief  PPage switching animation execution end callback 
  * @param  a: Pointer to animation
  * @retval None
  */
void PageManager::onSwitchAnimFinish(lv_anim_t* a)
{
    PageBase* base = (PageBase*)lv_anim_get_user_data(a);
    PageManager* manager = base->_Manager;

    PM_LOG_INFO("Page(%s) Anim finish", base->_Name);

    manager->StateUpdate(base);
    base->priv.Anim.IsBusy = false;
    bool isFinished = manager->SwitchReqCheck();

    if (!manager->_AnimState.IsEntering && isFinished)
    {
        manager->SwitchAnimTypeUpdate(manager->_PageCurrent);
    }
}

/**
  * @brief  Create page switching animation
  * @param  a: Point to the animated page
  * @retval None
  */
void PageManager::SwitchAnimCreate(PageBase* base)
{
    LoadAnimAttr_t animAttr;
    if (!GetCurrentLoadAnimAttr(&animAttr))
    {
        return;
    }

    lv_anim_t a;
    AnimDefaultInit(&a);
    lv_anim_set_user_data(&a, base);
    lv_anim_set_var(&a, base->_root);
    lv_anim_set_ready_cb(&a, onSwitchAnimFinish);
    lv_anim_set_exec_cb(&a, animAttr.setter);

    int32_t start = 0;

    if (animAttr.getter)
    {
        start = animAttr.getter(base->_root);
    }

    if (_AnimState.IsEntering)
    {
        if (base->priv.Anim.IsEnter)
        {
            lv_anim_set_values(
                &a,
                animAttr.push.enter.start,
                animAttr.push.enter.end
            );
        }
        else /* Exit */
        {
            lv_anim_set_values(
                &a,
                start,
                animAttr.push.exit.end
            );
        }
    }
    else /* Pop */
    {
        if (base->priv.Anim.IsEnter)
        {
            lv_anim_set_values(
                &a,
                animAttr.pop.enter.start,
                animAttr.pop.enter.end
            );
        }
        else /* Exit */
        {
            lv_anim_set_values(
                &a,
                start,
                animAttr.pop.exit.end
            );
        }
    }

    lv_anim_start(&a);
    base->priv.Anim.IsBusy = true;
}

/**
  * @brief  Set global animation properties 
  * @param  anim: Animation type
  * @param  time: Animation duration
  * @param  path: Animation curve
  * @retval None
  */
void PageManager::SetGlobalLoadAnimType(LoadAnim_t anim, uint16_t time, lv_anim_path_cb_t path)
{
    if (anim > _LOAD_ANIM_LAST)
    {
        anim = LOAD_ANIM_NONE;
    }

    _AnimState.Global.Type = anim;
    _AnimState.Global.Time = time;
    _AnimState.Global.Path = path;

    PM_LOG_INFO("Set global load anim type = %d", anim);
}

/**
  * @brief  Update current animation properties, apply page custom animation
  * @param  base: Pointer to page
  * @retval None
  */
void PageManager::SwitchAnimTypeUpdate(PageBase* base)
{
    if (base->priv.Anim.Attr.Type == LOAD_ANIM_GLOBAL)
    {
        PM_LOG_INFO(
            "Page(%s) Anim.Type was not set, use AnimState.Global.Type = %d",
            base->_Name,
            _AnimState.Global.Type
        );
        _AnimState.Current = _AnimState.Global;
    }
    else
    {
        if (base->priv.Anim.Attr.Type > _LOAD_ANIM_LAST)
        {
            PM_LOG_ERROR(
                "Page(%s) ERROR custom Anim.Type = %d, use AnimState.Global.Type = %d",
                base->_Name,
                base->priv.Anim.Attr.Type,
                _AnimState.Global.Type
            );
            base->priv.Anim.Attr = _AnimState.Global;
        }
        else
        {
            PM_LOG_INFO(
                "Page(%s) custom Anim.Type set = %d",
                base->_Name,
                base->priv.Anim.Attr.Type
            );
        }
        _AnimState.Current = base->priv.Anim.Attr;
    }
}

/**
  * @brief  Set animation default parameters
  * @param  a: Pointer to animation
  * @retval None
  */
void PageManager::AnimDefaultInit(lv_anim_t* a)
{
    lv_anim_init(a);

    uint32_t time = (GetCurrentLoadAnimType() == LOAD_ANIM_NONE) ? 1 : _AnimState.Current.Time;
    lv_anim_set_time(a, time);
    lv_anim_set_path_cb(a, _AnimState.Current.Path);
}
