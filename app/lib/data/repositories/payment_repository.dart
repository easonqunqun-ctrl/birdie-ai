import '../../core/api_client.dart';

class PlanOption {
  final String planType;
  final String name;
  final String amountYuanDisplay;
  final String? hint;

  const PlanOption({
    required this.planType,
    required this.name,
    required this.amountYuanDisplay,
    this.hint,
  });

  factory PlanOption.fromJson(Map<String, dynamic> j) => PlanOption(
        planType: j['plan_type']?.toString() ?? '',
        name: j['name']?.toString() ?? '',
        amountYuanDisplay: j['amount_yuan_display']?.toString() ??
            j['price_display']?.toString() ??
            '',
        hint: j['hint']?.toString() ?? j['subtitle']?.toString(),
      );
}

class CreateOrderResult {
  final String orderId;
  final bool mockMode;

  const CreateOrderResult({required this.orderId, required this.mockMode});

  factory CreateOrderResult.fromJson(Map<String, dynamic> j) {
    final order = j['order'] as Map<String, dynamic>? ?? const {};
    return CreateOrderResult(
      orderId: order['id']?.toString() ?? '',
      mockMode: j['mock_mode'] == true,
    );
  }
}

/// 支付域：对照 client paymentService（App 优先走 mock-confirm）。
class PaymentRepository {
  PaymentRepository(this._api);
  final ApiClient _api;

  Future<List<PlanOption>> listPlans() async {
    final data = await _api.get<dynamic>('/payments/plans');
    final list = data is List
        ? data
        : (data is Map ? (data['items'] as List? ?? const []) : const []);
    return list
        .whereType<Map>()
        .map((e) => PlanOption.fromJson(Map<String, dynamic>.from(e)))
        .toList();
  }

  Future<CreateOrderResult> createOrder(String planType) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/payments/orders',
      data: {'plan_type': planType},
    );
    return CreateOrderResult.fromJson(data);
  }

  Future<void> mockConfirm(String orderId) async {
    await _api.post<dynamic>('/payments/orders/$orderId/mock-confirm', data: {});
  }
}
