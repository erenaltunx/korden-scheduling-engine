-- Reproducible relational reporting examples for the OPTERA BI bridge.
-- Always filter or group by experiment_id AND time_unit; never sum minutes + hours.

-- 1. Scenario KPI comparison: what changed from baseline to optimized schedule?
SELECT experiment_id, scenario, industry, time_unit,
       MAX(CASE WHEN plan = 'baseline' THEN weighted_tardiness END) AS baseline_weighted_tardiness,
       MAX(CASE WHEN plan = 'optimized' THEN weighted_tardiness END) AS optimized_weighted_tardiness,
       MAX(CASE WHEN plan = 'baseline' THEN late_orders END) AS baseline_late_orders,
       MAX(CASE WHEN plan = 'optimized' THEN late_orders END) AS optimized_late_orders
FROM run_summary
GROUP BY experiment_id, scenario, industry, time_unit;

-- 2. Priority-adjusted tardiness at the work-order level.
SELECT experiment_id, plan, order_id, due, completion, tardiness, priority,
       weighted_tardiness, late, time_unit
FROM order_kpis
WHERE tardiness > 0
ORDER BY experiment_id, plan, weighted_tardiness DESC;

-- 3. Resource utilization proxy: assigned processing time / total scheduled horizon.
-- Not an actual shift/capacity utilization rate until calendars are modeled.
SELECT b.experiment_id, b.plan, b.resource_id, b.time_unit,
       SUM(b.duration) AS occupied_time,
       MAX(r.makespan) AS schedule_horizon,
       ROUND(100.0 * SUM(b.duration) / NULLIF(MAX(r.makespan),0),2) AS horizon_occupation_pct
FROM resource_bookings b
JOIN run_summary r ON b.experiment_id = r.experiment_id AND b.plan = r.plan
GROUP BY b.experiment_id, b.plan, b.resource_id, b.time_unit;

-- 4. Independently reconcile weighted lateness in the result and the work-order facts.
SELECT r.experiment_id, r.plan,
       r.weighted_tardiness AS reported,
       SUM(k.weighted_tardiness) AS recomputed,
       r.weighted_tardiness - SUM(k.weighted_tardiness) AS reconciliation_difference
FROM run_summary r
JOIN order_kpis k ON r.experiment_id = k.experiment_id AND r.plan = k.plan
GROUP BY r.experiment_id, r.plan;
