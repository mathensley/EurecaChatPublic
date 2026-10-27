\set ON_ERROR_STOP on

-- Este script é executado por um serviço one-shot do Compose. Ele pode ser
-- reaplicado tanto em instalações novas quanto em volumes PostgreSQL antigos.
SELECT 'CREATE ROLE eureca_monitor'
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_roles
    WHERE rolname = 'eureca_monitor'
) \gexec

ALTER ROLE eureca_monitor WITH
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    INHERIT
    NOREPLICATION
    NOBYPASSRLS
    CONNECTION LIMIT 5
    PASSWORD :'monitor_password';

GRANT pg_monitor TO eureca_monitor;
GRANT CONNECT ON DATABASE :"monitor_database" TO eureca_monitor;

-- Defesa em profundidade: o exporter só precisa das visões estatísticas.
ALTER ROLE eureca_monitor SET default_transaction_read_only = on;
ALTER ROLE eureca_monitor SET statement_timeout = '10s';
ALTER ROLE eureca_monitor SET lock_timeout = '2s';
ALTER ROLE eureca_monitor SET idle_in_transaction_session_timeout = '15s';
ALTER ROLE eureca_monitor SET search_path = pg_catalog;

-- TEMPORARY é concedido a PUBLIC por padrão e privilégios do PostgreSQL são
-- aditivos. Retirá-lo de PUBLIC e devolvê-lo ao dono impede que o monitor crie
-- tabelas temporárias sem afetar a aplicação.
REVOKE TEMPORARY ON DATABASE :"monitor_database" FROM PUBLIC;
GRANT TEMPORARY ON DATABASE :"monitor_database" TO :"application_user";
REVOKE CREATE, TEMPORARY ON DATABASE :"monitor_database" FROM eureca_monitor;
REVOKE CREATE ON SCHEMA public FROM eureca_monitor;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM eureca_monitor;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM eureca_monitor;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM eureca_monitor;
