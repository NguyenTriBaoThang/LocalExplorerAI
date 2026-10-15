-- Local Explorer AI - PostgreSQL upgrade script: 0012_slot_timestamps_utc -> 0017_merge_main_and_portal
--
-- For a database deployed from `main` before PR #71 (alembic revision 0012_slot_timestamps_utc).
-- Generated with: alembic upgrade 0012_slot_timestamps_utc:head --sql   (apps/api, PostgreSQL)
-- Verified on postgis/postgis:16-3.4: applies cleanly on a DB at 0012 and ends at 0017_merge_main_and_portal.
-- Prefer `alembic upgrade head` where you can run it; use this script when changes must go through SQL review.
-- Back up first. The RBAC seed rows carry the generation timestamp as created_at.
--
-- 0011_auth_foundation   users.token_version/email_verified_at/mfa_enabled (existing users are marked verified);
--                        new tables: auth_sessions, auth_tokens, user_mfa, mfa_recovery_codes, roles, permissions,
--                        role_permissions, service_accounts, auth_events
-- 0012_rbac_seed         default roles, permission catalogue and role grants
-- 0013_account_recovery  itinerary_claim_tokens; permission account:sessions
-- 0014_mfa               user_mfa.last_used_step; auth_tokens purpose 'mfa_login'; permission account:mfa
-- 0015_partner_onboarding providers: business/application/review columns + ix_providers_verification_status
--                        (existing 'pending' providers become 'verified')
-- 0016_portal_platform   POI visitor info, site content, page views, experience reviews
-- 0017_merge_main_and_portal  merge point of the two migration lines (no schema change)

BEGIN;


-- Running upgrade 0010_place_import_staging -> 0011_auth_foundation
ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT '0' NOT NULL;
ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN DEFAULT false NOT NULL;
UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL;
CREATE TABLE auth_sessions (
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    family_id VARCHAR(36) NOT NULL, 
    refresh_hash VARCHAR(64) NOT NULL, 
    issued_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    absolute_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    rotated_at TIMESTAMP WITH TIME ZONE, 
    replaced_by VARCHAR(36), 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    revoked_reason VARCHAR(40), 
    last_used_at TIMESTAMP WITH TIME ZONE, 
    ip VARCHAR(64), 
    user_agent VARCHAR(255), 
    amr JSON DEFAULT '[]' NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_auth_sessions_user_id ON auth_sessions (user_id);
CREATE INDEX ix_auth_sessions_family_id ON auth_sessions (family_id);
CREATE UNIQUE INDEX ix_auth_sessions_refresh_hash ON auth_sessions (refresh_hash);
CREATE INDEX ix_auth_sessions_user_active ON auth_sessions (user_id, revoked_at);
CREATE TABLE auth_tokens (
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    purpose VARCHAR(32) NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    used_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_auth_tokens_purpose CHECK (purpose IN ('reset_password', 'verify_email')), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_auth_tokens_user_id ON auth_tokens (user_id);
CREATE UNIQUE INDEX ix_auth_tokens_token_hash ON auth_tokens (token_hash);
CREATE TABLE user_mfa (
    user_id VARCHAR(36) NOT NULL, 
    secret_encrypted TEXT NOT NULL, 
    confirmed_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (user_id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE TABLE mfa_recovery_codes (
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    code_hash VARCHAR(64) NOT NULL, 
    used_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_mfa_recovery_codes_user_id ON mfa_recovery_codes (user_id);
CREATE TABLE roles (
    name VARCHAR(40) NOT NULL, 
    description VARCHAR(255) DEFAULT '' NOT NULL, 
    is_system BOOLEAN DEFAULT false NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (name)
);
CREATE TABLE permissions (
    name VARCHAR(80) NOT NULL, 
    description VARCHAR(255) DEFAULT '' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (name)
);
CREATE TABLE role_permissions (
    role_name VARCHAR(40) NOT NULL, 
    permission_name VARCHAR(80) NOT NULL, 
    PRIMARY KEY (role_name, permission_name), 
    FOREIGN KEY(role_name) REFERENCES roles (name) ON DELETE CASCADE, 
    FOREIGN KEY(permission_name) REFERENCES permissions (name) ON DELETE CASCADE
);
CREATE TABLE service_accounts (
    id VARCHAR(36) NOT NULL, 
    name VARCHAR(80) NOT NULL, 
    key_id VARCHAR(32) NOT NULL, 
    key_hash VARCHAR(64) NOT NULL, 
    permissions JSON DEFAULT '[]' NOT NULL, 
    created_by VARCHAR(36), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    last_used_at TIMESTAMP WITH TIME ZONE, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_service_accounts_name UNIQUE (name), 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX ix_service_accounts_key_id ON service_accounts (key_id);
CREATE TABLE auth_events (
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36), 
    session_id VARCHAR(36), 
    event_type VARCHAR(40) NOT NULL, 
    outcome VARCHAR(16) DEFAULT 'success' NOT NULL, 
    ip VARCHAR(64), 
    user_agent VARCHAR(255), 
    detail JSON DEFAULT '{}' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_auth_events_user_id ON auth_events (user_id);
CREATE INDEX ix_auth_events_event_type ON auth_events (event_type);
CREATE INDEX ix_auth_events_created_at ON auth_events (created_at);
INSERT INTO alembic_version (version_num) VALUES ('0011_auth_foundation') RETURNING alembic_version.version_num;
-- Running upgrade 0011_auth_foundation -> 0012_rbac_seed
INSERT INTO roles (name, description, is_system, created_at) VALUES ('admin', 'Platform administrator', true, '2026-10-15 16:06:05.726997+00:00');
INSERT INTO roles (name, description, is_system, created_at) VALUES ('provider', 'Experience provider', true, '2026-10-15 16:06:05.726997+00:00');
INSERT INTO roles (name, description, is_system, created_at) VALUES ('traveler', 'Signed-in visitor', true, '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('account:password', 'Change own password', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('account:read', 'Read own profile', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('account:update', 'Update own profile', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:ai_tools', 'Run administrator AI tools', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:audit', 'Read the system audit log', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:bot', 'Manage the chat bot', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:dashboard', 'Read the admin dashboard', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:duplicates', 'Detect and merge duplicate POIs', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:integrations', 'Manage third-party integration settings', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:models_3d', 'Save 3D model calibration', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:moderation', 'Review the moderation queue', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:place_import', 'Review and promote imported places', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:providers', 'List and create providers', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:rbac', 'View and edit the role-permission matrix', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:service_accounts', 'Manage service accounts', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:system', 'Manage system settings and metrics', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:users', 'List and update users', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('booking:cancel', 'Cancel own unpaid booking', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('booking:checkout', 'Start payment for own booking', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('booking:create', 'Create a seat hold', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('booking:history', 'Read a booking''s status history (participants only)', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('booking:read', 'List own bookings', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('chat:use', 'Use the AI concierge', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('itinerary:compare', 'Compare two own itineraries', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('itinerary:feedback', 'Submit and read feedback', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('itinerary:list', 'List own itineraries', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('itinerary:plan', 'Generate an itinerary', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('itinerary:read', 'Open an itinerary (ownership is enforced per object)', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('itinerary:share', 'Create or revoke a share link', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('itinerary:versions', 'Read itinerary version history', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('notification:read', 'Read own slot-cancellation notices', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('ops:read', 'Read operational status (also grantable to service accounts)', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('provider:audit', 'Read the provider audit log', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('provider:booking_decide', 'Accept or reject bookings and cancellations', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('provider:booking_read', 'Read booking requests addressed to the provider', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('provider:evidence', 'Submit and read evidence', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('provider:experience', 'Manage own experiences', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('provider:poi', 'Manage own POIs', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('provider:profile', 'Read own provider profile', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('provider:slot', 'Manage own slots', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('provider:slot_assist', 'Use the slot assistant', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('replan:accept', 'Accept a replanning proposal', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('replan:advise', 'Ask for replanning advice', '2026-10-15 16:06:05.726997+00:00');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'account:password');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'account:read');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'account:update');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:ai_tools');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:audit');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:bot');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:dashboard');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:duplicates');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:integrations');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:models_3d');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:moderation');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:place_import');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:providers');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:rbac');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:service_accounts');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:system');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:users');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'booking:history');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'booking:read');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'ops:read');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'account:password');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'account:read');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'account:update');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'booking:history');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'booking:read');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'provider:audit');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'provider:booking_decide');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'provider:booking_read');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'provider:evidence');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'provider:experience');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'provider:poi');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'provider:profile');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'provider:slot');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'provider:slot_assist');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'account:password');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'account:read');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'account:update');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'booking:cancel');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'booking:checkout');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'booking:create');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'booking:history');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'booking:read');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'chat:use');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'itinerary:compare');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'itinerary:feedback');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'itinerary:list');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'itinerary:plan');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'itinerary:read');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'itinerary:share');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'itinerary:versions');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'notification:read');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'replan:accept');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'replan:advise');
UPDATE alembic_version SET version_num='0012_rbac_seed' WHERE alembic_version.version_num = '0011_auth_foundation';
-- Running upgrade 0012_rbac_seed -> 0013_account_recovery
CREATE TABLE itinerary_claim_tokens (
    id VARCHAR(36) NOT NULL, 
    itinerary_id VARCHAR(36) NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    used_at TIMESTAMP WITH TIME ZONE, 
    used_by VARCHAR(36), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(itinerary_id) REFERENCES itineraries (id) ON DELETE CASCADE, 
    FOREIGN KEY(used_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_itinerary_claim_tokens_itinerary_id ON itinerary_claim_tokens (itinerary_id);
CREATE UNIQUE INDEX ix_itinerary_claim_tokens_token_hash ON itinerary_claim_tokens (token_hash);
INSERT INTO permissions (name, description, created_at) VALUES ('account:sessions', 'List and revoke own sign-in sessions', '2026-10-15 16:06:05.732731+00:00');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'account:sessions');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'account:sessions');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'account:sessions');
UPDATE alembic_version SET version_num='0013_account_recovery' WHERE alembic_version.version_num = '0012_rbac_seed';
-- Running upgrade 0013_account_recovery -> 0014_mfa
ALTER TABLE user_mfa ADD COLUMN last_used_step BIGINT;
ALTER TABLE auth_tokens DROP CONSTRAINT ck_auth_tokens_purpose;
ALTER TABLE auth_tokens ADD CONSTRAINT ck_auth_tokens_purpose CHECK (purpose IN ('reset_password', 'verify_email', 'mfa_login'));
INSERT INTO permissions (name, description, created_at) VALUES ('account:mfa', 'Manage own two-factor authentication', '2026-10-15 16:06:05.733595+00:00');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'account:mfa');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'account:mfa');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'account:mfa');
UPDATE alembic_version SET version_num='0014_mfa' WHERE alembic_version.version_num = '0013_account_recovery';
-- Running upgrade 0014_mfa -> 0015_partner_onboarding
ALTER TABLE providers ADD COLUMN business_type VARCHAR(40);
ALTER TABLE providers ADD COLUMN tax_code VARCHAR(40);
ALTER TABLE providers ADD COLUMN business_license_no VARCHAR(80);
ALTER TABLE providers ADD COLUMN website VARCHAR(300);
ALTER TABLE providers ADD COLUMN document_urls JSONB DEFAULT '[]' NOT NULL;
ALTER TABLE providers ADD COLUMN application_note TEXT DEFAULT '' NOT NULL;
ALTER TABLE providers ADD COLUMN applied_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE providers ADD COLUMN review_note TEXT DEFAULT '' NOT NULL;
ALTER TABLE providers ADD COLUMN reviewed_by VARCHAR(36);
ALTER TABLE providers ADD COLUMN reviewed_at TIMESTAMP WITH TIME ZONE;
CREATE INDEX ix_providers_verification_status ON providers (verification_status);
UPDATE providers SET verification_status = 'verified' WHERE verification_status = 'pending';
UPDATE alembic_version SET version_num='0015_partner_onboarding' WHERE alembic_version.version_num = '0014_mfa';
-- Running upgrade 0015_partner_onboarding -> 0016_portal_platform
ALTER TABLE pois ADD COLUMN opening_hours VARCHAR(200);
ALTER TABLE pois ADD COLUMN ticket_info VARCHAR(200);
ALTER TABLE pois ADD COLUMN tags JSONB DEFAULT '[]' NOT NULL;
ALTER TABLE pois ADD COLUMN is_landmark BOOLEAN DEFAULT false NOT NULL;
ALTER TABLE pois ADD COLUMN source_url VARCHAR(1000);
CREATE TABLE site_banners (
    id VARCHAR(36) NOT NULL, 
    title VARCHAR(180) NOT NULL, 
    subtitle VARCHAR(300) DEFAULT '' NOT NULL, 
    image_url VARCHAR(1000) NOT NULL, 
    link_url VARCHAR(500) DEFAULT '/' NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    sort_order INTEGER DEFAULT '0' NOT NULL, 
    starts_at TIMESTAMP WITH TIME ZONE, 
    ends_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);
CREATE TABLE site_articles (
    id VARCHAR(36) NOT NULL, 
    title VARCHAR(220) NOT NULL, 
    slug VARCHAR(220) NOT NULL, 
    excerpt VARCHAR(600) DEFAULT '' NOT NULL, 
    body TEXT DEFAULT '' NOT NULL, 
    cover_url VARCHAR(1000) DEFAULT '' NOT NULL, 
    category VARCHAR(60) DEFAULT 'Cẩm nang' NOT NULL, 
    status VARCHAR(16) DEFAULT 'draft' NOT NULL, 
    published_at TIMESTAMP WITH TIME ZONE, 
    author_id VARCHAR(36), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_site_articles_slug UNIQUE (slug), 
    CONSTRAINT ck_site_articles_status CHECK (status IN ('draft', 'published')), 
    FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_site_articles_slug ON site_articles (slug);
CREATE INDEX ix_site_articles_status ON site_articles (status);
CREATE TABLE site_collections (
    id VARCHAR(36) NOT NULL, 
    title VARCHAR(180) NOT NULL, 
    description VARCHAR(600) DEFAULT '' NOT NULL, 
    place_ids JSONB DEFAULT '[]' NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    sort_order INTEGER DEFAULT '0' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);
CREATE TABLE page_views (
    id VARCHAR(36) NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    visitor_hash VARCHAR(64) NOT NULL, 
    session_hash VARCHAR(64) NOT NULL, 
    user_id VARCHAR(36), 
    path VARCHAR(300) NOT NULL, 
    entity_type VARCHAR(20), 
    entity_id VARCHAR(36), 
    referrer_host VARCHAR(200), 
    device VARCHAR(16) DEFAULT 'desktop' NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_page_views_occurred_at ON page_views (occurred_at);
CREATE INDEX ix_page_views_visitor_hash ON page_views (visitor_hash);
CREATE INDEX ix_page_views_entity ON page_views (entity_type, entity_id, occurred_at);
CREATE TABLE experience_reviews (
    id VARCHAR(36) NOT NULL, 
    experience_id VARCHAR(36) NOT NULL, 
    provider_id VARCHAR(36) NOT NULL, 
    booking_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36), 
    rating INTEGER NOT NULL, 
    comment TEXT DEFAULT '' NOT NULL, 
    reply TEXT, 
    replied_at TIMESTAMP WITH TIME ZONE, 
    status VARCHAR(16) DEFAULT 'published' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_experience_reviews_booking UNIQUE (booking_id), 
    CONSTRAINT ck_experience_reviews_rating CHECK (rating BETWEEN 1 AND 5), 
    CONSTRAINT ck_experience_reviews_status CHECK (status IN ('published', 'hidden')), 
    FOREIGN KEY(experience_id) REFERENCES experiences (id) ON DELETE CASCADE, 
    FOREIGN KEY(provider_id) REFERENCES providers (id) ON DELETE CASCADE, 
    FOREIGN KEY(booking_id) REFERENCES bookings (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_experience_reviews_experience_id ON experience_reviews (experience_id);
CREATE INDEX ix_experience_reviews_provider_id ON experience_reviews (provider_id);
CREATE INDEX ix_experience_reviews_created_at ON experience_reviews (created_at);
INSERT INTO permissions (name, description, created_at) VALUES ('review:write', 'Review an experience after attending it', '2026-10-15 16:06:05.739747+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('provider:reviews', 'Read and reply to reviews of own experiences', '2026-10-15 16:06:05.739747+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('provider:analytics', 'Read views and conversion of own experiences', '2026-10-15 16:06:05.739747+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:places', 'Create, edit, publish and hide places and landmarks', '2026-10-15 16:06:05.739747+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:content', 'Manage banners, articles and collections on the traveler web', '2026-10-15 16:06:05.739747+00:00');
INSERT INTO permissions (name, description, created_at) VALUES ('admin:analytics', 'Read traffic analytics', '2026-10-15 16:06:05.739747+00:00');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('traveler', 'review:write');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'provider:reviews');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('provider', 'provider:analytics');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:places');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:content');
INSERT INTO role_permissions (role_name, permission_name) VALUES ('admin', 'admin:analytics');
UPDATE alembic_version SET version_num='0016_portal_platform' WHERE alembic_version.version_num = '0015_partner_onboarding';
-- Running upgrade 0012_slot_timestamps_utc, 0016_portal_platform -> 0017_merge_main_and_portal
DELETE FROM alembic_version WHERE alembic_version.version_num = '0012_slot_timestamps_utc';
UPDATE alembic_version SET version_num='0017_merge_main_and_portal' WHERE alembic_version.version_num = '0016_portal_platform';


COMMIT;
