package com.smartcartai.backend.repository;

import com.smartcartai.backend.entity.Consumption;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ConsumptionRepository extends JpaRepository<Consumption, String> {

    List<Consumption> findAll();
}
