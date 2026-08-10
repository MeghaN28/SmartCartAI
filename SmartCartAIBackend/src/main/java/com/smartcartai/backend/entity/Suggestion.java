package com.smartcartai.backend.entity;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Transient;
import lombok.Getter;
import lombok.Setter;

@Entity
@Table(name = "suggestions")
@Getter
@Setter
public class Suggestion {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "suggestion_id")
    private Integer suggestionId;

    @Column(name = "inventory_id", length = 32)
    private String inventoryId;

    @Column(name = "item_name", columnDefinition = "TEXT")
    private String itemName;

    @Column(name = "user_query", columnDefinition = "TEXT")
    private String userQuery;

    @Column(name = "action", length = 50)
    private String action;

    @Column(name = "priority", length = 20)
    private String priority;

    @Column(name = "reasoning", columnDefinition = "TEXT")
    private String reasoning;

    @Column(name = "expected_outcome", columnDefinition = "TEXT")
    private String expectedOutcome;

    @Column(name = "bundle_suggestion", columnDefinition = "TEXT")
    private String bundleSuggestion;

    @Column(name = "risk_level", length = 20)
    private String riskLevel;

    @Column(name = "risk_score")
    private Integer riskScore;

    @Column(name = "is_feasible")
    private Boolean isFeasible;

    @Column(name = "estimated_cost", precision = 12, scale = 2)
    private BigDecimal estimatedCost;

    @Column(name = "within_budget")
    private Boolean withinBudget;

    @Column(name = "explanation", columnDefinition = "TEXT")
    private String explanation;

    @Column(name = "current_stock")
    private Integer currentStock;

    @Column(name = "min_stock")
    private Integer minStock;

    @Column(name = "forecasted_demand", precision = 10, scale = 2)
    private BigDecimal forecastedDemand;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "status", length = 20)
    private String status;

    /**
     * Legacy JSON snapshot of nearest food bank(s), kept only for suggestions written
     * before the suggestion_food_bank table existed. New rows populate foodBanks instead.
     */
    @Column(name = "donation_info", columnDefinition = "TEXT")
    private String donationInfo;

    /** Normalized nearest-food-bank matches, joined in from suggestion_food_bank. Not a mapped column. */
    @Transient
    private List<SuggestionFoodBank> foodBanks;
}
