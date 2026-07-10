import 'package:flutter/material.dart';
import 'home_page.dart'; // 假设原主功能页面为 home_page.dart，可根据实际替换

class MainHomePage extends StatefulWidget {
  const MainHomePage({Key? key}) : super(key: key);

  @override
  State<MainHomePage> createState() => _MainHomePageState();
}

class _MainHomePageState extends State<MainHomePage> {
  int _selectedIndex = 0;

  final List<Widget> _pages = [
    HomePage(), // 原主功能页面
    // 未来可添加更多页面，如设置、关于等
    Center(child: Text('其他功能（待扩展）')),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('蓝牙追踪主界面')),
      body: _pages[_selectedIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home), label: '主功能'),
          BottomNavigationBarItem(icon: Icon(Icons.more_horiz), label: '更多'),
        ],
        onTap: (index) {
          setState(() {
            _selectedIndex = index;
          });
        },
      ),
    );
  }
}
