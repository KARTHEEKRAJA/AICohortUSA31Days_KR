# Structured Queries — Day 4

## Q1: What's the deductible on the Gold PPO plan?

```sql
SELECT plan_name, annual_deductible FROM plans WHERE plan_name = 'Gold PPO';
```

**Output:**

| plan_name   |   annual_deductible |
|:------------|--------------------:|
| Gold PPO    |                2000 |

## Q2: How many claims are pending for member M1001?

```sql
SELECT COUNT(*) AS pending_claims
FROM claims
WHERE member_id = 'M1001' AND status = 'Pending';
```

**Output:**

|   pending_claims |
|-----------------:|
|                1 |

## Q3: Which plans have a monthly premium under $400?

```sql
SELECT plan_name, monthly_premium FROM plans WHERE monthly_premium < 400;
```

**Output:**

| plan_name   |   monthly_premium |
|:------------|------------------:|
| Silver HMO  |               300 |
| Bronze HMO  |               150 |

## Q4: Show each claim with its plan details (JOIN)

```sql
SELECT c.claim_id, c.procedure, c.claim_amount, c.status,
       p.plan_name, p.coverage_type
FROM claims c
JOIN plans p ON c.plan_id = p.plan_id;
```

**Output:**

| claim_id   | procedure   |   claim_amount | status   | plan_name   | coverage_type   |
|:-----------|:------------|---------------:|:---------|:------------|:----------------|
| C1001      | X-ray       |            250 | Pending  | Gold PPO    | PPO             |
| C1002      | Surgery     |           1200 | Approved | Gold PPO    | PPO             |
| C1003      | X-ray       |            150 | Denied   | Silver HMO  | HMO             |
| C1004      | Surgery     |            900 | Approved | Silver HMO  | HMO             |
| C1005      | X-ray       |             50 | Pending  | Bronze HMO  | HMO             |

## Q5: Most claimed procedures by total amount (Top-N)

```sql
SELECT procedure, COUNT(*) AS num_claims, SUM(claim_amount) AS total_amount
FROM claims
GROUP BY procedure
ORDER BY total_amount DESC
LIMIT 3;
```

**Output:**

| procedure   |   num_claims |   total_amount |
|:------------|-------------:|---------------:|
| Surgery     |            2 |           2100 |
| X-ray       |            3 |            450 |

