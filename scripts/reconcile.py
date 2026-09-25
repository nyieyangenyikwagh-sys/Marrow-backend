"""Read-only snapshot reconciliation. Exit 1 means an accounting discrepancy."""
import asyncio
import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import engine
from app.services.reconciliation_service import reconcile


async def main():
    try:
        async with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                connection = await connection.execution_options(isolation_level="REPEATABLE READ", postgresql_readonly=True)
            async with connection.begin():
                async with AsyncSession(bind=connection) as session:
                    report = await reconcile(session)
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
