import 'dart:io';
import 'package:flutter/material.dart';
import 'package:get/get.dart';

/// 响应式布局服务
/// 根据屏幕尺寸和平台调整UI元素大小
class ResponsiveService extends GetxController {
  static ResponsiveService get to => Get.find();

  // 当前屏幕尺寸
  var screenSize = Size.zero.obs;
  var screenWidth = 0.0.obs;
  var screenHeight = 0.0.obs;

  // 设备类型
  var isDesktop = false.obs;
  var isTablet = false.obs;
  var isMobile = false.obs;

  // 响应式断点
  static const double mobileBreakpoint = 600;
  static const double tabletBreakpoint = 1024;

  @override
  void onInit() {
    super.onInit();
    _updateScreenInfo();
  }

  /// 更新屏幕信息
  void updateScreenInfo(Size size) {
    screenSize.value = size;
    screenWidth.value = size.width;
    screenHeight.value = size.height;
    _updateDeviceType();
  }

  /// 初始化屏幕信息
  void _updateScreenInfo() {
    if (Get.context != null) {
      final size = MediaQuery.of(Get.context!).size;
      updateScreenInfo(size);
    }
  }

  /// 更新设备类型
  void _updateDeviceType() {
    // 桌面平台或大屏幕
    if (Platform.isWindows ||
        Platform.isLinux ||
        Platform.isMacOS ||
        screenWidth.value >= tabletBreakpoint) {
      isDesktop.value = true;
      isTablet.value = false;
      isMobile.value = false;
    }
    // 平板尺寸
    else if (screenWidth.value >= mobileBreakpoint) {
      isDesktop.value = false;
      isTablet.value = true;
      isMobile.value = false;
    }
    // 手机尺寸
    else {
      isDesktop.value = false;
      isTablet.value = false;
      isMobile.value = true;
    }
  }

  /// 获取响应式字体大小
  double getFontSize(double baseFontSize) {
    if (isDesktop.value) {
      return baseFontSize * 0.9; // 桌面稍小
    } else if (isTablet.value) {
      return baseFontSize * 1.1; // 平板稍大
    } else {
      return baseFontSize; // 手机基准
    }
  }

  /// 获取响应式图标大小
  double getIconSize(double baseIconSize) {
    if (isDesktop.value) {
      return baseIconSize * 0.8; // 桌面更小
    } else if (isTablet.value) {
      return baseIconSize * 1.1; // 平板稍大
    } else {
      return baseIconSize; // 手机基准
    }
  }

  /// 获取响应式按钮尺寸
  Size getButtonSize(Size baseSize) {
    if (isDesktop.value) {
      return Size(baseSize.width * 0.8, baseSize.height * 0.8);
    } else if (isTablet.value) {
      return Size(baseSize.width * 1.1, baseSize.height * 1.1);
    } else {
      return baseSize;
    }
  }

  /// 获取响应式边距
  EdgeInsets getPadding(EdgeInsets basePadding) {
    double scale = 1.0;

    if (isDesktop.value) {
      scale = 0.7; // 桌面更紧凑
    } else if (isTablet.value) {
      scale = 1.2; // 平板更宽松
    }

    return EdgeInsets.fromLTRB(
      basePadding.left * scale,
      basePadding.top * scale,
      basePadding.right * scale,
      basePadding.bottom * scale,
    );
  }

  /// 获取响应式间距
  double getSpacing(double baseSpacing) {
    if (isDesktop.value) {
      return baseSpacing * 0.7;
    } else if (isTablet.value) {
      return baseSpacing * 1.2;
    } else {
      return baseSpacing;
    }
  }

  /// 获取响应式容器高度
  double getContainerHeight(double baseHeight) {
    if (isDesktop.value) {
      return baseHeight * 0.8;
    } else if (isTablet.value) {
      return baseHeight * 1.1;
    } else {
      return baseHeight;
    }
  }

  /// 获取响应式容器宽度
  double getContainerWidth(double baseWidth) {
    if (isDesktop.value) {
      return baseWidth * 0.9;
    } else if (isTablet.value) {
      return baseWidth * 1.05;
    } else {
      return baseWidth;
    }
  }

  /// 获取响应式卡片高度
  double getCardHeight(double baseHeight) {
    if (isDesktop.value) {
      // 桌面环境卡片更紧凑
      return baseHeight * 0.75;
    } else if (isTablet.value) {
      return baseHeight * 1.1;
    } else {
      return baseHeight;
    }
  }

  /// 获取网格列数
  int getGridColumns(int baseCols) {
    if (isDesktop.value) {
      return (baseCols * 1.5).round(); // 桌面更多列
    } else if (isTablet.value) {
      return (baseCols * 1.2).round(); // 平板稍多
    } else {
      return baseCols;
    }
  }

  /// 获取列表项高度
  double getListItemHeight(double baseHeight) {
    if (isDesktop.value) {
      return baseHeight * 0.8; // 桌面更紧凑
    } else if (isTablet.value) {
      return baseHeight * 1.1;
    } else {
      return baseHeight;
    }
  }

  /// 获取应用栏高度
  double getAppBarHeight() {
    if (isDesktop.value) {
      return 48.0; // 桌面更矮
    } else if (isTablet.value) {
      return 64.0; // 平板标准
    } else {
      return 56.0; // 手机标准
    }
  }

  /// 获取底部导航栏高度
  double getBottomNavHeight() {
    if (isDesktop.value) {
      return 56.0; // 桌面稍矮
    } else if (isTablet.value) {
      return 72.0; // 平板稍高
    } else {
      return 64.0; // 手机标准
    }
  }

  /// 获取对话框尺寸
  Size getDialogSize(Size baseSize) {
    if (isDesktop.value) {
      // 桌面对话框相对屏幕更小
      return Size(
        screenWidth.value * 0.4,
        screenHeight.value * 0.6,
      );
    } else if (isTablet.value) {
      return Size(
        screenWidth.value * 0.6,
        screenHeight.value * 0.7,
      );
    } else {
      return Size(
        screenWidth.value * 0.9,
        screenHeight.value * 0.8,
      );
    }
  }

  /// 是否应该使用紧凑布局
  bool get useCompactLayout => isDesktop.value;

  /// 是否应该显示侧边栏
  bool get shouldShowSidebar => isDesktop.value;

  /// 获取侧边栏宽度
  double get sidebarWidth {
    if (isDesktop.value) {
      return 250.0;
    } else {
      return 200.0;
    }
  }

  /// 获取主内容区域宽度
  double get contentWidth {
    if (shouldShowSidebar) {
      return screenWidth.value - sidebarWidth;
    } else {
      return screenWidth.value;
    }
  }

  /// 平台信息
  String get platformInfo {
    if (Platform.isWindows) return 'Windows';
    if (Platform.isMacOS) return 'macOS';
    if (Platform.isLinux) return 'Linux';
    if (Platform.isAndroid) return 'Android';
    if (Platform.isIOS) return 'iOS';
    return 'Unknown';
  }

  /// 获取设备类型文字
  String get deviceTypeText {
    if (isDesktop.value) return '桌面';
    if (isTablet.value) return '平板';
    if (isMobile.value) return '手机';
    return '未知';
  }
}
