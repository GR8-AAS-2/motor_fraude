-- Tabla propia del motor de fraude: guarda el hash de los datos de cada
-- póliza registrada. Vive en el mismo proyecto Supabase que poliza_seguridad,
-- pero es una tabla independiente (no se mezcla con audit_logs).
-- Ejecutar en el SQL Editor de Supabase.

create extension if not exists "pgcrypto";

create table if not exists public.poliza_hashes (
    id             uuid primary key default gen_random_uuid(),
    numero_poliza  text not null unique,
    hash           text not null,
    fecha_creacion timestamptz not null default now()
);

comment on table public.poliza_hashes is 'Hashes de integridad de datos de pólizas, calculados por el motor de fraude.';
comment on column public.poliza_hashes.id is 'Identificador único autogenerado (PK).';
comment on column public.poliza_hashes.numero_poliza is 'Número de póliza (único); clave de búsqueda del hash.';
comment on column public.poliza_hashes.hash is 'SHA-256 canónico calculado sobre los 8 campos de la póliza.';
comment on column public.poliza_hashes.fecha_creacion is 'Fecha en que se registró el hash.';

create index if not exists idx_poliza_hashes_numero_poliza on public.poliza_hashes (numero_poliza);

-- RLS activado sin políticas públicas: solo la service_role (que bypassa RLS)
-- puede leer/escribir, igual que en audit_logs.
alter table public.poliza_hashes enable row level security;
