import asyncio
import functools
import json
import logging
import os
import shutil
import subprocess
import sys
import urllib
from concurrent.futures import ThreadPoolExecutor
from secrets import token_hex
from timeit import default_timer

from aiohttp import (
    ClientError,
    ClientResponse,
    ClientSession,
    ClientTimeout,
)
from aries_cloudagent.utils.env import storage_path

LOGGER = logging.getLogger(__name__)

event_stream_handler = logging.StreamHandler()
event_stream_handler.setFormatter(logging.Formatter("\nEVENT: %(message)s"))

DEFAULT_PYTHON_PATH = ".."
PYTHON = os.getenv("PYTHON", sys.executable)

START_TIMEOUT = float(os.getenv("START_TIMEOUT", 30.0))

async def fetch_genesis_txns(genesis_url):
    genesis = None
    try:
        async with ClientSession() as session:
            async with session.get(genesis_url) as resp:
                genesis = await resp.text()
    except Exception:
        LOGGER.exception("Error loading genesis transactions:")
    return genesis

class AgentBase:
    def __init__(
            self,
            ident: str,
            http_port: int,
            internal_host: str = "127.0.0.1",
            external_host: str = "localhost",
            ledger_url: str = None,
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
        self.ledger_url = ledger_url
        self.genesis_data = genesis_data
        self.revocation = False
        self.mediation = False
        self.mediator_connection_id = None
        self.mediator_request_id = None
        self.log_file = None
        self.log_config = None
        self.log_level = None
        self.reuse_connections = False # TODO: check this
        self.multi_use_invitations = True
        self.public_did_connections = True
        self.transport_type = transport_type
        self.extra_args = extra_args

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
        self.wallet_key = self.ident
        self.did = None
        self.wallet_stats = []

        self.agent_log_callback = None
        self.controller_log_callback = None
        self.agent_log_cache = []
        self.controller_log_cache = []

    async def initialize(self):
        await self.register_did(self.ledger_url)
        self.log_msg("Created public DID")

        if not self.genesis_data:
            self.genesis_data = await fetch_genesis_txns(self.ledger_url + "/genesis")

        await self.start_process()

    async def get_connections(self):
        return await self.admin_GET("/connections")

    async def get_connection_by_did(self, their_public_did):
        uri = "/connection?their_public_did={}".format(their_public_did)
        rsp = await self.admin_GET(uri)
        return rsp["results"][0]

    async def create_connection(self, their_public_did, protocol="didexchange/1.1", use_public_did=True):
        uri = "/didexchange/create-request?their_public_did={}&protocol={}&use_public_did={}".format(
            their_public_did, urllib.parse.quote_plus(protocol), str(use_public_did).lower()
        )
        return await self.admin_POST(uri)

    async def accept_invitation(self, conn_id, use_did = None):
        uri = "/didexchange/{}/accept-invitation".format(conn_id)
        if use_did:
            uri += "?use_did=" + use_did
        return await self.admin_POST(uri)

    async def accept_conn_request(self, conn_id, use_public_did = False):
        uri = "/didexchange/{}/accept-request?use_public_did={}".format(conn_id, str(use_public_did).lower())
        return await self.admin_POST(uri)

    async def issue_credential(self, conn_id, schema_and_creddef, attributes):
        uri = "/issue-credential-2.0/send"
        body = {
            "connection_id": conn_id,
            "credential_preview": {
                "@type": "issue-credential/2.0/credential-preview",
                "attributes": attributes
            },
            "filter": {
                "indy": {
                    "cred_def_id": schema_and_creddef[1],
                    "issuer_did": self.did,
                    "schema_id": schema_and_creddef[0],
                    "schema_issuer_did": self.did,
                }
            }
        }
        return await self.admin_POST(uri, body)

    async def get_credentials(self):
        return await self.admin_GET("/issue-credential-2.0/records")

    async def get_credentials_for_pres_req(self, pres_ex_id):
        return await self.admin_GET("/present-proof-2.0/records/{}/credentials".format(pres_ex_id))

    async def send_presentation(self, pres_ex_id, credential):
        uri = "/present-proof-2.0/records/{}/send-presentation".format(pres_ex_id)
        body = {
            "indy": {
                "requested_attributes": {
                    attr: {
                        "cred_id": credential["cred_info"]["referent"],
                        "revealed": True
                    } for attr in credential["presentation_referents"]
                },
                "requested_predicates": {},
                "self_attested_attributes": {}
            }
        }
        return await self.admin_POST(uri, body)

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
            "--requests-through-public-did",
            "--auto-respond-credential-offer",
            "--auto-respond-credential-request",
            "--auto-store-credential",
            "--auto-verify-presentation",
            "--auto-disclose-features",
            ("--plugin", "acapy-plugins.serviceregistry.v1_0"),
            ("--plugin", "acapy-plugins.videostreaming.v1_0"),
            # ("--plugin", "http3.v1_0"),
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
        self.log_msg(f"Registering {self.ident} ...")
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
        self.log_msg(f"nym_info: {nym_info}")
        self.log_msg(f"Registered DID: {self.did}")

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
            functools.partial(self.log_agent_msg, source="stdout"),
        )
        loop.run_in_executor(
            self.thread_pool_executor,
            output_reader,
            proc.stderr,
            functools.partial(self.log_agent_msg, source="stderr"),
        )
        return proc

    def get_process_args(self):
        return list(
            flatten(
                ([PYTHON, "-m", "aries_cloudagent", "start"], self.get_agent_args())
            )
        )

    async def start_process(self, python_path: str = None, wait: bool = True):
        await self._init_wallet()

        my_env = os.environ.copy()
        python_path = DEFAULT_PYTHON_PATH if python_path is None else python_path
        if python_path:
            my_env["PYTHONPATH"] = python_path

        agent_args = self.get_process_args()
        self.log_msg(agent_args)

        # start agent sub-process
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(
            self.thread_pool_executor, self._process, agent_args, my_env, loop
        )
        self.proc = await asyncio.wait_for(future, 20)
        if wait:
            await asyncio.sleep(1.0)
            await self.detect_process()

    async def _init_wallet(self):
        wallet_path = storage_path("wallet", self.wallet_name)
        template_path = storage_path("wallet", self.ident.lower().replace(" ", ""))

        if template_path.exists():
            shutil.copytree(template_path, wallet_path, dirs_exist_ok=True)

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
            self.log_msg(f"Accepting TAA with: {taa_accept}")
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
            self.log_msg(f"Error during GET {path}: {str(e)}")
            raise

    async def admin_GET(
            self, path, text=False, params=None, headers=None
    ) -> ClientResponse:
        try:
            return await self.admin_request(
                "GET", path, None, text, params, headers=headers
            )
        except ClientError as e:
            self.log_msg(f"Error during GET {path}: {str(e)}")
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
            self.log_msg(f"Error during POST {path}: {str(e)}")
            raise

    async def admin_POST(
            self, path, data=None, text=False, params=None, headers=None, raise_error=True
    ) -> ClientResponse:
        try:
            return await self.admin_request(
                "POST", path, data, text, params, headers=headers
            )
        except ClientError as e:
            self.log_msg(f"Error during POST {path}: {str(e)}")
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
            self.log_msg(f"Error during PATCH {path}: {str(e)}")
            raise

    async def admin_PUT(
            self, path, data=None, text=False, params=None, headers=None
    ) -> ClientResponse:
        try:
            return await self.admin_request(
                "PUT", path, data, text, params, headers=headers
            )
        except ClientError as e:
            self.log_msg(f"Error during PUT {path}: {str(e)}")
            raise

    async def admin_DELETE(
            self, path, data=None, text=False, params=None, headers=None
    ) -> ClientResponse:
        try:
            return await self.admin_request(
                "DELETE", path, data, text, params, headers=headers
            )
        except ClientError as e:
            self.log_msg(f"Error during DELETE {path}: {str(e)}")
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
            self.log_msg(f"Error during GET FILE {path}: {str(e)}")
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
            self.log_msg(f"Error during PUT FILE {url}: {str(e)}")
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
            auto_accept: bool = False,
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

    async def receive_invite(self, invite):
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

    def set_log_callbacks(self, agent_log_callback, controller_log_callback):
        self.agent_log_callback = agent_log_callback
        self.controller_log_callback = controller_log_callback

        for log in self.agent_log_cache:
            self.log_agent_msg(log)
        self.agent_log_cache = []

        for log in self.controller_log_cache:
            self.log_msg(log)
        self.controller_log_cache = []

    def log_msg(self, msg):
        if isinstance(msg, list):
            msg = str(" ".join(msg))
        else:
            msg = str(msg).rstrip()

        if self.controller_log_callback is None:
            self.controller_log_cache.append(msg)
            return

        self.controller_log_callback(msg)

    def log_agent_msg(self, msg, source: str = None):
        if isinstance(msg, list):
            msg = str(" ".join(msg))
        else:
            msg = str(msg).rstrip()

        if source == "stderr":
            color = "[bold red]"
        elif not source:
            color = "[blue]"
        else:
            color = ""

        if self.agent_log_callback is None:
            self.agent_log_cache.append(color + msg)
            return

        self.agent_log_callback(color + msg)

    def log_json(self, msg, label=None):
        if label is not None:
            self.log_msg(label)
        self.log_msg(msg)


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
