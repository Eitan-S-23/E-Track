import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../services/scan_settings_service.dart';
import '../controllers/monitor_controller.dart';

class ScanSettingsPage extends StatelessWidget {
  const ScanSettingsPage({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final scanSettings = Get.find<ScanSettingsService>();
    final TextEditingController customController = TextEditingController();

    return Scaffold(
      appBar: AppBar(
        title: const Text('扫描设置'),
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF2E3A59),
        elevation: 0,
      ),
      body: Obx(() => Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // 当前设置显示
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xFF4A90E2).withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: const Color(0xFF4A90E2).withOpacity(0.3),
                      width: 1,
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '当前扫描间隔',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFF2E3A59),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${scanSettings.scanIntervalSeconds}秒 (${scanSettings.scanInterval.value}毫秒)',
                        style: TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.bold,
                          color: const Color(0xFF4A90E2),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '扫描间隔决定了设备数据的更新频率，较短的间隔可获得更实时的数据，但会增加电池消耗',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[600],
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 24),

                // 预设选项
                const Text(
                  '预设选项',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF2E3A59),
                  ),
                ),

                const SizedBox(height: 12),

                Expanded(
                  child: GridView.builder(
                    gridDelegate:
                        const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      childAspectRatio: 2.5,
                      crossAxisSpacing: 12,
                      mainAxisSpacing: 12,
                    ),
                    itemCount: scanSettings.getPresetIntervals().length,
                    itemBuilder: (context, index) {
                      final preset = scanSettings.getPresetIntervals()[index];
                      final isSelected = scanSettings.scanInterval.value ==
                          preset['milliseconds'];

                      return GestureDetector(
                        onTap: () async {
                          if (!isSelected) {
                            await scanSettings.setScanIntervalSeconds(
                              preset['value'],
                              onChanged: () =>
                                  MonitorController.to.refreshScanInterval(),
                            );
                          }
                        },
                        child: Container(
                          decoration: BoxDecoration(
                            color: isSelected
                                ? const Color(0xFF4A90E2)
                                : Colors.white,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: isSelected
                                  ? const Color(0xFF4A90E2)
                                  : Colors.grey.shade300,
                              width: isSelected ? 2 : 1,
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.black.withOpacity(0.05),
                                blurRadius: 8,
                                offset: const Offset(0, 2),
                              ),
                            ],
                          ),
                          child: Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Text(
                                  preset['label'],
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w600,
                                    color: isSelected
                                        ? Colors.white
                                        : const Color(0xFF2E3A59),
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  '${preset['milliseconds']}ms',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: isSelected
                                        ? Colors.white.withOpacity(0.8)
                                        : Colors.grey[600],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),

                const SizedBox(height: 24),

                // 自定义输入
                const Text(
                  '自定义间隔',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF2E3A59),
                  ),
                ),

                const SizedBox(height: 12),

                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: customController,
                        keyboardType: const TextInputType.numberWithOptions(
                            decimal: true),
                        decoration: InputDecoration(
                          hintText: '输入间隔秒数 (0.1-60)',
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide(color: Colors.grey.shade300),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: const BorderSide(
                                color: Color(0xFF4A90E2), width: 2),
                          ),
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 14,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    ElevatedButton(
                      onPressed: () {
                        final input = customController.text.trim();
                        if (input.isEmpty) {
                          Get.snackbar('错误', '请输入扫描间隔');
                          return;
                        }

                        final seconds = double.tryParse(input);
                        if (seconds == null) {
                          Get.snackbar('错误', '请输入有效的数字');
                          return;
                        }

                        scanSettings.setScanIntervalSeconds(
                          seconds,
                          onChanged: () =>
                              MonitorController.to.refreshScanInterval(),
                        );
                        customController.clear();
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF4A90E2),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(
                            horizontal: 24, vertical: 14),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Text('设置'),
                    ),
                  ],
                ),

                const SizedBox(height: 16),

                // 提示信息
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.orange.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: Colors.orange.withOpacity(0.3),
                      width: 1,
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.info_outline,
                        color: Colors.orange[700],
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          '建议：实时监控使用0.5-1秒，后台监控使用2-5秒',
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.orange[700],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          )),
    );
  }
}
