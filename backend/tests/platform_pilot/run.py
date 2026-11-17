"""Run the pilot smoke test in a disposable, loopback-only PostgreSQL cluster."""

import argparse
import base64
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-bin", type=Path, required=True)
    parser.add_argument("--tenant-rls-only", action="store_true")
    parser.add_argument("--integrations-only", action="store_true")
    parser.add_argument("--operations-only", action="store_true")
    parser.add_argument("--load-only", action="store_true")
    parser.add_argument("--load-quick", action="store_true", help="Shorter windows for harness checks")
    parser.add_argument("--chrome-bin", type=Path, help="Run the Chrome browser smoke against an isolated HTTPS pilot")
    args = parser.parse_args()
    postgres_bin = args.postgres_bin.resolve()
    backend = Path(__file__).resolve().parents[2]
    executable_suffix = ".exe" if os.name == "nt" else ""

    def postgres_tool(name: str) -> str:
        tool = postgres_bin / (name + executable_suffix)
        if not tool.is_file():
            parser.error(f"PostgreSQL tool not found: {tool}")
        return str(tool)

    initdb = postgres_tool("initdb")
    pg_ctl = postgres_tool("pg_ctl")
    createdb = postgres_tool("createdb")

    with TemporaryDirectory(prefix="enterprise-platform-pilot-") as temp:
        root = Path(temp).resolve()
        staged = root / "backend"
        for directory in ("app", "alembic"):
            shutil.copytree(backend / directory, staged / directory, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(backend / "alembic.ini", staged)
        shutil.copy2(Path(__file__).with_name("auth_smoke.py"), staged)
        shutil.copy2(Path(__file__).with_name("access_edge_smoke.py"), staged)
        shutil.copy2(Path(__file__).with_name("browser_smoke.py"), staged)
        shutil.copy2(Path(__file__).with_name("operations_smoke.py"), staged)
        shutil.copy2(Path(__file__).with_name("restoration_smoke.py"), staged)
        shutil.copy2(Path(__file__).with_name("smoke.py"), staged)
        shutil.copy2(Path(__file__).with_name("tenant_rls.py"), staged)
        shutil.copy2(Path(__file__).with_name("integration_smoke.py"), staged)
        shutil.copy2(Path(__file__).with_name("load_smoke.py"), staged)

        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]

        password = secrets.token_hex(24)
        password_file = root / "postgres-password"
        password_file.write_text(password + "\n", encoding="ascii")
        data_dir = root / "postgres"
        env = {
            key: value for key, value in os.environ.items()
            if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "HOME", "USERPROFILE", "TEMP", "TMP"}
        }
        env.update({
            "PGPASSWORD": password,
            "PYTHONUTF8": "1",
            "ENVIRONMENT": "platform-pilot-test",
            "DATABASE_URL": f"postgresql://pilot_qa:{password}@127.0.0.1:{port}/platform_pilot_test",
            "JWT_SECRET": secrets.token_hex(32),
            "ALLOW_REGISTRATION": "false",
            "GOOGLE_DRIVE_MOCK": "true",
            "GOOGLE_DRIVE_MOCK_DIR": str(root / "drive-default"),
            "STORAGE_DIR": str(root / "tenant-files"),
            "FRONTEND_DIST_DIR": str(root / "no-frontend"),
        })

        def run(*command: str) -> None:
            subprocess.run(command, cwd=staged, env=env, check=True)

        run(initdb, "-D", str(data_dir), "-U", "pilot_qa", "--auth=scram-sha-256",
            f"--pwfile={password_file}", "--encoding=UTF8", "--no-locale")
        password_file.unlink()
        try:
            run(pg_ctl, "-D", str(data_dir), "-l", str(root / "postgres.log"), "-w", "start",
                "-o", f"-h 127.0.0.1 -p {port} -c unix_socket_directories=")
            run(createdb, "-w", "-h", "127.0.0.1", "-p", str(port), "-U", "pilot_qa", "platform_pilot_test")
            if args.chrome_bin:
                run(sys.executable, "-m", "alembic", "upgrade", "head")
                frontend = backend.parent / "frontend" / "dist"
                if not (frontend / "index.html").is_file():
                    parser.error("Build the frontend before running the browser smoke.")
                shutil.copytree(frontend, root / "browser-frontend")
                env.update(
                    FRONTEND_DIST_DIR=str(root / "browser-frontend"),
                    PLATFORM_AUTH_ENABLED="true",
                    AUTH_MFA_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
                    AUTH_MAIL_OUTBOX=str(root / "auth-outbox"),
                )
                run(sys.executable, "browser_smoke.py", str(args.chrome_bin.resolve()))
            elif args.tenant_rls_only:
                run(sys.executable, "-m", "alembic", "upgrade", "005_engineer_documents")
                run(sys.executable, "tenant_rls.py", "--prepare-legacy")
                run(sys.executable, "-m", "alembic", "upgrade", "head")
                run(sys.executable, "tenant_rls.py", "--expect-legacy")
            elif args.load_only:
                run(sys.executable, "-m", "alembic", "upgrade", "head")
                env.update(
                    PLATFORM_AUTH_ENABLED="true",
                    AUTH_MFA_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
                )
                run(sys.executable, "load_smoke.py", *(["--quick"] if args.load_quick else []))
            else:
                run(sys.executable, "-m", "alembic", "upgrade", "head")
                if not args.operations_only:
                    run(sys.executable, "integration_smoke.py")
                if not args.integrations_only:
                    if not args.operations_only:
                        run(sys.executable, "smoke.py")
                        started = monotonic()
                        connection = ("-w", "-h", "127.0.0.1", "-p", str(port), "-U", "pilot_qa")
                        backup = root / "pilot-backup.dump"
                        run(postgres_tool("pg_dump"), *connection, "-Fc", "-f", str(backup), "platform_pilot_test")
                        shutil.copytree(root / "tenant-files", root / "restore-file-backup")
                        run(createdb, *connection, "platform_pilot_restore")
                        run(postgres_tool("pg_restore"), *connection, "--exit-on-error", "-d", "platform_pilot_restore", str(backup))
                        run(sys.executable, "restoration_smoke.py")
                        print(f"Disposable backup and restore elapsed {monotonic() - started:.2f}s.", flush=True)
                    env.update(
                        PLATFORM_AUTH_ENABLED="true",
                        AUTH_MFA_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
                        AUTH_MAIL_OUTBOX=str(root / "auth-outbox"),
                    )
                    run(sys.executable, "operations_smoke.py" if args.operations_only else "auth_smoke.py")
                    for name in ("PLATFORM_AUTH_ENABLED", "AUTH_MFA_KEY", "AUTH_MAIL_OUTBOX"):
                        env.pop(name)
                    if not args.operations_only:
                        run(sys.executable, "tenant_rls.py")
        finally:
            if (data_dir / "postmaster.pid").exists():
                run(pg_ctl, "-D", str(data_dir), "-m", "fast", "-w", "stop")


if __name__ == "__main__":
    main()
