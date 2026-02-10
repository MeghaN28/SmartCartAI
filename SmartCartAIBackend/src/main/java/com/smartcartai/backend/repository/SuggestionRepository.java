package com.smartcartai.backend.repository;

import com.smartcartai.backend.entity.Suggestion;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface SuggestionRepository extends JpaRepository<Suggestion, Integer> {
    List<Suggestion> findAllByOrderByCreatedAtDesc();
    List<Suggestion> findByStatusOrderByCreatedAtDesc(String status);
    List<Suggestion> findByInventoryIdOrderByCreatedAtDesc(String inventoryId);
}
