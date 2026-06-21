import psycopg2

conn = psycopg2.connect(
    "postgresql://opensync_db_user:hccpOk0Am6VkHxE3JPdTDofsLiqv8yUe@dpg-d8qhsrsvikkc73avqdvg-a.singapore-postgres.render.com/opensync_db?sslmode=require"
)
conn.autocommit = True
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS developers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    github_username VARCHAR(39) NOT NULL UNIQUE,
    github_id BIGINT UNIQUE,
    display_name VARCHAR(255),
    avatar_url TEXT,
    profile_confidence DECIMAL(4,3) DEFAULT 0.0,
    last_analyzed_at TIMESTAMPTZ,
    analysis_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS skill_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    developer_id UUID NOT NULL,
    skill_key VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    confidence DECIMAL(4,3) NOT NULL,
    evidence_count INTEGER DEFAULT 0,
    first_seen_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    trajectory VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(developer_id, skill_key)
);
CREATE TABLE IF NOT EXISTS repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    github_id INTEGER UNIQUE NOT NULL,
    full_name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    primary_language VARCHAR(50),
    topics TEXT[],
    stars INTEGER DEFAULT 0,
    forks INTEGER DEFAULT 0,
    open_issues INTEGER DEFAULT 0,
    last_commit_at TIMESTAMPTZ,
    has_contributing_guide BOOLEAN DEFAULT false,
    has_code_of_conduct BOOLEAN DEFAULT false,
    newcomer_friendliness FLOAT DEFAULT 0.5,
    embedding_id VARCHAR(255),
    last_indexed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
""")

print("Tables created successfully")
cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
print("Tables:", cur.fetchall())
conn.close()