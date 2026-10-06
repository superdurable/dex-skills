#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(message)


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def require_revision(checkout: Path, expected: str, label: str) -> None:
    checkout = checkout.resolve()
    if not (checkout / ".git").exists():
        fail(f"{label} is not a Git checkout: {checkout}")
    actual = git(checkout, "rev-parse", "HEAD")
    resolved = git(checkout, "rev-parse", f"{expected}^{{commit}}")
    if actual != resolved:
        fail(f"{label} checkout {actual} does not match baseline {resolved}")


def require_text(path: Path, *needles: str) -> None:
    content = path.read_text()
    for needle in needles:
        if needle not in content:
            fail(f"{path} is missing required text: {needle}")


def require_ancestor(checkout: Path, ancestor: str, descendant: str, label: str) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=checkout,
        check=False,
    )
    if result.returncode != 0:
        fail(f"{label} {ancestor} is not an ancestor of {descendant}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dex-root", required=True, type=Path)
    arguments = parser.parse_args()

    server_baseline = (ROOT / "DEX_SERVER_BASELINE").read_text().strip()
    cli_baseline = (ROOT / "DEX_CLI_BASELINE").read_text().strip()
    require_revision(arguments.dex_root, cli_baseline, "Dex CLI")
    require_ancestor(arguments.dex_root, server_baseline, cli_baseline, "Dex Server baseline")

    require_text(
        arguments.dex_root / "cli" / "internal" / "flowviz" / "v2_directives.go",
        "GetDexSummary",
        "GetDexDisplay",
        "dex:group",
        "RPCOptions.Action",
        "ActionRequiresPermission",
        '"ui-slot"',
        '"capture"',
        '"qr-code"',
        "capture requires a source:user string input field",
    )
    require_text(
        arguments.dex_root / "cli" / "schema" / "flow-definition-graph.v2.schema.json",
        '"capture"',
        '"qr-code"',
    )
    require_text(
        arguments.dex_root / "cli" / "README.md",
        "--schema-version 2.0",
        "Go-only",
    )
    require_text(
        arguments.dex_root / "web" / "api" / "v2.go",
        "V2PermissionModeTrustedHeader",
        "V2WorkQueuePermissionsHeader",
        "Action permission denied",
        'json:"capture,omitempty"',
    )
    require_text(
        arguments.dex_root / "web" / "app" / "v2" / "workspace" / "qrScanner.ts",
        "await import('@zxing/browser')",
        "facingMode: { ideal: 'environment' }",
        "for (const track of stream.getTracks()) track.stop()",
    )
    require_text(
        arguments.dex_root / "sdk-go" / "README.md",
        "Once a permission has",
        "remains searchable after completion",
    )
    require_text(
        arguments.dex_root / "cli" / "internal" / "flowviz" / "go_connector_factory.go",
        "parseConnectorFactoryStep",
        "parseConnectorAnnotations",
        '"annotations"',
        '"connectionName"',
        '"moduleVersion"',
    )
    require_text(
        arguments.dex_root / "cli" / "internal" / "flowviz" / "go_connector_trigger.go",
        "collectConnectorTriggerBindings",
        '"bindingName"',
        "TriggerBindingFactoryConfigMarker",
    )
    require_text(
        arguments.dex_root / "cli" / "internal" / "dev" / "config.go",
        "connector-config-dir",
        "connector-release-override",
    )
    require_text(
        arguments.dex_root / "web" / "connector_connection_store.go",
        "connections.json",
        "TriggerBindings",
        "putTriggerBinding",
        "os.Rename",
    )
    require_text(
        arguments.dex_root / "web" / "connector_oauth.go",
        "code_verifier",
        "connectorOAuthResponseValue",
        "credentials[mapping.Credential]",
        "credentialSecrets",
    )
    require_text(
        arguments.dex_root / "cli" / "internal" / "flowviz" / "go_connector_configuration_ui.go",
        "ConnectorConfigurationUI",
        "ConnectorUIUnit",
        "ConnectorUIBinding",
        "compile-time literals",
    )
    require_text(
        arguments.dex_root / "web" / "connector_studio_command.go",
        "connectorStudioCommandRequest",
        "CONNECTOR_STUDIO_COMMAND_NOT_FOUND",
        "containsConnectorSecret",
        "https",
    )
    require_text(
        arguments.dex_root / "web" / "connector_use_configuration.go",
        "validateConnectorUseConfiguration",
        "allowedPointers",
        "Connector configuration path",
    )
    require_text(
        arguments.dex_root / "web" / "app" / "v2" / "connectors" / "ConnectorsPage.tsx",
        "provider.command.execute",
        "use.configuration.save",
        "connector.frame.resize",
        "Local override",
    )
    require_text(
        arguments.dex_root / "web" / "api" / "v2_start.go",
        "START_FLOW_DISABLED",
        "WORKER_UNHEALTHY",
        "v2StartStepInput",
        "SkipWaitFor: definition.Start.SkipWaitFor",
        "hostedStartRequestIdentity",
        "START_IDENTITY_CONFLICT",
    )
    require_text(
        arguments.dex_root / "web" / "api" / "v2.go",
        "requireEmbeddedMutationCSRF",
        "WEB_MUTATION_CSRF_INVALID",
        "subtle.ConstantTimeCompare",
    )
    require_text(
        arguments.dex_root / "web" / "project_configuration.go",
        "projectconfig",
        "APPLICATION_ENVIRONMENT_FORBIDDEN",
    )
    print("validated Dex Server and CLI baselines")


if __name__ == "__main__":
    main()
