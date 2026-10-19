-- Run against an ISOLATED, restored full legacy backup before planning upgrade.
-- Counts only: no personal records or hashes are exported. No data is changed.
-- This script expects the supplied legacy table names, including auth_user.
\set ON_ERROR_STOP on
BEGIN TRANSACTION READ ONLY;

SELECT app, name, applied FROM public.django_migrations ORDER BY app, name;

SELECT 'users_without_email' AS finding, count(*) AS rows FROM public.users
 WHERE email IS NULL OR btrim(email) = ''
UNION ALL
SELECT 'users_email_over_254', count(*) FROM public.users WHERE length(email) > 254
UNION ALL
SELECT 'users_nullable_flags', count(*) FROM public.users
 WHERE is_active IS NULL OR is_staff IS NULL OR is_superuser IS NULL
UNION ALL
SELECT 'users_without_role', count(*) FROM public.users WHERE role_id IS NULL
UNION ALL
SELECT 'directors_without_institution', count(*) FROM public.users u
 JOIN public.roles r ON r.id=u.role_id
 WHERE r.code='DIRECTOR' AND u.institution_id IS NULL
UNION ALL
SELECT 'unknown_or_missing_role_code', count(*) FROM public.roles
 WHERE code IS NULL OR code NOT IN ('ADMIN', 'COMMITTEE', 'DIRECTOR')
UNION ALL
SELECT 'duplicate_normalized_email_groups', count(*) FROM (
 SELECT lower(btrim(email)) FROM public.users WHERE email IS NOT NULL AND btrim(email)<>''
 GROUP BY lower(btrim(email)) HAVING count(*)>1
) duplicates
UNION ALL
SELECT 'institutions_missing_required_values', count(*) FROM public.institutions
 WHERE short_name IS NULL OR address IS NULL OR created_at IS NULL OR updated_at IS NULL
UNION ALL
SELECT 'users_missing_timestamps', count(*) FROM public.users
 WHERE created_at IS NULL OR updated_at IS NULL
UNION ALL
SELECT 'users_password_hash_over_255', count(*) FROM public.users WHERE length(password_hash)>255
UNION ALL
SELECT 'orders_missing_timestamps', count(*) FROM public.orders
 WHERE created_at IS NULL OR updated_at IS NULL
UNION ALL
SELECT 'orders_invalid_dates', count(*) FROM public.orders WHERE deadline_date < issue_date
UNION ALL
SELECT 'orders_unknown_status', count(*) FROM public.orders
 WHERE status::text NOT IN ('NEW','IN_PROGRESS','EXPIRING','COMPLETED','OVERDUE')
UNION ALL
SELECT 'completed_orders_without_any_file', count(*) FROM public.orders o
 WHERE status::text='COMPLETED' AND NOT EXISTS (SELECT 1 FROM public.files f WHERE f.order_id=o.id)
UNION ALL
SELECT 'files_missing_uploaded_at', count(*) FROM public.files WHERE uploaded_at IS NULL;

-- Overlapping IDs do NOT establish that the people are the same.
SELECT count(*) AS historical_admin_logs,
 count(*) FILTER (WHERE u.id IS NULL) AS logs_without_same_id_in_users,
 count(*) FILTER (WHERE u.id IS NOT NULL) AS overlapping_ids_requiring_identity_review
 FROM public.django_admin_log l LEFT JOIN public.users u ON u.id=l.user_id;

SELECT 'auth_user' AS table_name, count(*) AS rows FROM public.auth_user
UNION ALL SELECT 'institutions_institution',count(*) FROM public.institutions_institution
UNION ALL SELECT 'institutions_employee',count(*) FROM public.institutions_employee
UNION ALL SELECT 'prescriptions_order',count(*) FROM public.prescriptions_order
UNION ALL SELECT 'prescriptions_violation',count(*) FROM public.prescriptions_violation
UNION ALL SELECT 'prescriptions_authority',count(*) FROM public.prescriptions_authority
UNION ALL SELECT 'prescriptions_status',count(*) FROM public.prescriptions_status
UNION ALL SELECT 'audit_logs',count(*) FROM public.audit_logs
UNION ALL SELECT 'funding_requests',count(*) FROM public.funding_requests;

SELECT t.relname AS table_name, c.conname, pg_get_constraintdef(c.oid) AS definition
 FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
 JOIN pg_namespace n ON n.oid=t.relnamespace
 WHERE n.nspname='public' AND c.contype='f' AND c.confdeltype='c'
 ORDER BY t.relname,c.conname;

COMMIT;
