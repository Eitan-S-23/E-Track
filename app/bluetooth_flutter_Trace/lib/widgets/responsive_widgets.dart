import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../services/responsive_service.dart';

/// 响应式容器
class ResponsiveContainer extends StatelessWidget {
  final Widget child;
  final double? width;
  final double? height;
  final EdgeInsets? padding;
  final EdgeInsets? margin;
  final Color? color;
  final Decoration? decoration;

  const ResponsiveContainer({
    Key? key,
    required this.child,
    this.width,
    this.height,
    this.padding,
    this.margin,
    this.color,
    this.decoration,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final responsive = Get.find<ResponsiveService>();

    return Obx(() => Container(
          width: width != null ? responsive.getContainerWidth(width!) : null,
          height:
              height != null ? responsive.getContainerHeight(height!) : null,
          padding: padding != null ? responsive.getPadding(padding!) : null,
          margin: margin != null ? responsive.getPadding(margin!) : null,
          color: color,
          decoration: decoration,
          child: child,
        ));
  }
}

/// 响应式文本
class ResponsiveText extends StatelessWidget {
  final String text;
  final double fontSize;
  final FontWeight? fontWeight;
  final Color? color;
  final TextAlign? textAlign;
  final int? maxLines;
  final TextOverflow? overflow;

  const ResponsiveText(
    this.text, {
    Key? key,
    required this.fontSize,
    this.fontWeight,
    this.color,
    this.textAlign,
    this.maxLines,
    this.overflow,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final responsive = Get.find<ResponsiveService>();

    return Obx(() => Text(
          text,
          style: TextStyle(
            fontSize: responsive.getFontSize(fontSize),
            fontWeight: fontWeight,
            color: color,
          ),
          textAlign: textAlign,
          maxLines: maxLines,
          overflow: overflow,
        ));
  }
}

/// 响应式图标
class ResponsiveIcon extends StatelessWidget {
  final IconData icon;
  final double size;
  final Color? color;

  const ResponsiveIcon(
    this.icon, {
    Key? key,
    required this.size,
    this.color,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final responsive = Get.find<ResponsiveService>();

    return Obx(() => Icon(
          icon,
          size: responsive.getIconSize(size),
          color: color,
        ));
  }
}

/// 响应式按钮
class ResponsiveElevatedButton extends StatelessWidget {
  final VoidCallback? onPressed;
  final Widget child;
  final Size? size;
  final EdgeInsets? padding;

  const ResponsiveElevatedButton({
    Key? key,
    required this.onPressed,
    required this.child,
    this.size,
    this.padding,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final responsive = Get.find<ResponsiveService>();

    return Obx(() {
      final buttonSize = size != null ? responsive.getButtonSize(size!) : null;
      final buttonPadding =
          padding != null ? responsive.getPadding(padding!) : null;

      return SizedBox(
        width: buttonSize?.width,
        height: buttonSize?.height,
        child: ElevatedButton(
          onPressed: onPressed,
          style: ElevatedButton.styleFrom(
            padding: buttonPadding,
          ),
          child: child,
        ),
      );
    });
  }
}

/// 响应式卡片
class ResponsiveCard extends StatelessWidget {
  final Widget child;
  final double? height;
  final EdgeInsets? margin;
  final EdgeInsets? padding;
  final Color? color;
  final double? elevation;

  const ResponsiveCard({
    Key? key,
    required this.child,
    this.height,
    this.margin,
    this.padding,
    this.color,
    this.elevation,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final responsive = Get.find<ResponsiveService>();

    return Obx(() => Card(
          elevation: elevation,
          color: color,
          margin: margin != null ? responsive.getPadding(margin!) : null,
          child: Container(
            height: height != null ? responsive.getCardHeight(height!) : null,
            padding: padding != null ? responsive.getPadding(padding!) : null,
            child: child,
          ),
        ));
  }
}

/// 响应式列表项
class ResponsiveListTile extends StatelessWidget {
  final Widget? leading;
  final Widget? title;
  final Widget? subtitle;
  final Widget? trailing;
  final VoidCallback? onTap;
  final double height;

  const ResponsiveListTile({
    Key? key,
    this.leading,
    this.title,
    this.subtitle,
    this.trailing,
    this.onTap,
    this.height = 56.0,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final responsive = Get.find<ResponsiveService>();

    return Obx(() => SizedBox(
          height: responsive.getListItemHeight(height),
          child: ListTile(
            leading: leading,
            title: title,
            subtitle: subtitle,
            trailing: trailing,
            onTap: onTap,
            contentPadding: responsive.getPadding(
              const EdgeInsets.symmetric(horizontal: 16.0),
            ),
          ),
        ));
  }
}

/// 响应式间距
class ResponsiveSpacing extends StatelessWidget {
  final double spacing;
  final bool isVertical;

  const ResponsiveSpacing({
    Key? key,
    required this.spacing,
    this.isVertical = true,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final responsive = Get.find<ResponsiveService>();

    return Obx(() {
      final adjustedSpacing = responsive.getSpacing(spacing);

      return SizedBox(
        width: isVertical ? null : adjustedSpacing,
        height: isVertical ? adjustedSpacing : null,
      );
    });
  }
}

/// 响应式网格
class ResponsiveGridView extends StatelessWidget {
  final List<Widget> children;
  final int crossAxisCount;
  final double childAspectRatio;
  final EdgeInsets? padding;
  final double mainAxisSpacing;
  final double crossAxisSpacing;
  final bool shrinkWrap;
  final ScrollPhysics? physics;

  const ResponsiveGridView({
    Key? key,
    required this.children,
    required this.crossAxisCount,
    this.childAspectRatio = 1.0,
    this.padding,
    this.mainAxisSpacing = 0.0,
    this.crossAxisSpacing = 0.0,
    this.shrinkWrap = false,
    this.physics,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final responsive = Get.find<ResponsiveService>();

    return Obx(() => GridView.count(
          crossAxisCount: responsive.getGridColumns(crossAxisCount),
          childAspectRatio: childAspectRatio,
          padding: padding != null ? responsive.getPadding(padding!) : null,
          mainAxisSpacing: responsive.getSpacing(mainAxisSpacing),
          crossAxisSpacing: responsive.getSpacing(crossAxisSpacing),
          shrinkWrap: shrinkWrap,
          physics: physics,
          children: children,
        ));
  }
}

/// 响应式应用栏
class ResponsiveAppBar extends StatelessWidget implements PreferredSizeWidget {
  final Widget? title;
  final List<Widget>? actions;
  final Widget? leading;
  final bool automaticallyImplyLeading;
  final Color? backgroundColor;
  final Color? foregroundColor;
  final double? elevation;
  final PreferredSizeWidget? bottom;

  const ResponsiveAppBar({
    Key? key,
    this.title,
    this.actions,
    this.leading,
    this.automaticallyImplyLeading = true,
    this.backgroundColor,
    this.foregroundColor,
    this.elevation,
    this.bottom,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final responsive = Get.find<ResponsiveService>();

    return Obx(() => AppBar(
          title: title,
          actions: actions,
          leading: leading,
          automaticallyImplyLeading: automaticallyImplyLeading,
          backgroundColor: backgroundColor,
          foregroundColor: foregroundColor,
          elevation: elevation,
          bottom: bottom,
          toolbarHeight: responsive.getAppBarHeight(),
        ));
  }

  @override
  Size get preferredSize {
    final responsive = Get.find<ResponsiveService>();
    double height = responsive.getAppBarHeight();
    if (bottom != null) {
      height += bottom!.preferredSize.height;
    }
    return Size.fromHeight(height);
  }
}

/// 响应式对话框
class ResponsiveDialog extends StatelessWidget {
  final Widget child;
  final Size? size;
  final EdgeInsets? insetPadding;

  const ResponsiveDialog({
    Key? key,
    required this.child,
    this.size,
    this.insetPadding,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final responsive = Get.find<ResponsiveService>();

    return Obx(() {
      final dialogSize = size != null
          ? responsive.getDialogSize(size!)
          : responsive.getDialogSize(const Size(400, 300));

      return Dialog(
        insetPadding: insetPadding ??
            responsive.getPadding(
              const EdgeInsets.symmetric(horizontal: 40.0, vertical: 24.0),
            ),
        child: SizedBox(
          width: dialogSize.width,
          height: dialogSize.height,
          child: child,
        ),
      );
    });
  }
}

/// 响应式布局构建器
class ResponsiveBuilder extends StatelessWidget {
  final Widget Function(
          BuildContext context, bool isDesktop, bool isTablet, bool isMobile)
      builder;

  const ResponsiveBuilder({
    Key? key,
    required this.builder,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final responsive = Get.find<ResponsiveService>();

    return Obx(() => builder(
          context,
          responsive.isDesktop.value,
          responsive.isTablet.value,
          responsive.isMobile.value,
        ));
  }
}
