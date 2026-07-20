create extension if not exists pgcrypto;

create table if not exists backup_runs (
    id uuid primary key default gen_random_uuid(),
    snapshot_date date not null unique,
    source text not null default 'discord-bot',
    created_at timestamptz not null default now()
);

create table if not exists backup_village_snapshots (
    backup_run_id uuid not null references backup_runs(id) on delete cascade,
    village text not null,
    points_json jsonb not null default '[]'::jsonb,
    point_count integer not null default 0 check (point_count >= 0),
    created_at timestamptz not null default now(),
    primary key (backup_run_id, village)
);

create index if not exists backup_runs_snapshot_date_idx
    on backup_runs (snapshot_date);

create index if not exists backup_village_snapshots_backup_run_id_idx
    on backup_village_snapshots (backup_run_id);

create index if not exists backup_village_snapshots_village_idx
    on backup_village_snapshots (village);
