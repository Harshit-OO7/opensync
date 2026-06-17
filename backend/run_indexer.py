import asyncio
import sys
sys.path.insert(0, ".")

from app.services.ml.repo_indexer import RepoIndexer


async def main():
    indexer = RepoIndexer()
    count = await indexer.index_all()  # all domains
    print(f"Total indexed: {count} repos")


asyncio.run(main())