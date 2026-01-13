from sqlalchemy import text
from shared.db.session import get_db

def create_materialized_views():
    sql = """
    -- Job Function Stats
    DROP MATERIALIZED VIEW IF EXISTS mv_job_function_stats;
    CREATE MATERIALIZED VIEW mv_job_function_stats AS
    SELECT 
        job_function as name, 
        COUNT(*) as count
    FROM job
    WHERE job_function IS NOT NULL 
      AND job_function NOT IN ('unknown', 'other', 'active')
    GROUP BY job_function
    ORDER BY count DESC;
    CREATE UNIQUE INDEX ON mv_job_function_stats (name);

    -- Seniority Stats
    DROP MATERIALIZED VIEW IF EXISTS mv_seniority_stats;
    CREATE MATERIALIZED VIEW mv_seniority_stats AS
    SELECT 
        seniority_level as name, 
        COUNT(*) as count
    FROM job
    WHERE seniority_level IS NOT NULL 
      AND seniority_level != 'unknown'
    GROUP BY seniority_level
    ORDER BY count DESC;
    CREATE UNIQUE INDEX ON mv_seniority_stats (name);

    -- Remote Type Stats
    DROP MATERIALIZED VIEW IF EXISTS mv_remote_stats;
    CREATE MATERIALIZED VIEW mv_remote_stats AS
    SELECT 
        remote_type as name, 
        COUNT(*) as count
    FROM job
    WHERE remote_type IS NOT NULL 
      AND remote_type != 'unknown'
    GROUP BY remote_type
    ORDER BY count DESC;
    CREATE UNIQUE INDEX ON mv_remote_stats (name);

    -- Salary Stats (Median and Distribution)
    DROP MATERIALIZED VIEW IF EXISTS mv_salary_stats;
    CREATE MATERIALIZED VIEW mv_salary_stats AS
    WITH job_salaries AS (
        SELECT 
            (COALESCE(salary_min_usd, salary_max_usd) + COALESCE(salary_max_usd, salary_min_usd)) / 2.0 as avg_salary
        FROM job
        WHERE salary_min_usd IS NOT NULL OR salary_max_usd IS NOT NULL
    )
    SELECT 
        percentile_cont(0.5) WITHIN GROUP (ORDER BY avg_salary) as median_salary,
        COUNT(*) as total_with_salary
    FROM job_salaries;

    -- Salary Bucket Stats
    DROP MATERIALIZED VIEW IF EXISTS mv_salary_bucket_stats;
    CREATE MATERIALIZED VIEW mv_salary_bucket_stats AS
    WITH bucketed_salaries AS (
        SELECT 
            CASE 
                WHEN (COALESCE(salary_min_usd, salary_max_usd) + COALESCE(salary_max_usd, salary_min_usd)) / 2.0 < 100000 THEN 'Under $100k'
                WHEN (COALESCE(salary_min_usd, salary_max_usd) + COALESCE(salary_max_usd, salary_min_usd)) / 2.0 < 150000 THEN '$100k-$150k'
                WHEN (COALESCE(salary_min_usd, salary_max_usd) + COALESCE(salary_max_usd, salary_min_usd)) / 2.0 < 200000 THEN '$150k-$200k'
                WHEN (COALESCE(salary_min_usd, salary_max_usd) + COALESCE(salary_max_usd, salary_min_usd)) / 2.0 < 250000 THEN '$200k-$250k'
                ELSE '$250k+'
            END as bucket,
            (COALESCE(salary_min_usd, salary_max_usd) + COALESCE(salary_max_usd, salary_min_usd)) / 2.0 as avg_val
        FROM job
        WHERE salary_min_usd IS NOT NULL OR salary_max_usd IS NOT NULL
    )
    SELECT 
        bucket as name,
        COUNT(*) as count,
        CASE 
            WHEN bucket = 'Under $100k' THEN 1
            WHEN bucket = '$100k-$150k' THEN 2
            WHEN bucket = '$150k-$200k' THEN 3
            WHEN bucket = '$200k-$250k' THEN 4
            ELSE 5
        END as sort_order
    FROM bucketed_salaries
    GROUP BY bucket
    ORDER BY sort_order ASC;
    CREATE UNIQUE INDEX ON mv_salary_bucket_stats (name);

    -- Location Stats (City, State)
    DROP MATERIALIZED VIEW IF EXISTS mv_location_stats;
    CREATE MATERIALIZED VIEW mv_location_stats AS
    SELECT 
        location_city || ', ' || location_state as name,
        location_city,
        location_state,
        COUNT(*) as count
    FROM job
    WHERE location_city IS NOT NULL 
      AND location_state IS NOT NULL
      AND location_city != 'unknown'
      AND location_state != 'unknown'
    GROUP BY location_city, location_state
    ORDER BY count DESC;
    CREATE UNIQUE INDEX ON mv_location_stats (name);
    """
    
    with get_db() as db:
        print("Creating materialized views...")
        db.execute(text(sql))
        db.commit()
        print("Successfully created materialized views.")

if __name__ == "__main__":
    create_materialized_views()
