import 'package:flutter/material.dart';
import 'device_tab_page.dart';
import 'shop_tab_page.dart';
import 'profile_tab_page.dart';

class NewMainPage extends StatefulWidget {
  const NewMainPage({Key? key}) : super(key: key);

  @override
  State<NewMainPage> createState() => _NewMainPageState();
}

class _NewMainPageState extends State<NewMainPage> {
  int _currentIndex = 0;

  final List<Widget> _pages = [
    const DeviceTabPage(),
    const ShopTabPage(),
    const ProfileTabPage(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _pages,
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.1),
              blurRadius: 10,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: BottomNavigationBar(
          currentIndex: _currentIndex,
          onTap: (index) {
            setState(() {
              _currentIndex = index;
            });
          },
          type: BottomNavigationBarType.fixed,
          backgroundColor: Colors.transparent,
          elevation: 0,
          selectedItemColor: const Color(0xFF4A90E2),
          unselectedItemColor: Colors.grey[600],
          selectedFontSize: 12,
          unselectedFontSize: 12,
          items: [
            BottomNavigationBarItem(
              icon: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: _currentIndex == 0
                      ? const Color(0xFF4A90E2).withOpacity(0.1)
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  _currentIndex == 0 ? Icons.devices : Icons.devices_outlined,
                  size: 24,
                ),
              ),
              label: '设备',
            ),
            BottomNavigationBarItem(
              icon: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: _currentIndex == 1
                      ? const Color(0xFF4A90E2).withOpacity(0.1)
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  _currentIndex == 1 ? Icons.explore : Icons.explore_outlined,
                  size: 24,
                ),
              ),
              label: '发现',
            ),
            BottomNavigationBarItem(
              icon: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: _currentIndex == 2
                      ? const Color(0xFF4A90E2).withOpacity(0.1)
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  _currentIndex == 2 ? Icons.person : Icons.person_outlined,
                  size: 24,
                ),
              ),
              label: '我的',
            ),
          ],
        ),
      ),
    );
  }
}
