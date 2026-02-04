package com.smartcartai.backend.repository;

import com.smartcartai.backend.entity.Demand;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface DemandRepository extends JpaRepository<Demand, Integer> {

    List<Demand> findAll();
}
