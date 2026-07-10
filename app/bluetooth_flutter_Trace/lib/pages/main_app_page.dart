import 'package:flutter/material.dart';
import 'device_tab_page.dart';
import 'discover_tab_page.dart';
import 'profile_tab_page.dart';
import 'trace_ui.dart';

class MainAppPage extends StatefulWidget {
  const MainAppPage({Key? key}) : super(key: key);

  @override
  State<MainAppPage> createState() => _MainAppPageState();
}

class _MainAppPageState extends State<MainAppPage> {
  int _selectedIndex = 0;
  bool _deviceOrbitActive = false;
  late final PageController _pageController;

  final List<Widget> _pages = const [
    DeviceTabPage(),
    DiscoverTabPage(),
    ProfileTabPage(),
  ];

  final List<_TraceNavItem> _navItems = const [
    _TraceNavItem(
      icon: Icons.devices_outlined,
      activeIcon: Icons.devices,
      label: '设备',
    ),
    _TraceNavItem(
      icon: Icons.explore_outlined,
      activeIcon: Icons.explore,
      label: '发现',
    ),
    _TraceNavItem(
      icon: Icons.person_outline,
      activeIcon: Icons.person,
      label: '我的',
    ),
  ];

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _selectPage(int index) {
    if (index == _selectedIndex) return;
    setState(() {
      _selectedIndex = index;
    });
    _pageController.animateToPage(
      index,
      duration: const Duration(milliseconds: 260),
      curve: Curves.easeOutCubic,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: TraceColors.ink,
      body: TracePageScaffold(
        child: Stack(
          children: [
            Positioned.fill(
              child: NotificationListener<DeviceOrbitInteractionNotification>(
                onNotification: (notification) {
                  if (_deviceOrbitActive != notification.active) {
                    setState(() {
                      _deviceOrbitActive = notification.active;
                    });
                  }
                  return false;
                },
                child: PageView(
                  controller: _pageController,
                  physics: _deviceOrbitActive
                      ? const NeverScrollableScrollPhysics()
                      : const BouncingScrollPhysics(),
                  onPageChanged: (index) {
                    if (index == _selectedIndex) return;
                    setState(() {
                      _selectedIndex = index;
                    });
                  },
                  children: _pages,
                ),
              ),
            ),
            Positioned(
              left: 22,
              right: 22,
              bottom: 10,
              child: SafeArea(
                top: false,
                child: _TraceBottomNavigation(
                  currentIndex: _selectedIndex,
                  items: _navItems,
                  onChanged: _selectPage,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TraceNavItem {
  const _TraceNavItem({
    required this.icon,
    required this.activeIcon,
    required this.label,
  });

  final IconData icon;
  final IconData activeIcon;
  final String label;
}

class _TraceBottomNavigation extends StatelessWidget {
  const _TraceBottomNavigation({
    required this.currentIndex,
    required this.items,
    required this.onChanged,
  });

  final int currentIndex;
  final List<_TraceNavItem> items;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 86,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            const Color(0xFF03121A).withOpacity(0.66),
            const Color(0xFF02090F).withOpacity(0.58),
          ],
        ),
        borderRadius: BorderRadius.circular(44),
        border: Border.all(color: TraceColors.cyan.withOpacity(0.28)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.56),
            blurRadius: 34,
            offset: const Offset(0, 18),
          ),
          BoxShadow(
            color: TraceColors.cyan.withOpacity(0.22),
            blurRadius: 34,
            spreadRadius: -10,
          ),
        ],
      ),
      child: Row(
        children: List.generate(items.length, (index) {
          final item = items[index];
          final selected = currentIndex == index;
          final color = selected ? TraceColors.cyan : TraceColors.muted;

          return Expanded(
            child: Row(
              children: [
                Expanded(
                  child: Material(
                    color: Colors.transparent,
                    borderRadius: BorderRadius.circular(30),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(30),
                      onTap: () => onChanged(index),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 220),
                        curve: Curves.easeOutCubic,
                        height: 68,
                        decoration: BoxDecoration(
                          color: selected
                              ? TraceColors.cyan.withOpacity(0.12)
                              : Colors.transparent,
                          borderRadius: BorderRadius.circular(30),
                          boxShadow: selected
                              ? [
                                  BoxShadow(
                                    color: TraceColors.cyan.withOpacity(0.24),
                                    blurRadius: 24,
                                    spreadRadius: -8,
                                  ),
                                ]
                              : const [],
                        ),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              selected ? item.activeIcon : item.icon,
                              color: color,
                              size: selected ? 27 : 25,
                              shadows: selected
                                  ? [
                                      Shadow(
                                        color:
                                            TraceColors.cyan.withOpacity(0.85),
                                        blurRadius: 14,
                                      ),
                                    ]
                                  : const [],
                            ),
                            const SizedBox(height: 5),
                            Text(
                              item.label,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                color: selected
                                    ? TraceColors.cyanSoft
                                    : TraceColors.muted,
                                fontSize: 14,
                                height: 1,
                                fontWeight: selected
                                    ? FontWeight.w900
                                    : FontWeight.w700,
                                shadows: selected
                                    ? [
                                        Shadow(
                                          color: TraceColors.cyan
                                              .withOpacity(0.75),
                                          blurRadius: 12,
                                        ),
                                      ]
                                    : const [],
                              ),
                            ),
                            AnimatedContainer(
                              duration: const Duration(milliseconds: 220),
                              margin: const EdgeInsets.only(top: 6),
                              width: selected ? 40 : 0,
                              height: 2,
                              decoration: BoxDecoration(
                                color: TraceColors.cyan,
                                borderRadius: BorderRadius.circular(2),
                                boxShadow: selected
                                    ? [
                                        BoxShadow(
                                          color: TraceColors.cyan
                                              .withOpacity(0.9),
                                          blurRadius: 8,
                                        ),
                                      ]
                                    : const [],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
                if (index != items.length - 1)
                  Container(
                    width: 1,
                    height: 32,
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    color: TraceColors.cyan.withOpacity(0.14),
                  ),
              ],
            ),
          );
        }),
      ),
    );
  }
}
