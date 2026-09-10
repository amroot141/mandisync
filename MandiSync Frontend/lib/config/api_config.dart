// =========================================================
// MANDISYNC FLUTTER — API CONFIGURATION
// Supports dynamic host resolution for Web, Mobile, and Cloud (Render)
// =========================================================

import 'package:flutter/foundation.dart';

class ApiConfig {
  static String? _customHost;

  /// Dynamically set custom backend host at runtime (e.g. from settings or environment)
  static void setHost(String url) {
    _customHost = url.endsWith('/') ? url.substring(0, url.length - 1) : url;
  }

  /// Automatically resolves backend host:
  /// 1. Custom host if explicitly set
  /// 2. If running in a web browser: uses the current origin (e.g. on Render or localhost:8000)
  /// 3. Default fallback: http://localhost:8000
  static String get host {
    if (_customHost != null && _customHost!.isNotEmpty) {
      return _customHost!;
    }
    if (kIsWeb) {
      final origin = Uri.base.origin;
      if (origin.contains('onrender.com') ||
          origin.contains('railway.app') ||
          origin.endsWith(':8000')) {
        return origin;
      }
    }
    return "http://localhost:8000";
  }

  static String get apiBase => "$host/api/v1";

  // System & Health
  static String get healthEndpoint => "$host/health";
  static String get rootEndpoint => "$host/";

  // Authentication & Users (Section 1)
  static String get login => "$apiBase/auth/login";
  static String get registerUser => "$apiBase/users/register";
  static String get registerAuth => "$apiBase/auth/register";
  static String get ondcCropListings => "$apiBase/ondc/crops";
  static String get registerMock => "$apiBase/register";
  static String get usersMe => "$apiBase/users/me";

  // Farmer Crop Listings (Section 2 & 6)
  static String get crops => "$apiBase/crops";

  // Agmarknet Mandi Prices (Section 3)
  static String get marketPrices => "$apiBase/market-prices";

  // AI Price Forecasting (Section 4)
  static String get predict => "$apiBase/predict";
  static String get forecast => "$apiBase/predict/forecast";

  // Logistics & Backhaul Matching (Section 5)
  static String get logisticsQuotes => "$apiBase/logistics/quotes";
  static String get logisticsProviders => "$apiBase/logistics/providers";

  // Mock & Scaffold (Section 7)
  static String get stats => "$apiBase/stats";
  static String get transactions => "$apiBase/transactions";
  static String get history => "$apiBase/history";
  static String get aadhaarStart => "$apiBase/auth/aadhaar/start";
  static String get digilockerStart => "$apiBase/auth/digilocker/start";

  // Shared Preferences Keys
  static const String tokenKey = "mandisync_token";
  static const String userKey = "mandisync_user";
}
