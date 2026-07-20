-- 1) Show imported snapshot dates and village counts
select
    br.snapshot_date,
    count(bvs.village) as villages,
    coalesce(sum(bvs.point_count), 0) as total_points
from backup_runs br
left join backup_village_snapshots bvs
    on bvs.backup_run_id = br.id
group by br.snapshot_date
order by br.snapshot_date;

-- 2) Check that every row has point_count matching JSON array length
select
    br.snapshot_date,
    bvs.village,
    bvs.point_count,
    jsonb_array_length(bvs.points_json) as json_len
from backup_village_snapshots bvs
join backup_runs br
    on br.id = bvs.backup_run_id
where bvs.point_count <> jsonb_array_length(bvs.points_json)
order by br.snapshot_date, bvs.village;

-- 3) Verify anonymization: should return 0 rows
select
    br.snapshot_date,
    bvs.village,
    point
from backup_village_snapshots bvs
join backup_runs br
    on br.id = bvs.backup_run_id
cross join lateral jsonb_array_elements(bvs.points_json) as point
where point ? 'user_id'
order by br.snapshot_date, bvs.village;

-- 4) Sample view for one snapshot date (replace date if needed)
-- select
--     bvs.village,
--     bvs.point_count,
--     bvs.points_json
-- from backup_village_snapshots bvs
-- join backup_runs br
--     on br.id = bvs.backup_run_id
-- where br.snapshot_date = date '2026-07-19'
-- order by bvs.village;
