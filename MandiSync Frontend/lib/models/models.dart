// =========================================================
// MANDISYNC FLUTTER — DATA MODELS
// =========================================================

class UserModel {
  final String id;
  final String username;
  final String fullName;
  final String email;
  final String role;
  final String? phone;

  UserModel({
    required this.id,
    required this.username,
    required this.fullName,
    required this.email,
    required this.role,
    this.phone,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id']?.toString() ?? json['_id']?.toString() ?? '',
      username: json['username'] ?? '',
      fullName: json['full_name'] ?? json['name'] ?? json['username'] ?? 'Citizen',
      email: json['email'] ?? '',
      role: json['role'] ?? 'Farmer',
      phone: json['phone'],
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'username': username,
    'full_name': fullName,
    'email': email,
    'role': role,
    'phone': phone,
  };
}

class MarketPriceModel {
  final String? id;
  final String commodity;
  final String? variety;
  final String market;
  final String? district;
  final String? state;
  final String? arrivalDate;
  final double? minPrice;
  final double? modalPrice;
  final double? maxPrice;
  final dynamic arrivals;

  MarketPriceModel({
    this.id,
    required this.commodity,
    this.variety,
    required this.market,
    this.district,
    this.state,
    this.arrivalDate,
    this.minPrice,
    this.modalPrice,
    this.maxPrice,
    this.arrivals,
  });

  double? get arrivalTonnes => (arrivals as num?)?.toDouble();

  factory MarketPriceModel.fromJson(Map<String, dynamic> json) {
    return MarketPriceModel(
      id: json['id']?.toString() ?? json['_id']?.toString(),
      commodity: json['commodity'] ?? json['crop_name'] ?? 'Crop',
      variety: json['variety'],
      market: json['market'] ?? 'APMC Mandi',
      district: json['district'],
      state: json['state'],
      arrivalDate: json['arrival_date'],
      minPrice: (json['min_price'] as num?)?.toDouble(),
      modalPrice: (json['modal_price'] as num?)?.toDouble(),
      maxPrice: (json['max_price'] as num?)?.toDouble(),
      arrivals: json['arrival_tonnes'] ?? json['arrivals'],
    );
  }
}

class CropListingModel {
  final String id;
  final String cropName;
  final String? variety;
  final String? category;
  final double quantity;
  final String unit;
  final double price;
  final String location;
  final String? district;
  final String? state;
  final String? farmerName;
  final String status;
  final double? aiPredictedMaxPrice;
  final double? aiRecommendedMsp;

  CropListingModel({
    required this.id,
    required this.cropName,
    this.variety,
    this.category,
    required this.quantity,
    required this.unit,
    required this.price,
    required this.location,
    this.district,
    this.state,
    this.farmerName,
    required this.status,
    this.aiPredictedMaxPrice,
    this.aiRecommendedMsp,
  });

  factory CropListingModel.fromJson(Map<String, dynamic> json) {
    return CropListingModel(
      id: json['id']?.toString() ?? json['_id']?.toString() ?? '',
      cropName: json['crop_name'] ?? json['commodity'] ?? 'Harvest Crop',
      variety: json['variety'],
      category: json['category'],
      quantity: (json['quantity'] as num?)?.toDouble() ?? 0.0,
      unit: json['unit'] ?? 'quintal',
      price: (json['price'] as num?)?.toDouble() ?? 0.0,
      location: json['location'] ?? json['district'] ?? 'Farm Location',
      district: json['district'],
      state: json['state'],
      farmerName: json['farmer_name'],
      status: json['status'] ?? 'active',
      aiPredictedMaxPrice: (json['ai_predicted_max_price'] as num?)?.toDouble(),
      aiRecommendedMsp: (json['ai_recommended_msp'] as num?)?.toDouble(),
    );
  }
}

class PredictionResultModel {
  final String commodity;
  final String market;
  final double? predictedMaxPrice;
  final double? recommendedListingPrice;
  final double? confidenceLow;
  final double? confidenceHigh;
  final String? targetDate;
  final String? modelVersion;
  final int? inferenceLatencyMs;

  PredictionResultModel({
    required this.commodity,
    required this.market,
    this.predictedMaxPrice,
    this.recommendedListingPrice,
    this.confidenceLow,
    this.confidenceHigh,
    this.targetDate,
    this.modelVersion,
    this.inferenceLatencyMs,
  });

  factory PredictionResultModel.fromJson(Map<String, dynamic> json) {
    return PredictionResultModel(
      commodity: json['commodity'] ?? 'Commodity',
      market: json['market'] ?? 'Market',
      predictedMaxPrice: (json['predicted_max_price'] as num?)?.toDouble(),
      recommendedListingPrice: (json['recommended_listing_price'] as num?)?.toDouble(),
      confidenceLow: (json['confidence_interval_low'] as num?)?.toDouble(),
      confidenceHigh: (json['confidence_interval_high'] as num?)?.toDouble(),
      targetDate: json['target_date'],
      modelVersion: json['model_version'] ?? 'xgboost-v1.4',
      inferenceLatencyMs: (json['inference_latency_ms'] as num?)?.toInt(),
    );
  }
}

class LogisticsQuoteModel {
  final String origin;
  final String destination;
  final double distanceKm;
  final String vehicleType;
  final double standardCost;
  final bool backhaulMatched;
  final int discountPercent;
  final double discountAmount;
  final double netCost;
  final String estimatedHours;
  final int co2ReductionPct;

  LogisticsQuoteModel({
    required this.origin,
    required this.destination,
    required this.distanceKm,
    required this.vehicleType,
    required this.standardCost,
    required this.backhaulMatched,
    required this.discountPercent,
    required this.discountAmount,
    required this.netCost,
    required this.estimatedHours,
    required this.co2ReductionPct,
  });

  factory LogisticsQuoteModel.fromJson(Map<String, dynamic> json) {
    final dist = (json['distance_km'] as num?)?.toDouble() ?? 180.0;
    final std = (json['standard_cost_inr'] as num?)?.toDouble() ?? 6500.0;
    final discPct = (json['backhaul_discount_percent'] as num?)?.toInt() ?? 30;
    final discAmt = (json['discount_amount_inr'] as num?)?.toDouble() ?? (std * discPct / 100);
    final net = (json['net_delivery_cost_inr'] as num?)?.toDouble() ?? (std - discAmt);

    return LogisticsQuoteModel(
      origin: json['origin'] ?? '',
      destination: json['destination'] ?? '',
      distanceKm: dist,
      vehicleType: json['vehicle_type'] ?? 'Medium Commercial',
      standardCost: std,
      backhaulMatched: json['backhaul_matched'] ?? true,
      discountPercent: discPct,
      discountAmount: discAmt,
      netCost: net,
      estimatedHours: json['estimated_hours']?.toString() ?? (dist / 45).toStringAsFixed(1),
      co2ReductionPct: (json['co2_reduction_pct'] as num?)?.toInt() ?? 30,
    );
  }
}

class TransportProviderModel {
  final String id;
  final String driverName;
  final String vehicle;
  final String homeBase;
  final String currentLocation;
  final String status;
  final double baseFee;
  final double perKmRate;
  final double? capacityKg;

  TransportProviderModel({
    required this.id,
    required this.driverName,
    required this.vehicle,
    required this.homeBase,
    required this.currentLocation,
    required this.status,
    required this.baseFee,
    required this.perKmRate,
    this.capacityKg,
  });

  factory TransportProviderModel.fromJson(Map<String, dynamic> json) {
    return TransportProviderModel(
      id: json['id']?.toString() ?? 'PRV-${DateTime.now().millisecond}',
      driverName: json['driver_name'] ?? json['name'] ?? 'Transport Fleet',
      vehicle: json['vehicle'] ?? 'Commercial Truck',
      homeBase: json['home_base'] ?? 'Hub',
      currentLocation: json['current_location'] ?? json['location'] ?? 'Mandi Hub',
      status: json['status'] ?? 'AVAILABLE',
      baseFee: (json['base_fee_inr'] as num?)?.toDouble() ?? 1000.0,
      perKmRate: (json['per_km_rate_inr'] as num?)?.toDouble() ?? 28.0,
      capacityKg: (json['capacity_kg'] as num?)?.toDouble(),
    );
  }
}

class DashboardStatsModel {
  final double totalSales;
  final int activeOrders;
  final int totalListings;
  final String avgPriceImprovement;

  DashboardStatsModel({
    required this.totalSales,
    required this.activeOrders,
    required this.totalListings,
    required this.avgPriceImprovement,
  });

  factory DashboardStatsModel.fromJson(Map<String, dynamic> json) {
    return DashboardStatsModel(
      totalSales: (json['total_sales'] as num?)?.toDouble() ?? 15000.0,
      activeOrders: (json['active_orders'] as num?)?.toInt() ?? 4,
      totalListings: (json['total_listings'] as num?)?.toInt() ?? 12,
      avgPriceImprovement: json['avg_price_improvement']?.toString() ?? "+18.4%",
    );
  }
}

class TransactionItemModel {
  final String id;
  final String crop;
  final String quantity;
  final double amount;
  final String buyer;
  final String date;
  final String status;

  TransactionItemModel({
    required this.id,
    required this.crop,
    required this.quantity,
    required this.amount,
    required this.buyer,
    required this.date,
    required this.status,
  });

  factory TransactionItemModel.fromJson(Map<String, dynamic> json) {
    return TransactionItemModel(
      id: json['id'] ?? json['transaction_id'] ?? 'TXN',
      crop: json['crop'] ?? json['commodity'] ?? 'Produce Harvest',
      quantity: json['quantity']?.toString() ?? '—',
      amount: (json['price'] as num?)?.toDouble() ?? (json['amount'] as num?)?.toDouble() ?? 0.0,
      buyer: json['buyer'] ?? json['counterparty'] ?? 'Verified Buyer',
      date: json['date'] ?? json['created_at'] ?? '',
      status: json['status'] ?? 'COMPLETED',
    );
  }
}

class HistoryItemModel {
  final String time;
  final String eventType;
  final String details;
  final String status;
  final String module;

  HistoryItemModel({
    required this.time,
    required this.eventType,
    required this.details,
    required this.status,
    required this.module,
  });

  factory HistoryItemModel.fromJson(Map<String, dynamic> json) {
    return HistoryItemModel(
      time: json['time'] ?? json['timestamp'] ?? '',
      eventType: json['type'] ?? json['action'] ?? 'Activity',
      details: json['details'] ?? json['description'] ?? '—',
      status: json['status'] ?? 'COMPLETED',
      module: json['module'] ?? 'System',
    );
  }
}

class OndcItemModel {
  final String itemId;
  final String name;
  final String category;
  final double price;
  final String status;

  OndcItemModel({
    required this.itemId,
    required this.name,
    required this.category,
    required this.price,
    required this.status,
  });

  factory OndcItemModel.fromJson(Map<String, dynamic> json) {
    return OndcItemModel(
      itemId: json['item_id'] ?? json['id'] ?? 'ONDC-SKU',
      name: json['descriptor']?['name'] ?? json['name'] ?? 'Catalog Produce',
      category: json['category_id'] ?? 'Agriculture',
      price: (json['price']?['value'] as num?)?.toDouble() ?? (json['price'] as num?)?.toDouble() ?? 0.0,
      status: 'Beckn Discoverable',
    );
  }
}

class ForecastPointModel {
  final int dayIndex;
  final String date;
  final String dayName;
  final double predictedPrice;
  final double confidenceLow;
  final double confidenceHigh;
  final double recommendedListingPrice;

  ForecastPointModel({
    required this.dayIndex,
    required this.date,
    required this.dayName,
    required this.predictedPrice,
    required this.confidenceLow,
    required this.confidenceHigh,
    required this.recommendedListingPrice,
  });

  factory ForecastPointModel.fromJson(Map<String, dynamic> json) {
    return ForecastPointModel(
      dayIndex: json['day_index'] ?? 0,
      date: json['date'] ?? '',
      dayName: json['day_name'] ?? '',
      predictedPrice: (json['predicted_price'] as num?)?.toDouble() ?? 0.0,
      confidenceLow: (json['confidence_low'] as num?)?.toDouble() ?? 0.0,
      confidenceHigh: (json['confidence_high'] as num?)?.toDouble() ?? 0.0,
      recommendedListingPrice: (json['recommended_listing_price'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class ForecastResponseModel {
  final String status;
  final String commodity;
  final String market;
  final int days;
  final List<ForecastPointModel> forecast;
  final String modelVersion;

  ForecastResponseModel({
    required this.status,
    required this.commodity,
    required this.market,
    required this.days,
    required this.forecast,
    required this.modelVersion,
  });

  factory ForecastResponseModel.fromJson(Map<String, dynamic> json) {
    final list = json['forecast'] as List? ?? [];
    return ForecastResponseModel(
      status: json['status'] ?? 'success',
      commodity: json['commodity'] ?? '',
      market: json['market'] ?? '',
      days: json['days'] ?? 7,
      forecast: list.map((e) => ForecastPointModel.fromJson(e)).toList(),
      modelVersion: json['model_version'] ?? '',
    );
  }
}
