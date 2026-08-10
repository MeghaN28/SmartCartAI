package com.smartcartai.backend.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import com.smartcartai.backend.entity.SuggestionFoodBank;

public interface SuggestionFoodBankRepository extends JpaRepository<SuggestionFoodBank, Integer> {

    @Query(value = "SELECT sfb.id AS id, sfb.suggestion_id AS suggestionId, sfb.food_bank_id AS foodBankId, "
            + "sfb.rank AS rank, sfb.distance_mi AS distanceMi, fb.name AS name, fb.address AS address "
            + "FROM suggestion_food_bank sfb "
            + "JOIN food_banks fb ON fb.food_bank_id = sfb.food_bank_id "
            + "WHERE sfb.suggestion_id IN (:suggestionIds) "
            + "ORDER BY sfb.suggestion_id ASC, sfb.rank ASC",
            nativeQuery = true)
    List<SuggestionFoodBankView> findWithFoodBankBySuggestionIdIn(@Param("suggestionIds") List<Integer> suggestionIds);
}
