/**
 * @file lv_port_indev_templ.c
 *
 */

 /*Copy this file as "lv_port_indev.c" and set this value to "1" to enable content*/
#if 1

/*********************
 *      INCLUDES
 *********************/
#include "lv_port.h"
#include "lvgl/lvgl.h"
#include "HAL/HAL.h"

/*********************
 *      DEFINES
 *********************/

/**********************
 *      TYPEDEFS
 **********************/

/**********************
 *  STATIC PROTOTYPES
 **********************/

static void encoder_init(void);
static void encoder_read(lv_indev_drv_t * indev_drv, lv_indev_data_t * data);
static void touch_init(void);
static void touch_read(lv_indev_drv_t * indev_drv, lv_indev_data_t * data);

/**********************
 *  STATIC VARIABLES
 **********************/

/**********************
 *      MACROS
 **********************/

/**********************
 *   GLOBAL FUNCTIONS
 **********************/

void lv_port_indev_init(void)
{
    static lv_indev_drv_t touch_indev_drv;
    static lv_indev_drv_t encoder_indev_drv;

    /*------------------
     * Touch
     * -----------------*/

    touch_init();

    lv_indev_drv_init(&touch_indev_drv);
    touch_indev_drv.type = LV_INDEV_TYPE_POINTER;
    touch_indev_drv.read_cb = touch_read;
    lv_indev_drv_register(&touch_indev_drv);

    /*------------------
     * Encoder
     * -----------------*/

    /*Initialize your encoder if you have*/
    encoder_init();

    /*Register a encoder input device*/
    lv_indev_drv_init(&encoder_indev_drv);
    encoder_indev_drv.type = LV_INDEV_TYPE_ENCODER;
    encoder_indev_drv.read_cb = encoder_read;
    lv_indev_t* indev = lv_indev_drv_register(&encoder_indev_drv);
    
    lv_group_t* group = lv_group_create();
    lv_indev_set_group(indev, group);
    lv_group_set_default(group);

    /* Later you should create group(s) with `lv_group_t * group = lv_group_create()`,
     * add objects to the group with `lv_group_add_obj(group, obj)`
     * and assign this input device to group to navigate in it:
     * `lv_indev_set_group(indev_encoder, group);` */
}

/**********************
 *   STATIC FUNCTIONS
 **********************/

/*------------------
 * Touch
 * -----------------*/

static void touch_init(void)
{
}

static void touch_read(lv_indev_drv_t * indev_drv, lv_indev_data_t * data)
{
    (void)indev_drv;

    static lv_point_t lastPoint;
    int16_t x;
    int16_t y;

    if (HAL::Touch_GetPoint(&x, &y))
    {
        lastPoint.x = x;
        lastPoint.y = y;
        data->state = LV_INDEV_STATE_PRESSED;
    }
    else
    {
        data->state = LV_INDEV_STATE_RELEASED;
    }

    data->point = lastPoint;
}

/*------------------
 * Encoder
 * -----------------*/

/* Initialize your keypad */
static void encoder_init(void)
{
    /*Your code comes here*/
}

/* Will be called by the library to read the encoder */
static void encoder_read(lv_indev_drv_t * indev_drv, lv_indev_data_t * data)
{
    static bool lastState;
    data->enc_diff = HAL::Encoder_GetDiff();
    
    bool isPush = HAL::Encoder_GetIsPush();
    
    data->state = isPush ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
    
    if(isPush != lastState)
    {
        HAL::Buzz_Tone(isPush ? 500 : 700, 20);
        lastState = isPush;
    }
}

#else /* Enable this file at the top */

/* This dummy typedef exists purely to silence -Wpedantic. */
typedef int keep_pedantic_happy;
#endif
