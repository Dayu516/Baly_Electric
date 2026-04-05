/// 統一回傳格式，對應後端 Result。
class Result<T> {
  final bool success;
  final String code;
  final String message;
  final T? data;
  final bool retryable;
  final String severity;

  const Result({
    required this.success,
    required this.code,
    this.message = '',
    this.data,
    this.retryable = false,
    this.severity = 'info',
  });

  factory Result.ok({T? data, String message = ''}) {
    return Result(success: true, code: 'OK', message: message, data: data);
  }

  factory Result.fail(String code, String message,
      {bool retryable = false, String severity = 'error'}) {
    return Result(
      success: false,
      code: code,
      message: message,
      retryable: retryable,
      severity: severity,
    );
  }

  bool get isFailure => !success;
}
