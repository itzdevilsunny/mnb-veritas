from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from veritas.client import VeritasClient


def create_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--url",
        default=os.getenv("VERITAS_API_URL", "http://127.0.0.1:8000"),
        help="Veritas backend URL (default: http://127.0.0.1:8000)",
    )
    common.add_argument(
        "--key",
        default=os.getenv("VERITAS_API_KEY", "veritas-local-dev-key-2026"),
        help="Veritas API key (default: veritas-local-dev-key-2026)",
    )

    parser = argparse.ArgumentParser(
        prog="veritas",
        description="MNB Veritas CLI: Multi-Model AI Verification & Anti-Hallucination Evidence Middleware",
        parents=[common],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. verify
    verify_cmd = subparsers.add_parser("verify", parents=[common], help="Execute multi-lab verification on a query")
    verify_cmd.add_argument("query", help="Financial or regulatory query text")
    verify_cmd.add_argument(
        "--policy",
        choices=["strict", "balanced", "standard"],
        default="strict",
        help="Policy enforcement profile (default: strict)",
    )
    verify_cmd.add_argument("--ref-date", help="Temporal reference date (YYYY-MM-DD)")
    verify_cmd.add_argument("--export-cert", help="File path to save signed PDF certificate")
    verify_cmd.add_argument("--json", action="store_true", help="Output raw JSON verification result")

    # 2. chain
    chain_cmd = subparsers.add_parser("chain", parents=[common], help="Verify cryptographic SHA-256 audit blockchain")
    chain_cmd.add_argument("--json", action="store_true", help="Output raw JSON status")

    # 3. health
    health_cmd = subparsers.add_parser("health", parents=[common], help="Check provider circuit states and readiness")
    health_cmd.add_argument("--json", action="store_true", help="Output raw JSON health status")

    # 4. cert
    cert_cmd = subparsers.add_parser("cert", parents=[common], help="Download compliance certificate by audit ID")
    cert_cmd.add_argument("audit_id", help="Target audit ID (e.g. aud_12345678)")
    cert_cmd.add_argument(
        "--format",
        choices=["pdf", "json"],
        default="pdf",
        help="Output certificate format (default: pdf)",
    )
    cert_cmd.add_argument("--out", help="Output file path (defaults to veritas-certificate-<audit_id>.<fmt>)")

    return parser


async def run_cli_async(args: argparse.Namespace) -> int:
    client = VeritasClient(api_url=args.url, api_key=args.key)
    try:
        if args.command == "verify":
            res = await client.verify(
                query=args.query,
                policy=args.policy,
                reference_date=args.ref_date,
            )
            if args.json:
                print(res.model_dump_json(indent=2))
            else:
                verdict_color = "\033[92m" if res.is_approved else ("\033[91m" if res.is_abstained else "\033[93m")
                reset_color = "\033[0m"
                print(f"\n=======================================================")
                print(f"VERITAS VERDICT: {verdict_color}{res.verdict}{reset_color} | Policy: {res.policy_applied.upper()}")
                print(f"Audit ID       : {res.audit_id}")
                print(f"Primary Model  : {res.telemetry.primary_model}")
                print(f"Auditor Model  : {res.telemetry.auditor_model or 'Single Lab'}")
                print(f"Latency        : {res.telemetry.latency_ms}ms")
                print(f"Claims         : {res.claims_count} total, {res.verified_quotes_count} verified quotes")
                print(f"=======================================================")
                print(f"Answer:\n{res.answer}\n")

            if args.export_cert:
                pdf_bytes = await client.download_certificate(res.audit_id, format="pdf")
                with open(args.export_cert, "wb") as f:
                    f.write(pdf_bytes)  # type: ignore
                print(f"  -> Certificate saved to: {args.export_cert}")

            return 0 if res.is_approved else 1

        elif args.command == "chain":
            status = await client.verify_chain()
            if args.json:
                print(status.model_dump_json(indent=2))
            else:
                print(f"\n=======================================================")
                print(f"SHA-256 AUDIT BLOCKCHAIN INTEGRITY: {'VALID' if status.valid else 'BROKEN'}")
                print(f"Records Checked : {status.checked_count}")
                print(f"Latest Hash     : {status.latest_record_hash}")
                print(f"Details         : {status.details}")
                print(f"=======================================================\n")
            return 0 if status.valid else 2

        elif args.command == "health":
            health = await client.get_provider_health()
            if args.json:
                print(health.model_dump_json(indent=2))
            else:
                print(f"\n=======================================================")
                print(f"PROVIDER GATEWAY HEALTH: {health.active_count}/{health.total_configured} ACTIVE")
                print(f"Redis Connected : {health.redis_connected}")
                print(f"Providers:")
                for lab, info in health.providers.items():
                    state = info.get("state", "UNKNOWN")
                    model = info.get("model", "default")
                    print(f"  • {lab:<10}: state={state:<8} model={model}")
                print(f"=======================================================\n")
            return 0

        elif args.command == "cert":
            out_file = args.out or f"veritas-certificate-{args.audit_id}.{args.format}"
            data = await client.download_certificate(args.audit_id, format=args.format)
            if args.format == "pdf":
                with open(out_file, "wb") as f:
                    f.write(data)  # type: ignore
                print(f"Exported signed PDF certificate to {out_file} ({len(data)} bytes)")
            else:
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                print(f"Exported canonical JSON seal to {out_file}")
            return 0

        return 0
    finally:
        await client.close()


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()
    try:
        sys.exit(asyncio.run(run_cli_async(args)))
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
