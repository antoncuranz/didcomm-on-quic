import asyncio
import base64
import functools
import json
import logging
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from timeit import default_timer
from secrets import token_hex

import yaml
from aiohttp import (
    ClientError,
    ClientRequest,
    ClientResponse,
    ClientSession,
    ClientTimeout,
    web,
)

LOGGER = logging.getLogger(__name__)

event_stream_handler = logging.StreamHandler()
event_stream_handler.setFormatter(logging.Formatter("\nEVENT: %(message)s"))

DEBUG_EVENTS = os.getenv("EVENTS")
EVENT_LOGGER = logging.getLogger("event")
EVENT_LOGGER.setLevel(logging.DEBUG if DEBUG_EVENTS else logging.NOTSET)
EVENT_LOGGER.addHandler(event_stream_handler)
EVENT_LOGGER.propagate = False

TRACE_TARGET = os.getenv("TRACE_TARGET")
TRACE_TAG = os.getenv("TRACE_TAG")
TRACE_ENABLED = os.getenv("TRACE_ENABLED")

WEBHOOK_TARGET = os.getenv("WEBHOOK_TARGET")

AGENT_ENDPOINT = os.getenv("AGENT_ENDPOINT")

DEFAULT_POSTGRES = bool(os.getenv("POSTGRES"))
DEFAULT_INTERNAL_HOST = "127.0.0.1"
DEFAULT_EXTERNAL_HOST = "localhost"
DEFAULT_PYTHON_PATH = ".."
PYTHON = os.getenv("PYTHON", sys.executable)

START_TIMEOUT = float(os.getenv("START_TIMEOUT", 30.0))

RUN_MODE = os.getenv("RUNMODE")

GENESIS_URL = os.getenv("GENESIS_URL")
LEDGER_URL = os.getenv("LEDGER_URL")
GENESIS_FILE = os.getenv("GENESIS_FILE")

if RUN_MODE == "docker":
    DEFAULT_INTERNAL_HOST = os.getenv("DOCKERHOST") or "host.docker.internal"
    DEFAULT_EXTERNAL_HOST = DEFAULT_INTERNAL_HOST
    DEFAULT_PYTHON_PATH = "."
elif RUN_MODE == "pwd":
    # DEFAULT_INTERNAL_HOST =
    DEFAULT_EXTERNAL_HOST = os.getenv("DOCKERHOST") or "host.docker.internal"
    DEFAULT_PYTHON_PATH = "."

WALLET_TYPE_INDY = "indy"
WALLET_TYPE_ASKAR = "askar"
WALLET_TYPE_ANONCREDS = "askar-anoncreds"

CRED_FORMAT_INDY = "indy"
CRED_FORMAT_JSON_LD = "json-ld"
CRED_FORMAT_VC_DI = "vc_di"
DID_METHOD_SOV = "sov"
DID_METHOD_KEY = "key"
KEY_TYPE_ED255 = "ed25519"
KEY_TYPE_BLS = "bls12381g2"
SIG_TYPE_BLS = "BbsBlsSignature2020"


class repr_json:
    def __init__(self, val):
        self.val = val

    def __repr__(self) -> str:
        if isinstance(self.val, str):
            return self.val
        return json.dumps(self.val, indent=4)


async def fetch_genesis_txns(genesis_url):
    genesis = None
    try:
        async with ClientSession() as session:
            async with session.get(genesis_url) as resp:
                genesis = await resp.text()
    except Exception:
        LOGGER.exception("Error loading genesis transactions:")
    return genesis


class AriesAgent:
    def __init__(
            self,
            ident: str,
            http_port: int,
            admin_port: int,
            internal_host: str = None,
            external_host: str = None,
            genesis_data: str = None,
            genesis_txn_list: str = None,
            seed: str = None,
            label: str = None,
            color: str = None,
            prefix: str = None,
            tails_server_base_url: str = None,
            timing: bool = False,
            timing_log: str = None,
            postgres: bool = None,
            revocation: bool = False,
            multitenant: bool = False,
            mediation: bool = False,
            aip: int = 20,
            arg_file: str = None,
            extra_args=None,
            log_file: str = None,
            log_config: str = None,
            log_level: str = None,
            reuse_connections: bool = False,
            multi_use_invitations: bool = False,
            public_did_connections: bool = False,
            **params,
    ):
        self.ident = ident
        self.http_port = http_port
        self.admin_port = admin_port
        self.internal_host = internal_host or DEFAULT_INTERNAL_HOST
        self.external_host = external_host or DEFAULT_EXTERNAL_HOST
        self.genesis_data = genesis_data
        self.genesis_txn_list = genesis_txn_list
        self.label = label or ident
        self.color = color
        self.prefix = prefix
        self.timing = timing
        self.timing_log = timing_log
        self.postgres = DEFAULT_POSTGRES if postgres is None else postgres
        self.tails_server_base_url = tails_server_base_url
        self.revocation = revocation
        self.extra_args = extra_args
        self.trace_enabled = TRACE_ENABLED
        self.trace_target = TRACE_TARGET
        self.trace_tag = TRACE_TAG
        self.multitenant = multitenant
        self.external_webhook_target = WEBHOOK_TARGET
        self.mediation = mediation
        self.mediator_connection_id = None
        self.mediator_request_id = None
        self.aip = aip
        self.arg_file = arg_file
        self.log_file = log_file
        self.log_config = log_config
        self.log_level = log_level
        self.reuse_connections = reuse_connections
        self.multi_use_invitations = multi_use_invitations
        self.public_did_connections = public_did_connections

        self.admin_url = f"http://{self.internal_host}:{admin_port}"
        if AGENT_ENDPOINT:
            self.endpoint = AGENT_ENDPOINT
        elif RUN_MODE == "pwd":
            self.endpoint = f"http://{self.external_host}".replace(
                "{PORT}", str(http_port)
            )
        else:
            self.endpoint = f"http://{self.external_host}:{http_port}"

        self.webhook_port = None
        self.webhook_url = None
        self.webhook_site = None
        self.params = params
        self.proc = None
        self.client_session: ClientSession = ClientSession()
        self.thread_pool_executor = ThreadPoolExecutor(20)

        if not seed:
            seed = "random"
        rand_name = token_hex(4)
        self.seed = token_hex(16) if seed == "random" else seed
        self.storage_type = params.get("storage_type")
        self.wallet_type = params.get("wallet_type") or "askar"
        self.wallet_name = (
                params.get("wallet_name") or self.ident.lower().replace(" ", "") + rand_name
        )
        self.wallet_key = params.get("wallet_key") or self.ident + rand_name
        self.did = None
        self.wallet_stats = []

        # for multitenancy, storage_type and wallet_type are the same for all wallets
        if self.multitenant:
            self.agency_ident = self.ident
            self.agency_wallet_name = self.wallet_name
            self.agency_wallet_seed = self.seed
            self.agency_wallet_did = self.did
            self.agency_wallet_key = self.wallet_key

        self.multi_write_ledger_url = None
        if self.genesis_txn_list:
            updated_config_list = []
            with open(self.genesis_txn_list, "r") as stream:
                ledger_config_list = yaml.safe_load(stream)
            for config in ledger_config_list:
                if "genesis_url" in config and "/$LEDGER_HOST:" in config.get(
                        "genesis_url"
                ):
                    config["genesis_url"] = config.get("genesis_url").replace(
                        "$LEDGER_HOST", str(self.external_host)
                    )
                updated_config_list.append(config)
                if "is_write" in config and config["is_write"]:
                    self.multi_write_ledger_url = config["genesis_url"].replace(
                        "/genesis", ""
                    )
            with open(self.genesis_txn_list, "w") as file:
                documents = yaml.dump(updated_config_list, file)

    async def get_wallets(self):
        """Get registered wallets of agent (this is an agency call)."""
        wallets = await self.admin_GET("/multitenancy/wallets")
        return wallets

    def get_new_webhook_port(self):
        """Get new webhook port for registering additional sub-wallets"""
        self.webhook_port = self.webhook_port + 1
        return self.webhook_port

    async def get_public_did(self):
        """Get public did of wallet (called for a sub-wallet)."""
        did = await self.admin_GET("/wallet/did/public")
        return did

    async def register_schema_and_creddef(
            self,
            schema_name,
            version,
            schema_attrs,
            support_revocation: bool = False,
            revocation_registry_size: int = None,
            tag=None,
            wallet_type=WALLET_TYPE_INDY,
    ):
        if wallet_type in [WALLET_TYPE_INDY, WALLET_TYPE_ASKAR]:
            return await self.register_schema_and_creddef_indy(
                schema_name,
                version,
                schema_attrs,
                support_revocation=support_revocation,
                revocation_registry_size=revocation_registry_size,
                tag=tag,
            )
        elif wallet_type == WALLET_TYPE_ANONCREDS:
            return await self.register_schema_and_creddef_anoncreds(
                schema_name,
                version,
                schema_attrs,
                support_revocation=support_revocation,
                revocation_registry_size=revocation_registry_size,
                tag=tag,
            )
        else:
            raise Exception("Invalid wallet_type: " + str(wallet_type))

    async def fetch_schemas(
            self,
            wallet_type=WALLET_TYPE_INDY,
    ):
        if wallet_type in [WALLET_TYPE_INDY, WALLET_TYPE_ASKAR]:
            schemas_saved = await self.admin_GET("/schemas/created")
            return schemas_saved
        elif wallet_type == WALLET_TYPE_ANONCREDS:
            schemas_saved = await self.admin_GET("/anoncreds/schemas")
            return schemas_saved
        else:
            raise Exception("Invalid wallet_type: " + str(wallet_type))

    async def fetch_cred_defs(
            self,
            wallet_type=WALLET_TYPE_INDY,
    ):
        if wallet_type in [WALLET_TYPE_INDY, WALLET_TYPE_ASKAR]:
            cred_defs_saved = await self.admin_GET("/credential-definitions/created")
            return cred_defs_saved
        elif wallet_type == WALLET_TYPE_ANONCREDS:
            cred_defs_saved = await self.admin_GET("/anoncreds/credential-definitions")
            return cred_defs_saved
        else:
            raise Exception("Invalid wallet_type: " + str(wallet_type))

    async def fetch_cred_def(
            self,
            cred_def_id: str,
            wallet_type=WALLET_TYPE_INDY,
    ):
        if wallet_type in [WALLET_TYPE_INDY, WALLET_TYPE_ASKAR]:
            cred_def_saved = await self.admin_GET(
                "/credential-definitions/" + cred_def_id
            )
            return cred_def_saved
        elif wallet_type == WALLET_TYPE_ANONCREDS:
            cred_def_saved = await self.admin_GET(
                "/anoncreds/credential-definition/" + cred_def_id
            )
            return cred_def_saved
        else:
            raise Exception("Invalid wallet_type: " + str(wallet_type))

    async def register_schema_and_creddef_indy(
            self,
            schema_name,
            version,
            schema_attrs,
            support_revocation: bool = False,
            revocation_registry_size: int = None,
            tag=None,
    ):
        # Create a schema
        schema_body = {
            "schema_name": schema_name,
            "schema_version": version,
            "attributes": schema_attrs,
        }
        schema_response = await self.admin_POST("/schemas", schema_body)
        self.log_json(json.dumps(schema_response), label="Schema:")
        await asyncio.sleep(2.0)
        if "schema_id" in schema_response:
            # schema is created directly
            schema_id = schema_response["schema_id"]
        else:
            # need to wait for the endorser process
            schema_response = {"schema_ids": []}
            attempts = 3
            while 0 < attempts and 0 == len(schema_response["schema_ids"]):
                schema_response = await self.admin_GET("/schemas/created")
                if 0 == len(schema_response["schema_ids"]):
                    await asyncio.sleep(1.0)
                    attempts = attempts - 1
            schema_id = schema_response["schema_ids"][0]
        self.log_msg("Schema ID:", schema_id)

        # Create a cred def for the schema
        cred_def_tag = (
            tag if tag else (self.ident + "." + schema_name).replace(" ", "_")
        )
        credential_definition_body = {
            "schema_id": schema_id,
            "support_revocation": support_revocation,
            **{
                "revocation_registry_size": revocation_registry_size
                for _ in [""]
                if support_revocation
            },
            "tag": cred_def_tag,
        }
        credential_definition_response = await self.admin_POST(
            "/credential-definitions", credential_definition_body
        )
        await asyncio.sleep(2.0)
        if "credential_definition_id" in credential_definition_response:
            # cred def is created directly
            credential_definition_id = credential_definition_response[
                "credential_definition_id"
            ]
        else:
            # need to wait for the endorser process
            credential_definition_response = {"credential_definition_ids": []}
            attempts = 3
            while 0 < attempts and 0 == len(
                    credential_definition_response["credential_definition_ids"]
            ):
                credential_definition_response = await self.admin_GET(
                    "/credential-definitions/created"
                )
                if 0 == len(
                        credential_definition_response["credential_definition_ids"]
                ):
                    await asyncio.sleep(1.0)
                    attempts = attempts - 1
            credential_definition_id = credential_definition_response[
                "credential_definition_ids"
            ][0]
        self.log_msg("Cred def ID:", credential_definition_id)
        return schema_id, credential_definition_id

    async def register_schema_and_creddef_anoncreds(
            self,
            schema_name,
            version,
            schema_attrs,
            support_revocation: bool = False,
            revocation_registry_size: int = None,
            tag=None,
    ):
        # Create a schema
        schema_body = {
            "schema": {
                "attrNames": schema_attrs,
                "issuerId": self.did,
                "name": schema_name,
                "version": version,
            },
            "options": {},
        }
        schema_response = await self.admin_POST("/anoncreds/schema", schema_body)
        self.log_json(json.dumps(schema_response), label="Schema:")
        await asyncio.sleep(2.0)
        if "schema_id" in schema_response["schema_state"]:
            # schema is created directly
            schema_id = schema_response["schema_state"]["schema_id"]
        else:
            # need to wait for the endorser process
            schema_response = {"schema_ids": []}
            attempts = 3
            while 0 < attempts and 0 == len(schema_response["schema_ids"]):
                schema_response = await self.admin_GET("/anoncreds/schemas")
                if 0 == len(schema_response["schema_ids"]):
                    await asyncio.sleep(1.0)
                    attempts = attempts - 1
            schema_id = schema_response["schema_ids"][0]
        self.log_msg("Schema ID:", schema_id)

        # Create a cred def for the schema
        cred_def_tag = (
            tag if tag else (self.ident + "." + schema_name).replace(" ", "_")
        )
        max_cred_num = revocation_registry_size if revocation_registry_size else 0
        credential_definition_body = {
            "credential_definition": {
                "tag": cred_def_tag,
                "schemaId": schema_id,
                "issuerId": self.did,
            },
            "options": {
                "support_revocation": support_revocation,
                "max_cred_num": max_cred_num,
            },
        }
        credential_definition_response = await self.admin_POST(
            "/anoncreds/credential-definition", credential_definition_body
        )
        self.log_json(json.dumps(credential_definition_response), label="Cred Def:")
        await asyncio.sleep(2.0)
        if (
                "credential_definition_id"
                in credential_definition_response["credential_definition_state"]
        ):
            # cred def is created directly
            credential_definition_id = credential_definition_response[
                "credential_definition_state"
            ]["credential_definition_id"]
        else:
            # need to wait for the endorser process
            credential_definition_response = {"credential_definition_ids": []}
            attempts = 3
            while 0 < attempts and 0 == len(
                    credential_definition_response["credential_definition_ids"]
            ):
                credential_definition_response = await self.admin_GET(
                    "/anoncreds/credential-definitions"
                )
                if 0 == len(
                        credential_definition_response["credential_definition_ids"]
                ):
                    await asyncio.sleep(1.0)
                    attempts = attempts - 1
            credential_definition_id = credential_definition_response[
                "credential_definition_ids"
            ][0]
        self.log_msg("Cred def ID:", credential_definition_id)
        return schema_id, credential_definition_id

    def get_agent_args(self):
        result = [
            ("--endpoint", self.endpoint),
            ("--label", self.label),
            "--auto-ping-connection",
            "--auto-respond-messages",
            ("--inbound-transport", "http", "0.0.0.0", str(self.http_port)),
            ("--outbound-transport", "http"),
            ("--admin", "0.0.0.0", str(self.admin_port)),
            "--admin-insecure-mode",
            ("--wallet-type", self.wallet_type),
            ("--wallet-name", self.wallet_name),
            ("--wallet-key", self.wallet_key),
            "--preserve-exchange-records",
            "--auto-provision",
            "--public-invites",
            # ("--log-level", "debug"),
        ]
        if self.log_file or self.log_file == "":
            result.extend(
                [
                    ("--log-file", self.log_file),
                ]
            )
        if self.log_config:
            result.extend(
                [
                    ("--log-config", self.log_config),
                ]
            )
        if self.log_level:
            result.extend(
                [
                    ("--log-level", self.log_level),
                ]
            )
        if self.aip == 20:
            result.append("--emit-new-didcomm-prefix")
        if self.multitenant:
            result.extend(
                [
                    "--multitenant",
                    "--multitenant-admin",
                    ("--jwt-secret", "very_secret_secret"),
                ]
            )
        if self.genesis_data:
            result.append(("--genesis-transactions", self.genesis_data))
        if self.genesis_txn_list:
            result.append(("--genesis-transactions-list", self.genesis_txn_list))
        if self.seed:
            result.append(("--seed", self.seed))
        if self.storage_type:
            result.append(("--storage-type", self.storage_type))
        if self.timing:
            result.append("--timing")
        if self.timing_log:
            result.append(("--timing-log", self.timing_log))
        if self.postgres:
            result.extend(
                [
                    ("--wallet-storage-type", "postgres_storage"),
                    ("--wallet-storage-config", json.dumps(self.postgres_config)),
                    ("--wallet-storage-creds", json.dumps(self.postgres_creds)),
                ]
            )
        if self.webhook_url:
            result.append(("--webhook-url", self.webhook_url))
        if self.external_webhook_target:
            result.append(("--webhook-url", self.external_webhook_target))
        if self.trace_enabled:
            result.extend(
                [
                    ("--trace",),
                    ("--trace-target", self.trace_target),
                    ("--trace-tag", self.trace_tag),
                    ("--trace-label", self.label + ".trace"),
                ]
            )

        if self.revocation:
            # turn on notifications if revocation is enabled
            result.append("--notify-revocation")
        # enable extended webhooks
        result.append("--debug-webhooks")
        # always enable notification webhooks
        result.append("--monitor-revocation-notification")

        if self.tails_server_base_url:
            result.append(("--tails-server-base-url", self.tails_server_base_url))
        else:
            # set the tracing parameters but don't enable tracing
            result.extend(
                [
                    (
                        "--trace-target",
                        self.trace_target if self.trace_target else "log",
                    ),
                    (
                        "--trace-tag",
                        self.trace_tag if self.trace_tag else "acapy.events",
                    ),
                    ("--trace-label", self.label + ".trace"),
                ]
            )

        if self.mediation:
            result.extend(
                [
                    "--open-mediation",
                ]
            )

        if self.arg_file:
            result.extend(
                (
                    "--arg-file",
                    self.arg_file,
                )
            )

        if self.extra_args:
            result.extend(self.extra_args)

        return result

    @property
    def prefix_str(self):
        if self.prefix:
            return f"{self.prefix:10s} |"

    async def register_did(
            self,
            ledger_url: str = None,
            alias: str = None,
            did: str = None,
            verkey: str = None,
            role: str = "TRUST_ANCHOR",
            cred_type: str = CRED_FORMAT_INDY,
    ):
        if cred_type in [CRED_FORMAT_INDY, CRED_FORMAT_VC_DI]:
            # if registering a did for issuing indy credentials, publish the did on the ledger
            self.log(f"Registering {self.ident} ...")
            if not ledger_url:
                if self.multi_write_ledger_url:
                    ledger_url = self.multi_write_ledger_url
                else:
                    ledger_url = LEDGER_URL
            if not ledger_url:
                ledger_url = f"http://{self.external_host}:9000"
            data = {"alias": alias or self.ident}
            if role:
                data["role"] = role
            if did and verkey:
                data["did"] = did
                data["verkey"] = verkey
            else:
                data["seed"] = self.seed
            if role is None or role == "":
                # if author using endorser register nym and wait for endorser ...
                await self.admin_POST("/ledger/register-nym", params=data)
                await asyncio.sleep(3.0)
                nym_info = data
            else:
                self.log_msg("using ledger: " + ledger_url + "/register")
                resp = await self.client_session.post(
                    ledger_url + "/register", json=data
                )
                if resp.status != 200:
                    raise Exception(
                        f"Error registering DID {data}, response code {resp.status}"
                    )
                nym_info = await resp.json()
            self.did = nym_info["did"]
            self.log(f"nym_info: {nym_info}")
            if self.multitenant:
                if not self.agency_wallet_did:
                    self.agency_wallet_did = self.did
            self.log(f"Registered DID: {self.did}")
        elif cred_type == CRED_FORMAT_JSON_LD:
            # TODO register a did:key with appropriate signature type
            pass
        else:
            raise Exception("Invalid credential type:" + cred_type)

    async def register_or_switch_wallet(
            self,
            target_wallet_name,
            public_did=False,
            webhook_port: int = None,
            cred_type: str = CRED_FORMAT_INDY,
            taa_accept=False,
    ):
        if webhook_port is not None:
            await self.listen_webhooks(webhook_port)
        self.log(f"Register or switch to wallet {target_wallet_name}")
        if target_wallet_name == self.agency_wallet_name:
            self.ident = self.agency_ident
            self.wallet_name = self.agency_wallet_name
            self.seed = self.agency_wallet_seed
            self.did = self.agency_wallet_did
            self.wallet_key = self.agency_wallet_key

            wallet_params = await self.get_id_and_token(self.wallet_name)
            self.managed_wallet_params["wallet_id"] = wallet_params["id"]
            self.managed_wallet_params["token"] = wallet_params["token"]

            if taa_accept:
                await self.taa_accept()

            self.log(f"Switching to AGENCY wallet {target_wallet_name}")
            return False

        # check if wallet exists already
        wallets = await self.agency_admin_GET("/multitenancy/wallets")
        for wallet in wallets["results"]:
            if wallet["settings"]["wallet.name"] == target_wallet_name:
                # if so set local agent attributes
                self.wallet_name = target_wallet_name
                # assume wallet key is wallet name
                self.wallet_key = target_wallet_name
                self.ident = target_wallet_name
                # we can't recover the seed so let's set it to None and see what happens
                self.seed = None

                wallet_params = await self.get_id_and_token(self.wallet_name)
                self.managed_wallet_params["wallet_id"] = wallet_params["id"]
                self.managed_wallet_params["token"] = wallet_params["token"]

                if taa_accept:
                    await self.taa_accept()

                self.log(f"Switching to EXISTING wallet {target_wallet_name}")
                return False

        # if not then create it
        wallet_params = {
            "wallet_key": target_wallet_name,
            "wallet_name": target_wallet_name,
            "wallet_type": self.wallet_type,
            "label": target_wallet_name,
            "wallet_webhook_urls": [self.webhook_url],
            "wallet_dispatch_type": "both",
        }
        self.wallet_name = target_wallet_name
        self.wallet_key = target_wallet_name
        self.ident = target_wallet_name
        new_wallet = await self.agency_admin_POST("/multitenancy/wallet", wallet_params)
        self.log("New wallet params:", new_wallet)
        self.managed_wallet_params = new_wallet

        if taa_accept:
            await self.taa_accept()

        if public_did:
            if cred_type == CRED_FORMAT_INDY:
                # assign public did
                new_did = await self.admin_POST("/wallet/did/create")
                self.did = new_did["result"]["did"]
                await self.register_did(
                    did=new_did["result"]["did"],
                    verkey=new_did["result"]["verkey"],
                )
                await self.admin_POST("/wallet/did/public?did=" + self.did)
                await asyncio.sleep(3.0)
            elif cred_type == CRED_FORMAT_VC_DI:
                # assign public did
                new_did = await self.admin_POST("/wallet/did/create")
                self.did = new_did["result"]["did"]
                await self.register_did(
                    did=new_did["result"]["did"],
                    verkey=new_did["result"]["verkey"],
                    cred_type=CRED_FORMAT_VC_DI,
                )
                await self.admin_POST("/wallet/did/public?did=" + self.did)
                await asyncio.sleep(3.0)
            elif cred_type == CRED_FORMAT_JSON_LD:
                # create did of appropriate type
                data = {"method": DID_METHOD_KEY, "options": {"key_type": KEY_TYPE_BLS}}
                new_did = await self.admin_POST("/wallet/did/create", data=data)
                self.did = new_did["result"]["did"]

                # did:key is not registered as a public did
            else:
                # todo ignore for now
                pass

        self.log(f"Created NEW wallet {target_wallet_name}")
        return True

    async def get_id_and_token(self, wallet_name):
        wallet = await self.agency_admin_GET(
            f"/multitenancy/wallets?wallet_name={wallet_name}"
        )
        wallet_id = wallet["results"][0]["wallet_id"]

        wallet = await self.agency_admin_POST(
            f"/multitenancy/wallet/{wallet_id}/token", {}
        )
        token = wallet["token"]

        return {"id": wallet_id, "token": token}

    def handle_output(self, output, source: str = None):
        if source == "stderr":
            color = "[bold red]"
        elif not source:
            color = self.color or "[blue]"
        else:
            color = None
        try:
            self.log_msg(output, color=color)
        except AssertionError as e:
            if self.trace_enabled and self.trace_target == "log":
                # when tracing to a log file,
                # we hit an issue with the underlying prompt_toolkit.
                # it attempts to output what is written by the log and can't find the
                # correct terminal and throws an error. The trace log record does show
                # in the terminal, so let's just ignore this error.
                pass
            else:
                raise e

    def log(self, msg, **kwargs):
        self.handle_output(msg, **kwargs)

    # def log_json(self, data, label: str = None, **kwargs):
    #     log_json(data, label=label, prefix=self.prefix_str, **kwargs)

    # def log_timer(self, label: str, show: bool = True, **kwargs):
    #     return log_timer(label, show, logger=self.log, **kwargs)

    def _process(self, args, env, loop):
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            encoding="utf-8",
            close_fds=True,
        )
        loop.run_in_executor(
            self.thread_pool_executor,
            output_reader,
            proc.stdout,
            functools.partial(self.handle_output, source="stdout"),
        )
        loop.run_in_executor(
            self.thread_pool_executor,
            output_reader,
            proc.stderr,
            functools.partial(self.handle_output, source="stderr"),
        )
        return proc

    def get_process_args(self):
        return list(
            flatten(
                ([PYTHON, "-m", "aries_cloudagent", "start"], self.get_agent_args())
            )
        )

    async def start_process(self, python_path: str = None, wait: bool = True):
        my_env = os.environ.copy()
        python_path = DEFAULT_PYTHON_PATH if python_path is None else python_path
        if python_path:
            my_env["PYTHONPATH"] = python_path

        agent_args = self.get_process_args()
        self.log(agent_args)

        # start agent sub-process
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(
            self.thread_pool_executor, self._process, agent_args, my_env, loop
        )
        self.proc = await asyncio.wait_for(future, 20)
        if wait:
            await asyncio.sleep(1.0)
            await self.detect_process()

    def _terminate(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=1.5)
                self.log(f"Exited with return code {self.proc.returncode}")
            except subprocess.TimeoutExpired:
                msg = "Process did not terminate in time"
                self.log(msg)
                raise Exception(msg)

    async def terminate(self):
        # close session to admin api
        await self.client_session.close()
        # shut down web hooks first
        if self.webhook_site:
            await self.webhook_site.stop()
            await asyncio.sleep(0.5)
        # now shut down the agent
        loop = asyncio.get_event_loop()
        if self.proc:
            future = loop.run_in_executor(self.thread_pool_executor, self._terminate)
            await asyncio.wait_for(future, 10)

    async def listen_webhooks(self, webhook_port):
        self.webhook_port = webhook_port
        if RUN_MODE == "pwd":
            self.webhook_url = f"http://localhost:{str(webhook_port)}/webhooks"
        else:
            self.webhook_url = self.external_webhook_target or (
                f"http://{self.external_host}:{str(webhook_port)}/webhooks"
            )
        app = web.Application()
        app.add_routes(
            [
                web.post("/webhooks/topic/{topic}/", self._receive_webhook),
                # route for fetching proof request for connectionless requests
                web.get(
                    "/webhooks/pres_req/{pres_req_id}/",
                    self._send_connectionless_proof_req,
                ),
            ]
        )
        runner = web.AppRunner(app)
        await runner.setup()
        self.webhook_site = web.TCPSite(runner, "0.0.0.0", webhook_port)
        await self.webhook_site.start()
        self.log_msg("Started webhook listener on port:", webhook_port)

    async def _receive_webhook(self, request: ClientRequest):
        topic = request.match_info["topic"].replace("-", "_")
        payload = await request.json()
        await self.handle_webhook(topic, payload, request.headers)
        return web.Response(status=200)

    async def service_decorator(self):
        # add a service decorator
        did_url = "/wallet/did/public"
        agent_public_did = await self.admin_GET(did_url)
        endpoint_url = (
                "/wallet/get-did-endpoint" + "?did=" + agent_public_did["result"]["did"]
        )
        agent_endpoint = await self.admin_GET(endpoint_url)
        decorator = {
            "recipientKeys": [agent_public_did["result"]["verkey"]],
            # "routingKeys": [agent_public_did["result"]["verkey"]],
            "serviceEndpoint": agent_endpoint["endpoint"],
        }
        return decorator

    async def _send_connectionless_proof_req(self, request: ClientRequest):
        pres_req_id = request.match_info["pres_req_id"]
        url = "/present-proof/records/" + pres_req_id
        proof_exch = await self.admin_GET(url)
        if not proof_exch:
            return web.Response(status=404)
        proof_reg_txn = proof_exch["presentation_request_dict"]
        proof_reg_txn["~service"] = await self.service_decorator()
        if request.headers.get("Accept") == "application/json":
            return web.json_response(proof_reg_txn)
        objJsonStr = json.dumps(proof_reg_txn)
        objJsonB64 = base64.b64encode(objJsonStr.encode("ascii"))
        service_url = self.webhook_url
        redirect_url = service_url + "/?m=" + objJsonB64.decode("ascii")
        self.log_msg(f"Redirecting to: {redirect_url}")
        raise web.HTTPFound(redirect_url)

    async def handle_webhook(self, topic: str, payload, headers: dict):
        if topic != "webhook":  # would recurse
            handler = f"handle_{topic}"
            wallet_id = headers.get("x-wallet-id")
            method = getattr(self, handler, None)
            if method:
                EVENT_LOGGER.debug(
                    "Agent called controller webhook: %s%s%s%s",
                    handler,
                    f"\nPOST {self.webhook_url}/topic/{topic}/",
                    (f" for wallet: {wallet_id}" if wallet_id else ""),
                    (f" with payload: \n{repr_json(payload)}\n" if payload else ""),
                )
                asyncio.get_event_loop().create_task(method(payload))
            else:
                self.log_msg(
                    f"Error: agent {self.ident} "
                    f"has no method {handler} "
                    f"to handle webhook on topic {topic}"
                )

    async def handle_problem_report(self, message):
        self.log(
            f"Received problem report: {message['description']['en']}\n",
            source="stderr",
        )

    async def handle_endorse_transaction(self, message):
        self.log("Received endorse transaction ...\n", source="stderr")

    async def handle_revocation_registry(self, message):
        reg_id = message.get("revoc_reg_id", "(undetermined)")
        self.log(f"Revocation registry: {reg_id} state: {message['state']}")

    async def handle_mediation(self, message):
        self.log("Received mediation message ...\n")

    async def handle_keylist(self, message):
        self.log("Received handle_keylist message ...\n")
        self.log(json.dumps(message))

    async def taa_accept(self):
        taa_info = await self.admin_GET("/ledger/taa")
        if taa_info["result"]["taa_required"]:
            taa_accept = {
                "mechanism": list(taa_info["result"]["aml_record"]["aml"].keys())[0],
                "version": taa_info["result"]["taa_record"]["version"],
                "text": taa_info["result"]["taa_record"]["text"],
            }
            self.log(f"Accepting TAA with: {taa_accept}")
            await self.admin_POST(
                "/ledger/taa/accept",
                data=taa_accept,
            )

    async def admin_request(
            self, method, path, data=None, text=False, params=None, headers=None
    ) -> ClientResponse:
        params = {k: v for (k, v) in (params or {}).items() if v is not None}
        async with self.client_session.request(
                method, self.admin_url + path, json=data, params=params, headers=headers
        ) as resp:
            resp_text = await resp.text()
            try:
                resp.raise_for_status()
            except Exception as e:
                # try to retrieve and print text on error
                raise Exception(f"Error: {resp_text}") from e
            if not resp_text and not text:
                return None
            if not text:
                try:
                    return json.loads(resp_text)
                except json.JSONDecodeError as e:
                    raise Exception(f"Error decoding JSON: {resp_text}") from e
            return resp_text

    async def agency_admin_GET(
            self, path, text=False, params=None, headers=None
    ) -> ClientResponse:
        if not self.multitenant:
            raise Exception("Error can't call agency admin unless in multitenant mode")
        try:
            EVENT_LOGGER.debug("Controller GET %s request to Agent", path)
            if not headers:
                headers = {}
            response = await self.admin_request(
                "GET", path, None, text, params, headers=headers
            )
            EVENT_LOGGER.debug(
                "Response from GET %s received: \n%s",
                path,
                repr_json(response),
            )
            return response
        except ClientError as e:
            self.log(f"Error during GET {path}: {str(e)}")
            raise

    async def admin_GET(
            self, path, text=False, params=None, headers=None
    ) -> ClientResponse:
        try:
            EVENT_LOGGER.debug("Controller GET %s request to Agent", path)
            if self.multitenant:
                if not headers:
                    headers = {}
                headers["Authorization"] = (
                        "Bearer " + self.managed_wallet_params["token"]
                )
            response = await self.admin_request(
                "GET", path, None, text, params, headers=headers
            )
            EVENT_LOGGER.debug(
                "Response from GET %s received: \n%s",
                path,
                repr_json(response),
            )
            return response
        except ClientError as e:
            self.log(f"Error during GET {path}: {str(e)}")
            raise

    async def agency_admin_POST(
            self, path, data=None, text=False, params=None, headers=None
    ) -> ClientResponse:
        if not self.multitenant:
            raise Exception("Error can't call agency admin unless in multitenant mode")
        try:
            EVENT_LOGGER.debug(
                "Controller POST %s request to Agent%s",
                path,
                (" with data: \n{}".format(repr_json(data)) if data else ""),
            )
            if not headers:
                headers = {}
            response = await self.admin_request(
                "POST", path, data, text, params, headers=headers
            )
            EVENT_LOGGER.debug(
                "Response from POST %s received: \n%s",
                path,
                repr_json(response),
            )
            return response
        except ClientError as e:
            self.log(f"Error during POST {path}: {str(e)}")
            raise

    async def admin_POST(
            self, path, data=None, text=False, params=None, headers=None, raise_error=True
    ) -> ClientResponse:
        try:
            EVENT_LOGGER.debug(
                "Controller POST %s request to Agent%s",
                path,
                (" with data: \n{}".format(repr_json(data)) if data else ""),
            )
            if self.multitenant:
                if not headers:
                    headers = {}
                headers["Authorization"] = (
                        "Bearer " + self.managed_wallet_params["token"]
                )
            response = await self.admin_request(
                "POST", path, data, text, params, headers=headers
            )
            EVENT_LOGGER.debug(
                "Response from POST %s received: \n%s",
                path,
                repr_json(response),
            )
            return response
        except ClientError as e:
            self.log(f"Error during POST {path}: {str(e)}")
            if not raise_error:
                return None
            raise

    async def admin_PATCH(
            self, path, data=None, text=False, params=None, headers=None
    ) -> ClientResponse:
        try:
            if self.multitenant:
                if not headers:
                    headers = {}
                headers["Authorization"] = (
                        "Bearer " + self.managed_wallet_params["token"]
                )
            return await self.admin_request(
                "PATCH", path, data, text, params, headers=headers
            )
        except ClientError as e:
            self.log(f"Error during PATCH {path}: {str(e)}")
            raise

    async def admin_PUT(
            self, path, data=None, text=False, params=None, headers=None
    ) -> ClientResponse:
        try:
            if self.multitenant:
                if not headers:
                    headers = {}
                headers["Authorization"] = (
                        "Bearer " + self.managed_wallet_params["token"]
                )
            return await self.admin_request(
                "PUT", path, data, text, params, headers=headers
            )
        except ClientError as e:
            self.log(f"Error during PUT {path}: {str(e)}")
            raise

    async def admin_DELETE(
            self, path, data=None, text=False, params=None, headers=None
    ) -> ClientResponse:
        try:
            EVENT_LOGGER.debug(
                "Controller DELETE %s request to Agent%s",
                path,
                (" with data: \n{}".format(repr_json(data)) if data else ""),
            )
            if self.multitenant:
                if not headers:
                    headers = {}
                headers["Authorization"] = (
                        "Bearer " + self.managed_wallet_params["token"]
                )
            response = await self.admin_request(
                "DELETE", path, data, text, params, headers=headers
            )
            EVENT_LOGGER.debug(
                "Response from DELETE %s received: \n%s",
                path,
                repr_json(response),
            )
            return response
        except ClientError as e:
            self.log(f"Error during DELETE {path}: {str(e)}")
            raise

    async def admin_GET_FILE(self, path, params=None, headers=None) -> bytes:
        try:
            if self.multitenant:
                if not headers:
                    headers = {}
                headers["Authorization"] = (
                        "Bearer " + self.managed_wallet_params["token"]
                )
            params = {k: v for (k, v) in (params or {}).items() if v is not None}
            resp = await self.client_session.request(
                "GET", self.admin_url + path, params=params, headers=headers
            )
            resp.raise_for_status()
            return await resp.read()
        except ClientError as e:
            self.log(f"Error during GET FILE {path}: {str(e)}")
            raise

    async def admin_PUT_FILE(self, files, url, params=None, headers=None) -> bytes:
        try:
            if self.multitenant:
                if not headers:
                    headers = {}
                headers["Authorization"] = (
                        "Bearer " + self.managed_wallet_params["token"]
                )
            params = {k: v for (k, v) in (params or {}).items() if v is not None}
            resp = await self.client_session.request(
                "PUT", url, params=params, data=files, headers=headers
            )
            resp.raise_for_status()
            return await resp.read()
        except ClientError as e:
            self.log(f"Error during PUT FILE {url}: {str(e)}")
            raise

    async def detect_process(self, headers=None):
        async def fetch_status(url: str, timeout: float, headers=None):
            code = None
            text = None
            start = default_timer()
            async with ClientSession(timeout=ClientTimeout(total=3.0)) as session:
                while default_timer() - start < timeout:
                    try:
                        async with session.get(url, headers=headers) as resp:
                            code = resp.status
                            if code == 200:
                                text = await resp.text()
                                break
                    except (ClientError, asyncio.TimeoutError):
                        pass
                    await asyncio.sleep(0.5)
            return code, text

        status_url = self.admin_url + "/status"
        status_code, status_text = await fetch_status(
            status_url, START_TIMEOUT, headers=headers
        )

        if not status_text:
            raise Exception(
                f"Timed out waiting for agent process to start (status={status_code}). "
                + f"Admin URL: {status_url}"
            )
        ok = False
        try:
            status = json.loads(status_text)
            ok = isinstance(status, dict) and "version" in status
        except json.JSONDecodeError:
            pass
        if not ok:
            raise Exception(
                f"Unexpected response from agent process. Admin URL: {status_url}"
            )

    async def fetch_timing(self):
        status = await self.admin_GET("/status")
        return status.get("timing")

    def format_timing(self, timing: dict) -> dict:
        result = []
        for name, count in timing["count"].items():
            result.append(
                (
                    name[:35],
                    count,
                    timing["total"][name],
                    timing["avg"][name],
                    timing["min"][name],
                    timing["max"][name],
                )
            )
        result.sort(key=lambda row: row[2], reverse=True)
        yield "{:35} | {:>12} {:>12} {:>10} {:>10} {:>10}".format(
            "", "count", "total", "avg", "min", "max"
        )
        yield "=" * 96
        yield from (
            "{:35} | {:12d} {:12.3f} {:10.3f} {:10.3f} {:10.3f}".format(*row)
            for row in result
        )
        yield ""

    async def reset_timing(self):
        await self.admin_POST("/status/reset", text=True)

    async def get_invite(
            self,
            use_did_exchange: bool,
            auto_accept: bool = True,
            reuse_connections: bool = False,
            multi_use_invitations: bool = False,
            public_did_connections: bool = False,
            emit_did_peer_2: bool = False,
            emit_did_peer_4: bool = False,
    ):
        self.connection_id = None
        if emit_did_peer_2:
            use_did_method = "did:peer:2"
        elif emit_did_peer_4:
            use_did_method = "did:peer:4"
        else:
            use_did_method = None

        create_unique_did = (
                use_did_method is not None
                and (not reuse_connections)
                and (not public_did_connections)
        )
        if use_did_exchange:
            # TODO can mediation be used with DID exchange connections?
            invi_params = {
                "auto_accept": json.dumps(auto_accept),
                "multi_use": json.dumps(multi_use_invitations),
                "create_unique_did": json.dumps(create_unique_did),
            }
            payload = {
                "handshake_protocols": ["didexchange/1.1"],
                "use_public_did": public_did_connections,
            }
            if self.mediation:
                payload["mediation_id"] = self.mediator_request_id
            if use_did_method:
                payload["use_did_method"] = use_did_method
            invi_rec = await self.admin_POST(
                "/out-of-band/create-invitation",
                payload,
                params=invi_params,
            )
        else:
            if reuse_connections:
                # use oob for connection reuse
                invi_params = {
                    "auto_accept": json.dumps(auto_accept),
                    "create_unique_did": json.dumps(create_unique_did),
                }
                payload = {
                    "handshake_protocols": ["https://didcomm.org/connections/1.0"],
                    "use_public_did": public_did_connections,
                }
                if self.mediation:
                    payload["mediation_id"] = self.mediator_request_id
                if use_did_method:
                    payload["use_did_method"] = use_did_method
                invi_rec = await self.admin_POST(
                    "/out-of-band/create-invitation",
                    payload,
                    params=invi_params,
                )
            elif self.mediation:
                invi_params = {
                    "auto_accept": json.dumps(auto_accept),
                }
                payload = {"mediation_id": self.mediator_request_id}
                invi_rec = await self.admin_POST(
                    "/connections/create-invitation",
                    payload,
                    params=invi_params,
                )
            else:
                invi_rec = await self.admin_POST("/connections/create-invitation")

        return invi_rec

    async def receive_invite(self, invite, auto_accept: bool = True):
        params = {}
        if self.mediation:
            params["mediation_id"] = self.mediator_request_id
        if "/out-of-band/" in invite.get("@type", ""):
            # reuse connections if requested and possible
            params["use_existing_connection"] = json.dumps(self.reuse_connections)
            connection = await self.admin_POST(
                "/out-of-band/receive-invitation",
                invite,
                params=params,
            )
        else:
            connection = await self.admin_POST(
                "/connections/receive-invitation",
                invite,
                params=params,
            )

        self.connection_id = connection["connection_id"]
        return connection

    def log_msg(self, msg, color=None):
        print(msg)

    def log_json(self, *msg):
        print(msg)


def output_reader(handle, callback):
    for line in iter(handle.readline, b""):
        if not line:
            continue
        try:
            callback(line)
        except:
            # see comment in DemoAgent.handle_output
            # trace log and prompt_toolkit do not get along...
            sys.exit(1)
            pass


def flatten(args):
    for arg in args:
        if isinstance(arg, (list, tuple)):
            yield from flatten(arg)
        else:
            yield arg
