import asyncio
import functools
import json
import logging
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from secrets import token_hex
from timeit import default_timer

import yaml
from aiohttp import (
    ClientError,
    ClientResponse,
    ClientSession,
    ClientTimeout,
)

LOGGER = logging.getLogger(__name__)

event_stream_handler = logging.StreamHandler()
event_stream_handler.setFormatter(logging.Formatter("\nEVENT: %(message)s"))

DEFAULT_PYTHON_PATH = ".."
PYTHON = os.getenv("PYTHON", sys.executable)

START_TIMEOUT = float(os.getenv("START_TIMEOUT", 30.0))

class AgentBase:
    def __init__(
            self,
            ident: str,
            http_port: int,
            internal_host: str = "127.0.0.1",
            external_host: str = "localhost",
            genesis_data: str = None,
            seed: str = None,
            transport_type: str = "http",
            extra_args=None,
    ):
        self.ident = ident
        self.http_port = http_port
        self.admin_port = http_port + 1
        self.internal_host = internal_host
        self.external_host = external_host
        self.genesis_data = genesis_data
        self.genesis_txn_list = None
        self.revocation = False
        self.mediation = False
        self.mediator_connection_id = None
        self.mediator_request_id = None
        self.log_file = None
        self.log_config = None
        self.log_level = None
        self.reuse_connections = False # TODO
        self.multi_use_invitations = True
        self.public_did_connections = True
        self.transport_type = transport_type

        self.extra_args = extra_args or [
            "--auto-accept-invites",
            "--auto-accept-requests",
            "--auto-store-credential",
            "--public-invites",
            "--invite-public",
            "--requests-through-public-did"
        ]

        self.admin_url = f"http://{self.internal_host}:{self.admin_port}"
        self.endpoint = f"http://{self.external_host}:{self.http_port}"

        self.proc = None
        self.client_session: ClientSession = ClientSession()
        self.thread_pool_executor = ThreadPoolExecutor(20)

        if not seed:
            seed = "random"
        rand_name = token_hex(4)
        self.seed = token_hex(16) if seed == "random" else seed
        self.wallet_type = "askar"
        self.wallet_name = self.ident.lower().replace(" ", "") + rand_name
        self.wallet_key = self.ident + rand_name
        self.did = None
        self.wallet_stats = []

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

        self.log_callback = None
        self.log_cache = []

    async def get_connections(self):
        return await self.admin_GET("/connections")

    async def get_wallets(self):
        """Get registered wallets of agent (this is an agency call)."""
        return await self.admin_GET("/multitenancy/wallets")

    async def get_public_did(self):
        """Get public did of wallet (called for a sub-wallet)."""
        return await self.admin_GET("/wallet/did/public")

    async def fetch_schemas(self):
        return await self.admin_GET("/schemas/created")

    async def fetch_cred_defs(self):
        return await self.admin_GET("/credential-definitions/created")

    async def fetch_cred_def(self, cred_def_id: str):
        return await self.admin_GET(
            "/credential-definitions/" + cred_def_id
        )

    async def register_schema_and_creddef(
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
        self.log_msg("Schema ID: " + schema_id)

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
        self.log_msg("Cred def ID: " + credential_definition_id)
        return schema_id, credential_definition_id


    def get_agent_args(self):
        result = [
            ("--endpoint", self.endpoint),
            ("--label", self.ident),
            "--auto-ping-connection",
            "--auto-respond-messages",
            ("--inbound-transport", self.transport_type, "0.0.0.0", str(self.http_port)),
            ("--outbound-transport", self.transport_type),
            ("--admin", "0.0.0.0", str(self.admin_port)),
            "--admin-insecure-mode",
            ("--wallet-type", self.wallet_type),
            ("--wallet-name", self.wallet_name),
            ("--wallet-key", self.wallet_key),
            "--preserve-exchange-records",
            "--auto-provision",
            "--public-invites",
            "--emit-new-didcomm-prefix",
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
        if self.genesis_data:
            result.append(("--genesis-transactions", self.genesis_data))
        if self.genesis_txn_list:
            result.append(("--genesis-transactions-list", self.genesis_txn_list))
        if self.seed:
            result.append(("--seed", self.seed))

        if self.revocation:
            # turn on notifications if revocation is enabled
            result.append("--notify-revocation")
        # enable extended webhooks
        result.append("--debug-webhooks")
        # always enable notification webhooks
        result.append("--monitor-revocation-notification")

        if self.mediation:
            result.append("--open-mediation")

        if self.extra_args:
            result.extend(self.extra_args)

        return result

    async def register_did(
            self,
            ledger_url: str = None,
            alias: str = None,
            did: str = None,
            verkey: str = None,
            role: str = "TRUST_ANCHOR",
    ):
        # if registering a did for issuing indy credentials, publish the did on the ledger
        self.log(f"Registering {self.ident} ...")
        if not ledger_url:
            if self.multi_write_ledger_url:
                ledger_url = self.multi_write_ledger_url
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
        self.log(f"Registered DID: {self.did}")

    def log(self, output, source: str = None):
        if source == "stderr":
            color = "[bold red]"
        elif not source:
            color = "[blue]"
        else:
            color = None
        try:
            self.log_msg(output, color=color)
        except AssertionError as e:
            raise e

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
            functools.partial(self.log, source="stdout"),
        )
        loop.run_in_executor(
            self.thread_pool_executor,
            output_reader,
            proc.stderr,
            functools.partial(self.log, source="stderr"),
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
                self.proc.stdout.close()
                self.proc.stderr.close()
                print(f"Exited with return code {self.proc.returncode}")
            except subprocess.TimeoutExpired:
                msg = "Process did not terminate in time"
                print(msg)
                raise Exception(msg)

    async def terminate(self):
        # close session to admin api
        await self.client_session.close()
        # now shut down the agent
        loop = asyncio.get_event_loop()
        if self.proc:
            future = loop.run_in_executor(self.thread_pool_executor, self._terminate)
            await asyncio.wait_for(future, 10)

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
        try:
            if not headers:
                headers = {}
            response = await self.admin_request(
                "GET", path, None, text, params, headers=headers
            )
            return response
        except ClientError as e:
            self.log(f"Error during GET {path}: {str(e)}")
            raise

    async def admin_GET(
            self, path, text=False, params=None, headers=None
    ) -> ClientResponse:
        try:
            return await self.admin_request(
                "GET", path, None, text, params, headers=headers
            )
        except ClientError as e:
            self.log(f"Error during GET {path}: {str(e)}")
            raise

    async def agency_admin_POST(
            self, path, data=None, text=False, params=None, headers=None
    ) -> ClientResponse:
        try:
            if not headers:
                headers = {}
            return await self.admin_request(
                "POST", path, data, text, params, headers=headers
            )
        except ClientError as e:
            self.log(f"Error during POST {path}: {str(e)}")
            raise

    async def admin_POST(
            self, path, data=None, text=False, params=None, headers=None, raise_error=True
    ) -> ClientResponse:
        try:
            return await self.admin_request(
                "POST", path, data, text, params, headers=headers
            )
        except ClientError as e:
            self.log(f"Error during POST {path}: {str(e)}")
            if not raise_error:
                return None
            raise

    async def admin_PATCH(
            self, path, data=None, text=False, params=None, headers=None
    ) -> ClientResponse:
        try:
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
            return await self.admin_request(
                "DELETE", path, data, text, params, headers=headers
            )
        except ClientError as e:
            self.log(f"Error during DELETE {path}: {str(e)}")
            raise

    async def admin_GET_FILE(self, path, params=None, headers=None) -> bytes:
        try:
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

    async def get_invite(
            self,
            label: str = None,
            auto_accept: bool = True,
            reuse_connections: bool = False,
            multi_use_invitations: bool = True,
            public_did_connections: bool = True,
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
        if label:
            payload["my_label"] = label
        return await self.admin_POST(
            "/out-of-band/create-invitation",
            payload,
            params=invi_params,
        )

    async def receive_invite(self, invite, auto_accept: bool = True):
        params = {}
        if self.mediation:
            params["mediation_id"] = self.mediator_request_id

        # reuse connections if requested and possible
        params["use_existing_connection"] = json.dumps(self.reuse_connections)
        connection = await self.admin_POST(
            "/out-of-band/receive-invitation",
            invite,
            params=params,
        )

        self.connection_id = connection["connection_id"]
        return connection

    def set_log_callback(self, log_callback):
        self.log_callback = log_callback
        for log in self.log_cache:
            self.log_msg(log)
        self.log_cache = []

    def log_msg(self, msg, color=None):
        if isinstance(msg, list):
            msg = str(" ".join(msg))
        else:
            msg = str(msg).rstrip()

        if color is not None:
            msg = color + msg

        if self.log_callback is None:
            self.log_cache.append(msg)
            return

        self.log_callback(msg)

    def log_json(self, *msg):
        pass


def output_reader(handle, callback):
    while not handle.closed:
        try:
            line = handle.readline()
            if line is not None:
                callback(line)
        except:
            # see comment in DemoAgent.handle_output
            # trace log and prompt_toolkit do not get along...
            pass


def flatten(args):
    for arg in args:
        if isinstance(arg, (list, tuple)):
            yield from flatten(arg)
        else:
            yield arg
