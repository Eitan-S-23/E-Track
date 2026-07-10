import 'package:flutter/material.dart';

class CyclingDashboardPage extends StatelessWidget {
  const CyclingDashboardPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          child: Column(
            children: [
              _buildHeader(context),
              const SizedBox(height: 24),
              Expanded(
                child: Column(
                  children: [
                    _buildPrimarySection(context),
                    const SizedBox(height: 40),
                    _buildStatsGrid(context),
                    const Spacer(),
                    _buildActionArea(context),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: Colors.grey.shade100,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Row(
            children: const [
              Text(
                'GPS',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF171717),
                ),
              ),
              SizedBox(width: 4),
              Icon(
                Icons.signal_cellular_alt,
                color: Color(0xFF31C664),
                size: 16,
              ),
            ],
          ),
        ),
        const Spacer(),
        OutlinedButton(
          onPressed: () {},
          style: OutlinedButton.styleFrom(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            side: BorderSide(color: Colors.grey.shade300),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(24),
            ),
          ),
          child: const Text(
            '表盘设置',
            style: TextStyle(
              fontSize: 14,
              color: Color(0xFF171717),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildPrimarySection(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSideMetric(
          value: '--',
          label: '温度(°C)',
          footer: _buildFooterAction('心率'),
          alignment: CrossAxisAlignment.start,
        ),
        Expanded(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: const [
              Text(
                '0.00',
                style: TextStyle(
                  fontSize: 72,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF171717),
                ),
              ),
              SizedBox(height: 8),
              Text(
                '时速(km/h)',
                style: TextStyle(
                  fontSize: 16,
                  color: Color(0xFF707070),
                ),
              ),
            ],
          ),
        ),
        _buildSideMetric(
          value: '--',
          label: '功率(w)·估',
          footer: _buildFooterAction('踏频'),
          alignment: CrossAxisAlignment.end,
        ),
      ],
    );
  }

  Widget _buildStatsGrid(BuildContext context) {
    return Column(
      children: [
        Row(
          children: const [
            Expanded(child: _StatTile(value: '0.00', label: '里程(km)')),
            SizedBox(width: 16),
            Expanded(child: _StatTile(value: '00:00', label: '运动时间')),
            SizedBox(width: 16),
            Expanded(child: _StatTile(value: '0.00', label: '运动均速(km/h)')),
          ],
        ),
        const SizedBox(height: 24),
        Row(
          children: const [
            Expanded(child: _StatTile(value: '0.00', label: '极速(km/h)')),
            SizedBox(width: 16),
            Expanded(child: _StatTile(value: '0.0', label: '海拔(m)')),
            SizedBox(width: 16),
            Expanded(child: _StatTile(value: '0.0', label: '爬升(m)')),
          ],
        ),
      ],
    );
  }

  Widget _buildActionArea(BuildContext context) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: Colors.grey.shade300, width: 2),
              ),
              child: const Center(
                child: Icon(
                  Icons.directions_bike,
                  color: Color(0xFF707070),
                  size: 28,
                ),
              ),
            ),
            const SizedBox(width: 24),
            ElevatedButton(
              onPressed: () {},
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF24A8FF),
                foregroundColor: Colors.white,
                padding:
                    const EdgeInsets.symmetric(horizontal: 48, vertical: 20),
                shape: const CircleBorder(),
                elevation: 0,
              ),
              child: const Text(
                '开始',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(width: 24),
            OutlinedButton(
              onPressed: () {},
              style: OutlinedButton.styleFrom(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                foregroundColor: const Color(0xFF9B9B9B),
                side: BorderSide(color: Colors.grey.shade300),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(28),
                ),
              ),
              child: const Text(
                '继续上次',
                style: TextStyle(fontSize: 16),
              ),
            ),
          ],
        ),
        const SizedBox(height: 24),
        Container(
          height: 4,
          width: 120,
          decoration: BoxDecoration(
            color: Colors.grey.shade300,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
      ],
    );
  }

  Widget _buildSideMetric({
    required String value,
    required String label,
    required Widget footer,
    CrossAxisAlignment alignment = CrossAxisAlignment.center,
  }) {
    return SizedBox(
      width: 90,
      child: Column(
        crossAxisAlignment: alignment,
        children: [
          Text(
            value,
            style: const TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w600,
              color: Color(0xFF171717),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              color: Color(0xFF9B9B9B),
            ),
          ),
          const SizedBox(height: 24),
          footer,
        ],
      ),
    );
  }

  Widget _buildFooterAction(String title) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 12,
              color: Color(0xFF9B9B9B),
            ),
          ),
          const SizedBox(width: 6),
          const Icon(
            Icons.add,
            size: 14,
            color: Color(0xFF24A8FF),
          ),
        ],
      ),
    );
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            value,
            style: const TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w600,
              color: Color(0xFF171717),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              color: Color(0xFF9B9B9B),
            ),
          ),
        ],
      ),
    );
  }
}
