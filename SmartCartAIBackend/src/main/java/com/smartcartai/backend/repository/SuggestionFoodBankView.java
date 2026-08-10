package com.smartcartai.backend.repository;

import java.math.BigDecimal;

/** Native-query projection: suggestion_food_bank row joined with its food_banks name/address. */
public interface SuggestionFoodBankView {
    Integer getId();
    Integer getSuggestionId();
    Integer getFoodBankId();
    Integer getRank();
    BigDecimal getDistanceMi();
    String getName();
    String getAddress();
}
