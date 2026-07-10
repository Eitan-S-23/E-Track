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
#include "MapConv.h"
#include <stdio.h>
#include "GPS_Transform/GPS_Transform.h"

using namespace::Microsoft_MapPoint;

#ifndef constrain
#  define constrain(amt,low,high) ((amt)<(low)?(low):((amt)>(high)?(high):(amt)))
#endif

char MapConv::dirPath[] = "/MAP";
char MapConv::extName[] = "bin";
int16_t MapConv::levelMin = 0;
int16_t MapConv::levelMax = 19;
int16_t MapConv::levelExtra = 0;
bool MapConv::coordTransformEnable = false;

/* 扩展显示级的缩放阶梯:每 +1 级线性 ×√2(面积减半),
 * 区别于标准整级的线性 ×2(面积 1/4)。 */
#define MAP_CONV_SQRT2      1.4142135623730951

/* 级别的"半级指数":标准级每级计 2 步,扩展级每级计 1 步(√2)。
 * 两级别的缩放比 = √2^(半级指数之差),用于跨级坐标换算。 */
static inline int MapLevelHalfSteps(int level, int dataMax)
{
    return (level <= dataMax) ? level * 2 : dataMax * 2 + (level - dataMax);
}

MapConv::MapConv()
{
    priv.level = 16;
    priv.tileSize = 256;
}

void MapConv::SetLevel(int level)
{
    priv.level = constrain(level, levelMin, levelMax);
}

void MapConv::GetMapTile(double longitude, double latitude, MapTile_t* mapTile)
{
    int32_t x, y;
    ConvertMapCoordinate(longitude, latitude, &x, &y);
    ConvertPosToTile(x, y, mapTile);
}

void MapConv::ConvertMapCoordinate(
    double longitude, double latitude,
    int32_t* mapX, int32_t* mapY
)
{
    int pixelX, pixelY;

    if (coordTransformEnable)
    {
        GPS_Transform(latitude, longitude, &latitude, &longitude);
    }

    int extra = priv.level - GetDataLevelMax();
    if (extra > 0)
    {
        /* 扩展显示级(√2 阶梯):坐标系 = 基准整级 × √2^(extra 奇偶),
         * extra 的偶数部分并入基准级(每 2 个扩展级等于 1 个标准级)。 */
        int baseLevel = GetDataLevelMax() + (extra >> 1);
        TileSystem::LatLongToPixelXY(latitude, longitude, baseLevel, &pixelX, &pixelY);
        if (extra & 1)
        {
            pixelX = (int)(pixelX * MAP_CONV_SQRT2 + 0.5);
            pixelY = (int)(pixelY * MAP_CONV_SQRT2 + 0.5);
        }
    }
    else
    {
        TileSystem::LatLongToPixelXY(latitude, longitude, priv.level, &pixelX, &pixelY);
    }

    *mapX = pixelX;
    *mapY = pixelY;
};

void MapConv::ConvertMapLevelPos(
    int32_t* destX, int32_t* destY,
    int32_t srcX, int32_t srcY, int srcLevel
)
{
    /* 半级指数差:diffH 每 2 步 = ×2,奇数余步 = ×√2。
     * 负奇数经算术右移取 floor 后,余步统一表现为"再除一次 √2",
     * 数学上对正负 diffH 一致成立。 */
    int dataMax = GetDataLevelMax();
    int diffH = MapLevelHalfSteps(srcLevel, dataMax)
                - MapLevelHalfSteps(GetLevel(), dataMax);
    int sh = diffH >> 1;

    int32_t x = (sh >= 0) ? (srcX >> sh) : (int32_t)((int64_t)srcX << -sh);
    int32_t y = (sh >= 0) ? (srcY >> sh) : (int32_t)((int64_t)srcY << -sh);

    if (diffH & 1)
    {
        /* ×1/√2,定点 46341/65536 */
        x = (int32_t)(((int64_t)x * 46341) >> 16);
        y = (int32_t)(((int64_t)y * 46341) >> 16);
    }

    *destX = x;
    *destY = y;
}

int MapConv::ConvertMapPath(int32_t x, int32_t y, char* path, uint32_t len)
{
    return ConvertMapPathAtLevel(priv.level, x, y, path, len);
}

int MapConv::ConvertMapPathAtLevel(int level, int32_t x, int32_t y, char* path, uint32_t len)
{
    int32_t tileX = x / priv.tileSize;
    int32_t tileY = y / priv.tileSize;
    int ret = snprintf(
                  path, len,
                  "%s/%d/%d/%d.%s",
                  dirPath,
                  level,
                  tileX,
                  tileY,
                  extName
              );

    return ret;
}

void MapConv::ConvertPosToTile(int32_t x, int32_t y, MapTile_t* mapTile)
{
    mapTile->tileX = x / priv.tileSize;
    mapTile->tileY = y / priv.tileSize;
    mapTile->subX = x % priv.tileSize;
    mapTile->subY = y % priv.tileSize;
}
