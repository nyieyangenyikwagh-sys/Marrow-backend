"""Run PostgreSQL migrations and integration tests with workspace-local Windows binaries.

Optional verification utility; the application itself uses the configured database.
Install @embedded-postgres/windows-x64 into .tools/postgres before invoking this module.
The temporary server binds only to loopback and is always stopped in finally.
"""
import asyncio
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", help="Optional directory containing the Microsoft C++ runtime DLLs")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    binaries = root / ".tools/postgres/node_modules/@embedded-postgres/windows-x64/native/bin"
    if not (binaries / "postgres.exe").is_file():
        raise SystemExit("Workspace-local PostgreSQL binaries are not installed")
    data = root / ".tools" / f"postgres-test-{uuid4().hex}"
    assert data.resolve().parent == (root / ".tools").resolve()
    data.mkdir()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    native_env = {**os.environ, "PATH": os.pathsep.join([str(binaries), str(binaries.parent / "lib"),
                  args.runtime_dir or str(Path(sys.base_prefix)), str(Path(sys.base_prefix)), os.environ.get("PATH", "")])}
    subprocess.run([str(binaries / "initdb.exe"), "-D", str(data / "data"), "-U", "banking",
                    "--auth=trust", "--no-locale", "--encoding=UTF8"], check=True, creationflags=hidden, env=native_env)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    url = f"postgresql+asyncpg://banking@127.0.0.1:{port}/postgres"
    env = {**native_env, "DATABASE_URL": url, "TEST_DATABASE_URL": url, "ENVIRONMENT": "test"}
    with (data / "postgres.log").open("w") as log:
        server = subprocess.Popen([str(binaries / "postgres.exe"), "-D", str(data / "data"),
                                   "-h", "127.0.0.1", "-p", str(port)],
                                  stdout=log, stderr=subprocess.STDOUT, creationflags=hidden, env=native_env)
        try:
            async def ready():
                import asyncpg
                for _ in range(40):
                    try:
                        conn = await asyncpg.connect(host="127.0.0.1", port=port, user="banking", database="postgres", timeout=2)
                        await conn.close()
                        return
                    except (OSError, asyncpg.PostgresError):
                        await asyncio.sleep(0.5)
                raise RuntimeError(f"PostgreSQL did not start; inspect {data / 'postgres.log'}")
            asyncio.run(ready())
            subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, check=True)
            subprocess.run([sys.executable, "-c", "import asyncio; from scripts.seed import seed; asyncio.run(seed('LocalTestPassword123!', demo=True))"], cwd=root, env=env, check=True)
            subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=short"], cwd=root, env=env, check=True)
            print("PostgreSQL migration, demo seed, and full test suite verified.")
        finally:
            subprocess.run([str(binaries / "pg_ctl.exe"), "-D", str(data / "data"), "stop", "-m", "fast"],
                           creationflags=hidden, timeout=20, check=False, env=native_env)
            server.wait(timeout=20)


if __name__ == "__main__":
    main()
