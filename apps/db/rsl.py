"""Row Level Security policies."""
from sqlalchemy import text

RSL_TABLES = {
    "tenants": "SELECT true FROM tenant_members WHERE tenant_members.tenant_id = current_setting('app.current_tenant_id')::uuid AND tenant_members.user_id = current_setting('app.current_user_id')::uuid",
    "soldaten": "SELECT true FROM tenant_members WHERE tenant_members.tenant_id = current_setting('app.current_tenant_id')::uuid AND (tenant_members.role IN ('admin','planer','soldat') OR tenant_members.user_id = current_setting('app.current_user_id')::uuid)",
    "schichten": "SELECT true FROM tenant_members WHERE tenant_members.tenant_id = current_setting('app.current_tenant_id')::uuid AND (tenant_members.role IN ('admin','planer','soldat') OR tenant_members.user_id = current_setting('app.current_user_id')::uuid)",
    "dienstplaene": "SELECT true FROM tenant_members WHERE tenant_members.tenant_id = current_setting('app.current_tenant_id')::uuid AND (tenant_members.role IN ('admin','planer','soldat','audit') OR tenant_members.user_id = current_setting('app.current_user_id')::uuid)",
    "abwesenheiten": "SELECT true FROM tenant_members WHERE tenant_members.tenant_id = current_setting('app.current_tenant_id')::uuid AND (tenant_members.role IN ('admin','planer','truppenarzt','soldat') OR tenant_members.user_id = current_setting('app.current_user_id')::uuid)",
}
