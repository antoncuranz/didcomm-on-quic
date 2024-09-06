import argparse
import asyncio
import logging

from services.common.aries_agent import fetch_genesis_txns
from services.discovery.app import DiscoveryService
from .agent import Agent

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

parser = argparse.ArgumentParser()

parser.add_argument(
    "--ip",
    default="localhost",
    help="External host IP",
)
parser.add_argument(
    "ident",
    type=str,
    help="Agent identity (label)"
)
parser.add_argument(
    "-p",
    "--port",
    type=int,
    default=8020,
    help="Choose the starting port number to listen on",
)
parser.add_argument(
    "--broadcast-invitations",
    action="store_true"
)
parser.add_argument(
    "--receive-invitations",
    action="store_true"
)

async def main(args):
    genesis_data = await fetch_genesis_txns("http://test.bcovrin.vonx.io/genesis")
    agent = Agent(args.ident, genesis_data, http_port=args.port, external_host=args.ip,
                  broadcast_invitations=args.broadcast_invitations, receive_invitations=args.receive_invitations)
    app = DiscoveryService(agent)

    try:
        asyncio.create_task(agent.initialize())
        await app.run_async()
    finally:
        await agent.terminate()


if __name__ == "__main__":
    asyncio.run(main(parser.parse_args()), debug=True)
