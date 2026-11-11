-- PostgreSQL Row-Level Security (Spec Kap. 6, ADR-03).
-- Ausfuehren als Owner nach dem Anlegen der Tabellen. Die App verbindet sich als
-- application_user OHNE BYPASSRLS; die API setzt app.current_tenant_id transaktionslokal.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['soldaten','abwesenheiten','roster_jobs','schichten','trade_requests',
                           'audit_log','datev_outbox','deletion_registry']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
    EXECUTE format($p$CREATE POLICY tenant_isolation ON %I FOR ALL TO application_user
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)$p$, t);
  END LOOP;
END $$;

-- Audit-Log ist append-only
REVOKE UPDATE, DELETE ON audit_log FROM application_user;
