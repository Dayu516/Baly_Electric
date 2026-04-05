import 'package:flutter/material.dart';

/// Level C 功能的引導頁 — 不是錯誤頁。
///
/// 告訴使用者去哪裡操作。
/// 禁止顯示「功能開發中」。
class FeatureLockedPage extends StatelessWidget {
  final String featureName;
  final String guidanceMessage;

  const FeatureLockedPage({
    super.key,
    required this.featureName,
    this.guidanceMessage = '請在桌面版操作此功能',
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(featureName)),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.desktop_windows_outlined,
                size: 80,
                color: Theme.of(context).colorScheme.outline,
              ),
              const SizedBox(height: 24),
              Text(
                featureName,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              Text(
                guidanceMessage,
                style: Theme.of(context).textTheme.bodyLarge,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
