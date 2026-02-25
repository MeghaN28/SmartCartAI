package com.smartcartai.backend.controller;

import com.smartcartai.backend.entity.Sales;
import com.smartcartai.backend.repository.SalesRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;

@RestController
@RequestMapping("/api/dashboard")
@Tag(name = "Dashboard", description = "Dashboard aggregates and chart-ready responses")
public class DashboardController {

    private static final DateTimeFormatter LABEL_FORMAT = DateTimeFormatter.ofPattern("MM/dd");

    private final SalesRepository salesRepository;

    public DashboardController(SalesRepository salesRepository) {
        this.salesRepository = salesRepository;
    }

    @GetMapping("/overview")
    @Operation(summary = "Get dashboard overview including 7-day sales chart")
    public ResponseEntity<Map<String, Object>> getOverview() {
        List<Sales> sales = salesRepository.findAll();
        LocalDate latestDate = sales.stream()
                .map(Sales::getPurchaseDate)
                .filter(Objects::nonNull)
                .max(Comparator.naturalOrder())
                .orElse(null);

        Map<String, Object> response = new HashMap<>();

        if (latestDate == null) {
            response.put("salesChart", emptySalesChart(LocalDate.now()));
            response.put("totalRevenue7d", 0.0);
            response.put("totalUnits7d", 0);
            return ResponseEntity.ok(response);
        }

        LocalDate startDate = latestDate.minusDays(6);
        Map<LocalDate, SalesAggregate> dailyAgg = new TreeMap<>();

        for (LocalDate d = startDate; !d.isAfter(latestDate); d = d.plusDays(1)) {
            dailyAgg.put(d, new SalesAggregate());
        }

        for (Sales sale : sales) {
            if (sale.getPurchaseDate() == null || sale.getPurchaseDate().isBefore(startDate) || sale.getPurchaseDate().isAfter(latestDate)) {
                continue;
            }
            SalesAggregate aggregate = dailyAgg.get(sale.getPurchaseDate());
            if (aggregate == null) {
                continue;
            }
            aggregate.quantity += sale.getQuantity() != null ? sale.getQuantity() : 0;
            aggregate.revenue = aggregate.revenue.add(sale.getTotalCost() != null ? sale.getTotalCost() : BigDecimal.ZERO);
        }

        List<String> labels = new ArrayList<>();
        List<Integer> quantity = new ArrayList<>();
        List<Double> revenue = new ArrayList<>();

        int totalUnits7d = 0;
        BigDecimal totalRevenue7d = BigDecimal.ZERO;

        for (Map.Entry<LocalDate, SalesAggregate> entry : dailyAgg.entrySet()) {
            labels.add(entry.getKey().format(LABEL_FORMAT));
            quantity.add(entry.getValue().quantity);
            double dayRevenue = entry.getValue().revenue.doubleValue();
            revenue.add(dayRevenue);
            totalUnits7d += entry.getValue().quantity;
            totalRevenue7d = totalRevenue7d.add(entry.getValue().revenue);
        }

        Map<String, Object> salesChart = new HashMap<>();
        salesChart.put("labels", labels);
        salesChart.put("quantity", quantity);
        salesChart.put("revenue", revenue);

        response.put("salesChart", salesChart);
        response.put("totalRevenue7d", totalRevenue7d.doubleValue());
        response.put("totalUnits7d", totalUnits7d);

        return ResponseEntity.ok(response);
    }

    private Map<String, Object> emptySalesChart(LocalDate endDate) {
        List<String> labels = new ArrayList<>();
        List<Integer> quantity = new ArrayList<>();
        List<Double> revenue = new ArrayList<>();

        LocalDate startDate = endDate.minusDays(6);
        for (LocalDate d = startDate; !d.isAfter(endDate); d = d.plusDays(1)) {
            labels.add(d.format(LABEL_FORMAT));
            quantity.add(0);
            revenue.add(0.0);
        }

        Map<String, Object> salesChart = new HashMap<>();
        salesChart.put("labels", labels);
        salesChart.put("quantity", quantity);
        salesChart.put("revenue", revenue);
        return salesChart;
    }

    private static class SalesAggregate {
        int quantity = 0;
        BigDecimal revenue = BigDecimal.ZERO;
    }
}
