"""
Sync local repositories table to production PostgreSQL.
"""
import psycopg2

# Local DB
local = psycopg2.connect(
    "postgresql://opensync:opensync@localhost:5432/opensync"
)
local_cur = local.cursor()
local_cur.execute("""
    SELECT github_id, full_name, description, primary_language,
           topics, stars, forks, open_issues, last_commit_at,
           has_contributing_guide, has_code_of_conduct,
           newcomer_friendliness, embedding_id, last_indexed_at
    FROM repositories
""")
repos = local_cur.fetchall()
print(f"Found {len(repos)} repos locally")

# Production DB
prod = psycopg2.connect(
    "postgresql://opensync_db_user:hccpOk0Am6VkHxE3JPdTDofsLiqv8yUe@dpg-d8qhsrsvikkc73avqdvg-a.singapore-postgres.render.com/opensync_db?sslmode=require"
)
prod.autocommit = True
prod_cur = prod.cursor()

for repo in repos:
    try:
        prod_cur.execute("""
            INSERT INTO repositories (
                github_id, full_name, description, primary_language,
                topics, stars, forks, open_issues, last_commit_at,
                has_contributing_guide, has_code_of_conduct,
                newcomer_friendliness, embedding_id, last_indexed_at,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                now(), now()
            )
            ON CONFLICT (github_id) DO UPDATE SET
                stars = EXCLUDED.stars,
                newcomer_friendliness = EXCLUDED.newcomer_friendliness,
                embedding_id = EXCLUDED.embedding_id,
                updated_at = now()
        """, repo)
        print(f"Synced: {repo[1]}")
    except Exception as e:
        print(f"Failed {repo[1]}: {e}")

print("Sync complete!")
local.close()
prod.close()