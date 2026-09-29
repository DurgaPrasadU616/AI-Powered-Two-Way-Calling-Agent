-- =============================================================================
-- AI Calling Agent -- Seed Data
-- =============================================================================
-- Run AFTER: alembic upgrade head (from backend/)
--   psql -U calling_agent -d calling_agent_db -f database/seed.sql
-- OR run the Python seeder (recommended, uses the app's own hasher):
--   python scripts/seed_db.py
--
-- Admin credentials seeded here:
--   Email:    admin@sephawk.com
--   Password: Admin@123
--   Hash generated with:
--     python -c "from app.core.security import hash_password; print(hash_password('Admin@123'))"
--   NOTE: this is a DEMO credential. Change ADMIN_PASSWORD in .env for anything real.
-- =============================================================================

-- == 2 sample contacts ========================================================
INSERT INTO contacts (name, phone_e164, company, purpose, product)
VALUES
    (
        'Rahul Kumar',
        '+919876543210',
        'Hotel Blue Diamond',
        'Interested in commercial RO system for hotel water treatment',
        'Commercial RO System'
    ),
    (
        'Priya Sharma',
        '+919845123456',
        'Sharma Food Industries',
        'Enquiry about industrial RO system for food processing plant',
        'Industrial RO System'
    )
ON CONFLICT DO NOTHING;

-- == 1 admin ==================================================================
INSERT INTO admins (email, password_hash)
VALUES (
    'admin@sephawk.com',
    '$2b$12$ZuCdhzU2Fc7FHaH4nT5fVeo6hnH6539ov9E2kytRT1y6zbhXkLhOO'
)
ON CONFLICT (email) DO NOTHING;
