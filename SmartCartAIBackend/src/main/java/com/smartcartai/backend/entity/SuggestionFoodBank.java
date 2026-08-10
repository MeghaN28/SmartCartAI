package com.smartcartai.backend.entity;

import java.math.BigDecimal;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

/** Normalized nearest-food-bank match for a suggestion; supersedes Suggestion.donationInfo. */
@Entity
@Table(name = "suggestion_food_bank")
@Getter
@Setter
public class SuggestionFoodBank {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Integer id;

    @Column(name = "suggestion_id")
    private Integer suggestionId;

    @Column(name = "food_bank_id")
    private Integer foodBankId;

    @Column(name = "rank")
    private Integer rank;

    @Column(name = "distance_mi", precision = 8, scale = 2)
    private BigDecimal distanceMi;

    // Populated by the repository join at read time; not a mapped column.
    @jakarta.persistence.Transient
    private String name;

    @jakarta.persistence.Transient
    private String address;
}
