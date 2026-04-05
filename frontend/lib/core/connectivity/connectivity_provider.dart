import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

enum AppConnectivityStatus {
  online,
  offline,
  syncing,
  conflict,
}

class ConnectivityNotifier extends StateNotifier<AppConnectivityStatus> {
  StreamSubscription<List<ConnectivityResult>>? _subscription;

  ConnectivityNotifier() : super(AppConnectivityStatus.online) {
    _subscription = Connectivity().onConnectivityChanged.listen((results) {
      final hasConnection = results.any((r) => r != ConnectivityResult.none);
      state = hasConnection
          ? AppConnectivityStatus.online
          : AppConnectivityStatus.offline;
    });
  }

  @override
  void dispose() {
    _subscription?.cancel();
    super.dispose();
  }
}

final connectivityProvider =
    StateNotifierProvider<ConnectivityNotifier, AppConnectivityStatus>((ref) {
  return ConnectivityNotifier();
});
